import math
import os

import bmesh
import bpy
import mathutils

from ..batch_utils import BatchProcessOperatorMixin, BatchProcessRunner
from ..constants import BATCH_TASK_RENDER_PREVIEW, IMG_TYPE_EXT_MAP

from ..utils import (
    check_batch_props,
    deselect_all_objects,
    find_ancestor,
    find_children,
    find_pmx_armature,
    find_pmx_objects,
    hide_object,
    import_pmx,
    recursive_search_img,
    restore_selection,
    select_and_activate,
    show_object,
    view3d_context,
)


class GenPreviewCameraOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.gen_preview_camera"
    bl_label = "预览"
    bl_description = "根据当前设置的参数生成预览相机并切换到摄像机视角，重复点击时会更新预览相机参数"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if not self.check_props():
            return {'CANCELLED'}
        scene = context.scene
        props = scene.mmd_kafei_tools_render_preview
        camera_to_view_selected(props)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self):
        objs = bpy.context.selected_objects
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=f'Select at least one object!')
            return False
        return True


class RenderPreviewBatchRunner(BatchProcessRunner):
    """批量渲染执行器：按图片格式扫描模型并逐个渲染预览图"""

    def search_files(self):
        output_format = bpy.context.scene.render.image_settings.file_format
        batch = self.props.batch
        return recursive_search_img(
            self.abs_path,
            batch.suffix,
            batch.threshold,
            batch.search_strategy,
            batch.conflict_strategy,
            IMG_TYPE_EXT_MAP[output_format],
            stats=self.search_stats,
        )

    def process_file(self, filepath):
        output_format = bpy.context.scene.render.image_settings.file_format
        new_filepath = os.path.splitext(filepath)[0] + self.suffix + IMG_TYPE_EXT_MAP[output_format]
        import_pmx(filepath)
        pmx_root = bpy.context.active_object
        pmx_armature = find_pmx_armature(pmx_root)
        convert_materials(pmx_armature, self.props.force_center)

        # 相机对准角色
        show_object(pmx_root)
        hide_object(pmx_armature)
        select_and_activate(pmx_root)
        camera_to_view_selected(self.props)

        # 隐藏可能会对渲染结果造成影响的物体
        deselect_all_objects()
        hide_object(pmx_root)

        # 渲染，完成后恢复原始输出路径
        original_output_path = bpy.context.scene.render.filepath
        # Blender 会将输出路径中的 {} 解析为模板表达式，路径中的大括号需转义
        bpy.context.scene.render.filepath = new_filepath.replace("{", "{{").replace("}", "}}")
        try:
            render(False)
        finally:
            bpy.context.scene.render.filepath = original_output_path


class RenderPreviewOperator(BatchProcessOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.render_preview"
    bl_label = "渲染"
    bl_description = "渲染预览图\n渲染逻辑相当于点击预览按钮并执行图像渲染\n勾选批量参数后，按钮将切换为批量渲染模式"
    bl_options = {'REGISTER', 'UNDO'}
    batch_task = BATCH_TASK_RENDER_PREVIEW
    batch_runner_class = RenderPreviewBatchRunner

    def execute(self, context):
        props = context.scene.mmd_kafei_tools_render_preview
        if not self.check_render_preview_props(props):
            return {'CANCELLED'}
        if props.batch.flag:
            return self.start_batch_process(context, props, None)
        self.render_single(props)
        return {'FINISHED'}

    def render_single(self, props):
        objs = bpy.context.selected_objects
        if len(objs) != 0:
            camera_to_view_selected(props)
        render(True)

    def check_render_preview_props(self, props):
        batch = props.batch
        batch_flag = batch.flag
        if batch_flag:
            if not check_batch_props(self, batch):
                return False
            output_format = bpy.context.scene.render.image_settings.file_format
            if output_format not in IMG_TYPE_EXT_MAP.keys():
                self.report(type={'ERROR'}, message=f'Unsupported output format! Use image format instead.')
                return False
        else:
            objs = bpy.context.selected_objects
            if len(objs) == 0:
                self.report(type={'ERROR'}, message=f'Select at least one object!')
                return False
        return True


def convert_materials(pmx_armature, force_center):
    pmx_objects = find_pmx_objects(pmx_armature)
    if not pmx_objects:
        return
    obj = pmx_objects[0]

    if not obj.material_slots:
        return
    # 材质名称与alpha值的映射
    mat_alpha_map = {}
    for slot in obj.material_slots:
        material = slot.material
        if not material:
            continue
        alpha = material.mmd_material.alpha
        mat_alpha_map[material.name] = alpha

    deselect_all_objects()
    select_and_activate(obj)
    bpy.ops.mmd_tools.convert_materials()

    # 将当前材质的不透明度恢复为材质转换前的不透明度
    for material_name, alpha in mat_alpha_map.items():
        material = bpy.data.materials.get(material_name)
        node_tree = material.node_tree
        nodes = node_tree.nodes
        for node in nodes:
            if node.type == 'BSDF_PRINCIPLED':
                if bpy.app.version < (4, 0, 0):
                    specular_node = node.inputs['Specular']
                else:
                    specular_node = node.inputs['Specular IOR Level']
                specular_node.default_value = 0
                if alpha == 1:
                    continue
                alpha_node = node.inputs['Alpha']
                for link in material.node_tree.links:
                    if link.to_node == node and link.to_socket == alpha_node:
                        material.node_tree.links.remove(link)
                alpha_node.default_value = alpha

    if not force_center:
        return

    # 必须处于顶点选择模式，且无点线面被选择
    deselect_all_objects()
    select_and_activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode="OBJECT")
    # 先删除alpha为0的材质所对应的面（仅面），再删除无法构成面的顶点。
    # 避免通过“按材质分开”/“bmesh”的方式来删除，防止影响模型法向。
    remove_alpha_zero_mesh(obj)
    remove_unused_verts(obj)


def remove_unused_verts(obj):
    mesh = obj.data

    bm = bmesh.new()
    bm.from_mesh(mesh)

    # 取消全部顶点选择
    for v in bm.verts:
        v.select = False

    # 标记所有被使用的顶点
    used_vertex = set()
    for f in bm.faces:
        for v in f.verts:
            used_vertex.add(v.index)

    # 选中所有未使用的顶点
    unused_count = 0
    for v in bm.verts:
        if v.index not in used_vertex:
            v.select = True
            unused_count += 1

    # 写回 mesh
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type='VERT')
    bpy.ops.object.mode_set(mode="OBJECT")


def remove_alpha_zero_mesh(obj):
    deselect_all_objects()
    select_and_activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    for index, slot in enumerate(obj.material_slots):
        material = slot.material
        if not material:
            continue
        alpha = material.mmd_material.alpha
        if alpha != 0:
            continue
        obj.active_material_index = index
        bpy.ops.object.material_slot_select()
    bpy.ops.mesh.delete(type="ONLY_FACE")
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.material_slot_remove_unused()


def camera_to_view_selected(props, camera=None):
    do_camera_to_view_selected(props.type, props.align,
                               props.rotation_euler_x, props.rotation_euler_y, props.rotation_euler_z,
                               props.scale, camera)


def switch_to_camera_view():
    """切换视图到前视图 + 相机视角"""
    # 切换下视图（确保view_camera执行后肯定在相应视图）
    bpy.ops.view3d.view_axis(type='FRONT')
    # 视图 - 摄像机 对应快捷键0
    bpy.ops.view3d.view_camera()
    # 摄像机边界框 对应快捷键home
    bpy.ops.view3d.view_center_camera()


def do_camera_to_view_selected(camera_type, align,
                               rotation_euler_x, rotation_euler_y, rotation_euler_z,
                               scale, camera=None):
    if not camera:
        camera = gen_preview_camera(camera_type)

    # 备份当前选中和激活的对象
    active_object = bpy.context.active_object
    objs = bpy.context.selected_objects

    # 获取选中物体最外层祖先的孩子set
    ancestors = set()
    children = set()
    for obj in objs:
        ancestor = find_ancestor(obj)
        ancestors.add(ancestor)
    for ancestor in ancestors:
        children.update(find_children(ancestor))
    for child in children:
        select_and_activate(child)

    # 随便选择一个ancestor
    ancestor = next(iter(ancestors))
    if align:
        # 获取 ancestor 的坐标
        ancestor_location = ancestor.location.copy()
        # 将 ancestor 移动到 (0, 0, 0) 原点位置
        ancestor.location = mathutils.Vector((0, 0, 0))
        # 计算坐标差值
        delta = ancestor_location - mathutils.Vector((0, 0, 0))

    # 修改相机参数
    camera.rotation_mode = 'XYZ'

    camera.rotation_euler[0] = rotation_euler_x
    if align:
        camera.rotation_euler[1] = math.radians(0)
    else:
        camera.rotation_euler[1] = rotation_euler_y
    camera.rotation_euler[2] = rotation_euler_z

    if abs(camera.data.passepartout_alpha - 0.5) < 0.0001:
        camera.data.passepartout_alpha = 1

    if camera_type == "PERSPECTIVE":
        camera.data.type = 'PERSP'
    elif camera_type == "ORTHOGRAPHIC":
        camera.data.type = 'ORTHO'
    else:
        pass
    # 激活该相机
    bpy.context.scene.camera = camera

    if align:
        constraint = camera.constraints.new(type='LIMIT_LOCATION')
        # 设置局部X轴的最小值和最大值
        constraint.use_min_x = True
        constraint.use_max_x = True
        constraint.min_x = 0.0
        constraint.max_x = 0.0
        # 设置约束为局部空间
        constraint.owner_space = 'LOCAL'
        # 将这个约束放到首位
        camera.constraints.move(len(camera.constraints) - 1, 0)

    # 对准选中物体
    with bpy.context.temp_override(**view3d_context()):
        bpy.ops.view3d.camera_to_view_selected()
        if camera_type == "ORTHOGRAPHIC":
            for _ in range(10):
                bpy.ops.view3d.camera_to_view_selected()  # 正交需多执行n次
        switch_to_camera_view()

    if align:
        # 这里要选中后才能应用
        # 如果存在约束，用户调整相机角度时会受到限制拖拽不动，所以这里应用掉
        select_and_activate(camera)
        constraint = camera.constraints[0]
        bpy.ops.constraint.apply(constraint=constraint.name, owner='OBJECT')

        # 将 ancestor 移动回原来的位置
        ancestor.location = ancestor_location
        camera.location += delta

    # 调整边距
    if camera_type == "PERSPECTIVE":
        # 这里实际上修改的是视野，而非“焦距”
        camera.data.angle = camera.data.angle * scale
    elif camera_type == "ORTHOGRAPHIC":
        camera.data.ortho_scale = camera.data.ortho_scale * scale
    else:
        pass

    # 恢复默认选中
    restore_selection(objs, active_object)


def gen_preview_camera(camera_type):
    # 在“预览相机”集合中生成一个相机
    # 检查是否已有名为“预览相机”的相机对象
    # 即使场景中存在其它相机，也不把这个相机进行返回，因为不清楚这个相机的用途
    camera_name = bpy.app.translations.pgettext_iface("预览相机")
    custom_property_name = 'preview_camera'
    for camera in bpy.data.objects:
        if camera.type == 'CAMERA' and custom_property_name in camera.keys():

            # 恢复相机参数默认值
            if camera_type == "PERSPECTIVE":
                camera.data.lens_unit = 'MILLIMETERS'
                camera.data.lens = 50
            elif camera_type == "ORTHOGRAPHIC":
                camera.data.ortho_scale = 6
            else:
                pass
            return camera
    # 场景中是否含有名称为“预览相机”的集合，没有则不一定新建（没有相机的情况下才会新建）
    collection_name = bpy.app.translations.pgettext_iface("相机")
    if collection_name in bpy.data.collections:
        preview_collection = bpy.data.collections[collection_name]
    else:
        preview_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(preview_collection)

    camera_data = bpy.data.cameras.new(name=camera_name)
    camera = bpy.data.objects.new(name=camera_name, object_data=camera_data)
    camera[custom_property_name] = True

    preview_collection.objects.link(camera)
    return camera


def render(view_show):
    """
    渲染预览图。
    视口上下文由 view3d_context 提供（后台也能取到 space_data）；
    后台模式没有 OpenGL 上下文，只能走完整渲染，且直接写文件而不是显示渲染结果。
    """
    with bpy.context.temp_override(**view3d_context()):
        # 没有可用的 3D 视图时 space_data 为 None，按 RENDERED 处理，即走完整渲染
        space_data = bpy.context.space_data
        shading_type = space_data.shading.type if space_data else 'RENDERED'
        show = view_show and not bpy.app.background
        use_opengl = shading_type != 'RENDERED' and not bpy.app.background
        # 视图 - 视图渲染图像
        if use_opengl:
            bpy.ops.render.opengl("INVOKE_DEFAULT" if show else "EXEC_DEFAULT", write_still=not show)
        else:  # 渲染 - 渲染图像
            bpy.ops.render.render("INVOKE_DEFAULT" if show else "EXEC_DEFAULT", write_still=not show)
        # 渲染 - 查看渲染结果
        if show:
            bpy.ops.render.view_show()
