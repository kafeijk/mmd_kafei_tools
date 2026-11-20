import math
import os

import bmesh
import bpy
import mathutils
import numpy as np
from mathutils.bvhtree import BVHTree

from ..batch_utils import BatchProcessOperatorMixin, BatchProcessRunner
from ..constants import (
    ARM_ANGLE_LIMIT,
    ARM_ANGLE_STEP,
    ARM_EXCLUDED_GROUP_NAMES,
    BATCH_TASK_RENDER_PREVIEW,
    BATCH_TASK_RENDER_THREE_VIEW,
    IMG_TYPE_EXT_MAP,
    MATERIAL_ALPHA_EPSILON,
    OBJECT_NAME_MAX_BYTES,
    PREVIEW_BOUNDS_PROXY_NAME,
    THREE_VIEW_BACK_COPY_LABEL,
    THREE_VIEW_CAMERA_CLIP_MARGIN,
    THREE_VIEW_CAMERA_DISTANCE_MARGIN,
    THREE_VIEW_CAMERA_NAME,
    THREE_VIEW_CENTER_PERCENTILE,
    THREE_VIEW_CLIP_CUBE_NAME,
    THREE_VIEW_CLIP_DEPTH_MARGIN,
    THREE_VIEW_CLIP_MODIFIER_NAME,
    THREE_VIEW_CLOSEUP_COPY_LABEL,
    THREE_VIEW_CLOSEUP_EYE_HEIGHT_RATIO,
    THREE_VIEW_EYE_BONE_RANGE_RATIO,
    THREE_VIEW_COLLECTION_NAME,
    THREE_VIEW_HEAD_FALLBACK_RATIO,
    THREE_VIEW_HEAD_EYE_RANGE_RATIO,
    THREE_VIEW_HEAD_SYMMETRY_TOLERANCE,
    THREE_VIEW_OFFSCREEN_GAP,
    THREE_VIEW_SIDE_COPY_LABEL,
    THREE_VIEW_TEMP_FLAG,
    THREE_VIEW_TEMP_SOURCE,
)

from ..utils import (
    check_batch_props,
    deselect_all_objects,
    find_ancestor,
    find_children,
    find_pmx_armature,
    find_pmx_objects,
    get_collection,
    hide_object,
    import_pmx,
    is_mmd_rigid_body,
    recursive_search_img,
    restore_selection,
    select_and_activate,
    show_object,
    translate,
    view3d_context,
)


class GenPreviewCameraOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.gen_preview_camera"
    bl_label = "预览"
    bl_description = "根据当前设置的参数生成预览相机并切换到摄像机视角，重复点击时会更新预览相机参数"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        props = context.scene.mmd_kafei_tools_render_preview
        if not self.check_props():
            return {'CANCELLED'}

        # 选中的是上一轮三视图副本时，先换回原模型，否则副本被删后选择为空
        reselect_temp_sources()
        reset_three_view()
        if not self.check_props():
            return {'CANCELLED'}
        camera_to_view_selected(props)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self):
        objs = bpy.context.selected_objects
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=translate("请至少选择一个对象！"))
            return False
        return True


class GenThreeViewCameraOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.gen_three_view_camera"
    bl_label = "预览"
    bl_description = "根据当前设置的参数生成三视图预览相机并切换到摄像机视角，重复点击时会更新预览相机参数"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.mmd_kafei_tools_render_three_view
        ancestor = check_three_view_props(self.report)
        if ancestor is None:
            return {'CANCELLED'}
        if not preview_three_view(props, self.report, ancestor):
            return {'CANCELLED'}
        return {'FINISHED'}


class FillThreeViewBoneNamesOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_three_view_bone_names"
    bl_label = "填入选中的骨骼名称"
    bl_description = ("把选中的骨骼名称填入对应参数（支持物体模式、姿态模式和编辑模式）\n"
                      "请按需选择需要获取的骨骼")
    bl_options = {'REGISTER', 'UNDO'}

    target: bpy.props.EnumProperty(
        items=[
            ("HEAD", "头骨骼", "头部顶点组名称"),
            ("EYE", "目骨骼", "眼部顶点组名称"),
            ("UPPER", "大臂骨骼", "大臂骨骼名称"),
            ("FOREARM", "小臂骨骼", "小臂骨骼名称"),
        ],
    )

    def execute(self, context):
        armature = context.active_object
        # 只需为骨架即可，不限于 MMD 模型
        if armature is None or armature.type != 'ARMATURE':
            self.report({'ERROR'}, translate("请选择骨架！"))
            return {'CANCELLED'}

        # 根据骨架当前模式获取选中骨骼，避免选择状态未同步
        if armature.mode == 'EDIT':
            names = [bone.name for bone in armature.data.edit_bones if bone.select]
        elif armature.mode == 'POSE':
            if bpy.app.version >= (5, 0, 0):
                names = [bone.name for bone in armature.pose.bones if bone.select]
            else:
                names = [bone.name for bone in armature.pose.bones if bone.bone.select]
        else:
            if bpy.app.version >= (5, 0, 0):
                names = [bone.name for bone in armature.pose.bones if bone.select]
            else:
                names = [bone.name for bone in armature.data.bones if bone.select]

        if not names:
            self.report({'ERROR'}, translate("请选择骨骼！"))
            return {'CANCELLED'}

        # 左侧、右侧优先，再按名称排序，保证“左, 右”的阅读顺序
        names.sort(key=lambda name: (
            0 if name.endswith(".L") else
            1 if name.endswith(".R") else
            2,
            name
        ))

        props = context.scene.mmd_kafei_tools_render_three_view
        attribute = {"HEAD": "head_vg_names",
                     "EYE": "eye_vg_names",
                     "UPPER": "upper_arm_names",
                     "FOREARM": "forearm_names"}[self.target]
        setattr(props, attribute, ", ".join(names))
        return {'FINISHED'}


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
        convert_materials(pmx_armature, self.props.visible_only)

        # 相机对准角色
        show_object(pmx_root)
        hide_object(pmx_armature)
        select_and_activate(pmx_root)

        reset_three_view()
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


class RenderThreeViewBatchRunner(BatchProcessRunner):
    """批量渲染执行器：按图片格式扫描模型并逐个渲染三视图"""

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
        convert_materials(pmx_armature, self.props.visible_only)

        # 相机对准角色
        show_object(pmx_root)
        hide_object(pmx_armature)
        select_and_activate(pmx_root)

        if not render_three_view(self.props, self.report, pmx_root,
                                 output_filepath=new_filepath, cleanup=True):
            raise RuntimeError(translate("三视图渲染失败"))


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
        if not self.render_single(props):
            return {'CANCELLED'}
        return {'FINISHED'}

    def render_single(self, props):
        # 选中的是上一轮三视图副本时，先换回原模型，否则副本被删后取景没有对象
        reselect_temp_sources()
        reset_three_view()
        objs = bpy.context.selected_objects
        if len(objs) != 0:
            camera_to_view_selected(props)
        render(True)
        return True

    def check_render_preview_props(self, props):
        batch = props.batch
        batch_flag = batch.flag
        if batch_flag:
            if not check_batch_props(self, batch):
                return False
            output_format = bpy.context.scene.render.image_settings.file_format
            if output_format not in IMG_TYPE_EXT_MAP.keys():
                self.report(type={'ERROR'}, message=translate("输出文件格式不正确，请更改为图像类型格式！"))
                return False
        else:
            objs = bpy.context.selected_objects
            if len(objs) == 0:
                self.report(type={'ERROR'}, message=translate("请至少选择一个对象！"))
                return False
        return True


class RenderThreeViewOperator(BatchProcessOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.render_three_view"
    bl_label = "渲染"
    bl_description = "渲染三视图\n勾选批量参数后，按钮将切换为批量渲染模式"
    bl_options = {'REGISTER', 'UNDO'}
    batch_task = BATCH_TASK_RENDER_THREE_VIEW
    batch_runner_class = RenderThreeViewBatchRunner

    def execute(self, context):
        props = context.scene.mmd_kafei_tools_render_three_view
        if props.batch.flag:
            if not check_batch_props(self, props.batch):
                return {'CANCELLED'}
            output_format = bpy.context.scene.render.image_settings.file_format
            if output_format not in IMG_TYPE_EXT_MAP.keys():
                self.report(type={'ERROR'}, message=translate("输出文件格式不正确，请更改为图像类型格式！"))
                return {'CANCELLED'}
            return self.start_batch_process(context, props, None)

        ancestor = check_three_view_props(self.report)
        if ancestor is None:
            # 模型可能已被删除，清理残留的临时对象并恢复状态
            reset_three_view()
            return {'CANCELLED'}
        if not render_three_view(props, self.report, ancestor):
            return {'CANCELLED'}
        return {'FINISHED'}


def convert_materials(pmx_armature, visible_only):
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

    if not visible_only:
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
    reset_three_view()
    do_camera_to_view_selected(props.type,
                               props.rotation_euler_x, props.rotation_euler_y, props.rotation_euler_z,
                               props.scale, camera,
                               visible_only=props.visible_only)


def get_visible_bounds(meshes):
    """
    可见几何的世界包围盒 (min_x, max_x, min_y, max_y, min_z, max_z)；没有可见几何时返回 None

    只统计“至少属于一个可见面”的顶点，完全透明材质（隐藏的尾巴、耳朵）覆盖的顶点不参与。
    """
    # 先只看材质：整块材质都不可见的网格直接跳过，全部可见的网格不必再算顶点掩码
    targets = []
    for obj in meshes:
        flags = [is_material_visible(slot.material) for slot in obj.material_slots]
        if flags and not any(flags):
            continue
        targets.append((obj, not all(flags)))

    world_vertices = evaluate_world_vertices([obj for obj, _ in targets])
    arrays = []
    for obj, need_mask in targets:
        vertices = world_vertices.get(obj)
        if vertices is None or not len(vertices):
            continue
        if need_mask:
            mask = get_visible_vertex_mask(obj)
            # 修改器改变了顶点数（如焊接等生成类修改器）时掩码长度对不上，按全部可见处理
            if len(mask) == len(vertices):
                vertices = vertices[mask]
        if len(vertices):
            arrays.append(vertices)
    if not arrays:
        return None
    return points_bounds(np.concatenate(arrays))


def create_visible_bounds_proxies(ancestors):
    """
    为每个模型创建一个只含“可见包围盒 8 个角点”的临时网格，作为取景对象

    临时网格挂在模型 root 下（跟随 root 一起移动），取景结束后由 remove_visible_bounds_proxies 立即删除。
    """
    collection = bpy.context.scene.collection
    proxies = []
    for ancestor in ancestors:
        bounds = get_visible_bounds(get_renderable_meshes(ancestor))
        if bounds is None:
            continue
        min_x, max_x, min_y, max_y, min_z, max_z = bounds
        # 角点先按世界坐标给出，再换算到 root 的局部空间：
        # 这样 root 被临时移到原点取景时，角点会跟着一起走
        to_local = ancestor.matrix_world.inverted()
        corners = [to_local @ mathutils.Vector((x, y, z))
                   for x in (min_x, max_x) for y in (min_y, max_y) for z in (min_z, max_z)]
        mesh = bpy.data.meshes.new(PREVIEW_BOUNDS_PROXY_NAME)
        mesh.from_pydata([tuple(corner) for corner in corners], [], [])
        mesh.update()
        proxy = bpy.data.objects.new(PREVIEW_BOUNDS_PROXY_NAME, mesh)
        collection.objects.link(proxy)
        # 挂到 root 下，root 移动时包围盒同步跟随
        proxy.parent = ancestor
        proxies.append(proxy)
    return proxies


def remove_visible_bounds_proxies(proxies):
    """删除取景用的临时包围盒网格"""
    for proxy in proxies:
        mesh = proxy.data
        bpy.data.objects.remove(proxy, do_unlink=True)
        bpy.data.meshes.remove(mesh)


def switch_to_camera_view():
    """切换视图到前视图 + 相机视角"""
    # 切换下视图（确保view_camera执行后肯定在相应视图）
    bpy.ops.view3d.view_axis(type='FRONT')
    # 视图 - 摄像机 对应快捷键0
    bpy.ops.view3d.view_camera()
    # 摄像机边界框 对应快捷键home
    bpy.ops.view3d.view_center_camera()


def do_camera_to_view_selected(camera_type,
                               rotation_euler_x, rotation_euler_y, rotation_euler_z,
                               scale, camera=None, visible_only=False):
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

    # 仅可见网格：取景对象换成“可见几何的包围盒”，完全透明的部位（隐藏的尾巴、耳朵）不再参与取景
    proxies = create_visible_bounds_proxies(ancestors) if visible_only else []
    try:
        # 有临时包围盒时只用包围盒（8 个角点）取景，否则沿用模型本身的包围盒
        # 用包围盒时必须先清空选择，否则原模型仍被选中，它的包围盒会一起参与取景，等于没排除不可见部位
        if proxies:
            deselect_all_objects()
            for proxy in proxies:
                select_and_activate(proxy)
        else:
            for child in children:
                select_and_activate(child)

        # 仅单个角色且Y轴旋转为0时才能对齐；多角色或Y轴有值时无法对齐，直接由 camera_to_view_selected 取景
        # 开启自动参数后会存在一定误差，所以用 1e-3 而不是 1e-6
        align = len(ancestors) == 1 and abs(rotation_euler_y) < 1e-3

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
            # 这里实际上修改的是视野（FOV），而非“焦距”
            #
            # 视野角取决于 sensor_fit：默认的 AUTO 取渲染画幅较长的一边，即 angle_x 与 angle_y 中较大的那个。
            # 预览分辨率默认 1080P（1920×1080，横版），所以 camera.data.angle 是左右方向的水平视角；
            # 若分辨率为竖版（如交换 XY），较长边变为高度，angle 则转为上下方向的垂直视角。
            #
            # 问：根据当前视野角下角色在画幅中的位置，使其长宽变为原来的1/n，求新视野角。
            # 推导：设视野角为 θ，距离 d 处画面的半宽（或半高）为 h = d·tan(θ/2)。
            # 物体半宽为 r 时占画面比例 r / (d·tan(θ/2))，要让占比变成 1/n，只需让 tan(θ/2) 变成 n·tan(θ/2)：
            #   tan(θ'/2) = n·tan(θ/2)
            #   θ' = 2·atan(n·tan(θ/2))
            #
            # 之所以改视野而不用相机后退：改视野是以光心为中心的等比缩放，画面每个点的投影距离都按 1/n 缩小，
            # 与物体离相机的远近无关，横竖两方向同步缩放且画幅比例不变；
            # 而相机后退会让不同深度的物体缩放比例不一致，透视关系发生变化。
            camera.data.angle = 2 * math.atan(math.tan(camera.data.angle / 2) * scale)
        elif camera_type == "ORTHOGRAPHIC":
            # ortho_scale 本身就是可见尺寸（较长边），线性缩放即精确，无需 tan 换算
            camera.data.ortho_scale = camera.data.ortho_scale * scale
        else:
            pass

        # 恢复默认选中
        restore_selection(objs, active_object)
    finally:
        # 临时包围盒用完即删；放在 finally 里，异常时也不会残留在场景中
        remove_visible_bounds_proxies(proxies)


def gen_preview_camera(camera_type):
    # 在“预览相机”集合中生成一个相机
    # 检查是否已有名为“预览相机”的相机对象
    # 即使场景中存在其它相机，也不把这个相机进行返回，因为不清楚这个相机的用途
    camera_name = translate("预览相机")
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
    collection_name = translate("相机")
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


def gen_three_view_camera():
    """生成三视图相机，重复执行时直接复用"""
    camera_name = translate(THREE_VIEW_CAMERA_NAME)
    custom_property_name = 'three_view_camera'
    for camera in bpy.data.objects:
        if camera.type == 'CAMERA' and custom_property_name in camera.keys():
            return camera

    collection_name = translate("相机")
    if collection_name in bpy.data.collections:
        target_collection = bpy.data.collections[collection_name]
    else:
        target_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(target_collection)

    camera_data = bpy.data.cameras.new(name=camera_name)
    camera = bpy.data.objects.new(name=camera_name, object_data=camera_data)
    camera[custom_property_name] = True
    target_collection.objects.link(camera)
    return camera


def get_renderable_meshes(ancestor):
    """模型祖先下参与渲染的网格对象（排除隐藏与 mmd 刚体）"""
    objects = [ancestor] if ancestor.type == 'MESH' else []
    objects.extend(ancestor.children_recursive)
    return [obj for obj in objects
            if obj.type == 'MESH' and not is_mmd_rigid_body(obj)
            and not obj.hide_get() and not obj.hide_viewport]

def collect_ancestors():
    """
    收集选中对象对应的模型 root

    三视图临时对象都带 kafei_temp 标记，选中时按记录的 root 名找回原模型，
    不会把副本当成新模型。
    """
    ancestors = set()
    for obj in bpy.context.selected_objects:
        if obj.get(THREE_VIEW_TEMP_FLAG):
            source_name = obj.get(THREE_VIEW_TEMP_SOURCE)
            source = bpy.data.objects.get(source_name) if source_name else None
            if source is not None:
                ancestors.add(source)
            continue
        ancestor = find_ancestor(obj)
        if ancestor is not None:
            ancestors.add(ancestor)
    return ancestors


def get_missing_temp_source():
    """
    选中的临时对象所引用的源对象已不存在时，返回该源对象名；否则返回 None

    例如源模型被删除、重命名后，按记录的名字找不到源对象，需要提示用户重新选择源对象。
    """
    for obj in bpy.context.selected_objects:
        if not obj.get(THREE_VIEW_TEMP_FLAG):
            continue
        source_name = obj.get(THREE_VIEW_TEMP_SOURCE)
        if source_name and bpy.data.objects.get(source_name) is None:
            return source_name
    return None


def reselect_temp_sources():
    """
    把选中的三视图临时副本换成它对应的原模型

    临时副本会被 reset_three_view 删除，若继续用副本取景，删除后选择为空；
    副本记录了原模型名（kafei_source_root），这里提前改选原模型。
    """
    temp_objects = [obj for obj in bpy.context.selected_objects if obj.get(THREE_VIEW_TEMP_FLAG)]
    if not temp_objects:
        return

    sources = []
    for temp in temp_objects:
        temp.select_set(False)
        source_name = temp.get(THREE_VIEW_TEMP_SOURCE)
        source = bpy.data.objects.get(source_name) if source_name else None
        if source is not None and source not in sources:
            sources.append(source)
    for source in sources:
        source.select_set(True)
    if sources:
        bpy.context.view_layer.objects.active = sources[0]


def capture_temp_selection():
    """
    记录执行前选中的三视图临时对象名称

    返回空列表表示当前不是“选中临时对象”的场景，执行后不需要干预选中。
    """
    return [obj.name for obj in bpy.context.selected_objects if obj.get(THREE_VIEW_TEMP_FLAG)]


def restore_temp_selection(names, ancestor):
    """
    三视图执行后恢复选中，避免再次执行时提示“请选择对象”

    临时对象会先被删除再按原模型重新生成，名字通常不变，按名字选回即可；
    名字找不到时（例如换成别的模型、副本数量变化）退回选中原模型 root。
    """
    if not names:
        return
    objects = [obj for obj in (bpy.data.objects.get(name) for name in names)
               if obj is not None and obj.get(THREE_VIEW_TEMP_FLAG)]
    if not objects:
        objects = [ancestor] if ancestor is not None else []
    if not objects:
        return
    deselect_all_objects()
    for obj in objects:
        select_and_activate(obj)


def check_three_view_props(report):
    """
    三视图参数校验：解析并返回要渲染的模型，校验失败返回 None

    必须选中模型才能执行；选中临时对象时，按临时对象记录的 root 名找回原模型。
    """
    missing_source = get_missing_temp_source()
    if missing_source:
        report({'ERROR'}, translate("当前选中对象是“{}”的副本，未找到对应的源对象，请检查是否被更名或删除。请先选择源对象，再执行此操作。")
               .format(missing_source))
        return None

    ancestors = collect_ancestors()
    if len(ancestors) > 1:
        report({'ERROR'}, translate("仅支持单个模型！"))
        return None
    if not ancestors:
        report({'ERROR'}, translate("请选择模型！"))
        return None

    ancestor = next(iter(ancestors))
    if get_armature(ancestor) is None:
        report({'ERROR'}, translate("未找到骨架！"))
        return None
    if not get_renderable_meshes(ancestor):
        report({'ERROR'}, translate("未找到可渲染的网格。"))
        return None
    return ancestor


def mark_temp_object(obj, source_root_name):
    obj[THREE_VIEW_TEMP_FLAG] = True
    obj[THREE_VIEW_TEMP_SOURCE] = source_root_name


def cleanup_three_view_collection():
    """
    删除三视图临时对象；集合内没有残留物体时才删除该集合

    若用户手工往临时集合里放过其它物体，则保留集合，避免误删。
    """
    for obj in list(bpy.data.objects):
        if obj.get(THREE_VIEW_TEMP_FLAG):
            bpy.data.objects.remove(obj, do_unlink=True)

    collection = bpy.data.collections.get(THREE_VIEW_COLLECTION_NAME)
    if collection is not None and len(collection.objects) == 0:
        bpy.data.collections.remove(collection)

def reset_poses(ancestor=None, update=True):
    """把骨架姿态复位为静置姿态

    update：是否在复位后刷新依赖图；调用方紧接着还会更新依赖图时传 False，省一次全场景求值
    """
    armature = get_armature(ancestor)
    if not armature:
        return

    identity = mathutils.Matrix.Identity(4)
    changed = False
    for pose_bone in armature.pose.bones:
        if pose_bone.matrix_basis != identity:
            pose_bone.matrix_basis = identity
            changed = True
    # 已经是静置姿态时跳过依赖图求值，避免重复执行时白等一次全场景更新
    if changed and update:
        bpy.context.view_layer.update()


def reset_root_transform(ancestor):
    """
    重置原模型 root 的变换

    三视图会按布局重写 root 的缩放与位置，归零后再摆放可保证重复执行时
    不累积缩放/位移；原模型原有的变换不保留。
    """
    ancestor.matrix_world = mathutils.Matrix.Identity(4)
    bpy.context.view_layer.update()


def reset_three_view(ancestor=None):
    """三视图统一复位：删临时对象，骨架姿态恢复为静置"""
    cleanup_three_view_collection()
    reset_poses(ancestor)


def get_armature(ancestor=None):
    """获取模型骨架：优先当前激活的骨架，其次是模型自身或其子孙中的骨架"""
    # 候选顺序：激活对象 → 模型 root → root 的子孙，统一用同一套过滤条件
    # children_recursive 是一次 C 级遍历（几百个物体也只要零点几毫秒），
    # 比逐层递归读取 .children 快两个数量级（MMD 模型有近千个子物体）
    candidates = [bpy.context.view_layer.objects.active]
    if ancestor is not None:
        candidates.append(ancestor)
        candidates.extend(ancestor.children_recursive)
    for obj in candidates:
        if (obj is not None and obj.type == 'ARMATURE'
                and ".dummy_armature" not in obj.name
                and not obj.get(THREE_VIEW_TEMP_FLAG)):
            return obj
    return None


def rotate_arm_bone(armature, bone_name, angle_degrees, sign, base_world=None):
    """绕世界 Y 轴旋转腕骨骼；base_world 为基础姿态下的世界矩阵，避免每次读取评估结果"""
    pose_bone = armature.pose.bones[bone_name]
    world = base_world if base_world is not None else armature.matrix_world @ pose_bone.matrix
    pivot = world.translation
    rotation = mathutils.Matrix.Rotation(math.radians(angle_degrees) * sign, 4, 'Y')
    matrix = mathutils.Matrix.Translation(pivot) @ rotation @ mathutils.Matrix.Translation(-pivot)
    pose_bone.matrix = armature.matrix_world.inverted() @ matrix @ world


def evaluate_world_vertices(objects):
    """
    一次性读取评估后网格（含修改器与姿态）的世界坐标，{对象: (n, 3) 数组}

    取的是“评估后”的网格：布尔、骨架、形态键等修改器的最终结果都在里面；
    顶点用 foreach_get 整体拷出，再用 numpy 批量做矩阵变换，避免逐顶点访问 bpy。
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    result = {}
    for obj in objects:
        if obj.type != 'MESH':
            continue

        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.data
        count = len(mesh.vertices)
        # 空网格：返回形状 (0, 3) 的空数组，下游的分位数/包围盒计算可直接跳过
        if count == 0:
            result[obj] = np.zeros((0, 3), dtype=np.float32)
            continue

        # 先按一维缓冲整体拷出 (x, y, z, x, y, z, ...)，再重排成 (顶点数, 3)
        coords = np.empty(count * 3, dtype=np.float32)
        mesh.vertices.foreach_get('co', coords)
        coords = coords.reshape(count, 3)
        # matrix_world 为 4x4 齐次矩阵：左上 3x3 是旋转+缩放，最后一列前三个是平移
        matrix = np.array(eval_obj.matrix_world, dtype=np.float32)
        # 等价于逐点做 M @ v = R @ v + t（R 为 3x3，t 为平移）
        # .T 为转置，作用是交换行和列
        # Blender 的矩阵变换习惯使用列向量，而 NumPy 顶点坐标是按行排列的。
        result[obj] = coords @ matrix[:3, :3].T + matrix[:3, 3]
    return result


def points_bounds(points):
    """点集的三轴包围盒 (min_x, max_x, min_y, max_y, min_z, max_z)；空集返回 None"""
    if len(points) == 0:
        return None
    # points[:, 0]，: 表示选取所有行，0 表示选取第 0 列。
    return (float(points[:, 0].min()), float(points[:, 0].max()),
            float(points[:, 1].min()), float(points[:, 1].max()),
            float(points[:, 2].min()), float(points[:, 2].max()))


def bounds_from_vertices(vertex_map):
    """多个网格的世界坐标合并后求三轴包围盒；没有顶点时返回 None"""
    arrays = [vertices for vertices in vertex_map.values() if len(vertices)]
    if not arrays:
        return None
    return points_bounds(np.concatenate(arrays))


def find_shader_from_output(tree, node_name=None, node_type=None):
    """
    基于材质输出寻找着色器节点：返回直接连接到活动输出 Surface 的节点，没有则返回 None

    node_name：节点名称，如 mmd_shader
    node_type：节点类型（bl_idname），如 ShaderNodeBsdfPrincipled
    两者同时给出时命中任意一个即可；只认直接连接，中间夹了别的节点不算。
    """
    for output in tree.nodes:
        if output.type != 'OUTPUT_MATERIAL' or not output.is_active_output:
            continue
        for link in output.inputs['Surface'].links:
            target = link.from_node
            if node_type is not None and target.bl_idname == node_type:
                return target
            if node_name is not None and target.name == node_name:
                return target
    return None


def get_socket_alpha(socket):
    """读取输入接口 Alpha 的当前值；接口不存在时按 1.0（可见）处理"""
    if socket is None:
        return 1.0
    # default_value 即为当前值
    return float(socket.default_value)


def is_material_visible(material):
    """材质是否可见"""
    if material is None:
        return True

    # OPAQUE 材质不做透明判断，一律可见
    if getattr(material, "blend_method", None) == 'OPAQUE':
        return True

    tree = material.node_tree
    if tree is None:
        return True

    # mmd_tools 材质：透明度由 mmd_shader 节点组的 Alpha 输入决定
    shader = find_shader_from_output(tree, node_name="mmd_shader")
    if shader is not None:
        return get_socket_alpha(shader.inputs.get("Alpha")) >= MATERIAL_ALPHA_EPSILON

    # 普通材质：材质输出直接连原理化 BSDF 时，看它的 Alpha
    principled = find_shader_from_output(tree, node_type='ShaderNodeBsdfPrincipled')
    if principled is not None:
        return get_socket_alpha(principled.inputs.get("Alpha")) >= MATERIAL_ALPHA_EPSILON

    return True


def get_face_material_indices(mesh):
    """读取每个面的材质索引"""
    count = len(mesh.polygons)
    indices = np.empty(count, dtype=np.int32)
    attribute = mesh.attributes.get("material_index")
    if attribute is not None and len(attribute.data) == count:
        attribute.data.foreach_get('value', indices)
    elif count:
        mesh.polygons.foreach_get('material_index', indices)
    return indices


def get_loop_vertices(mesh):
    """读取每个 loop 的顶点索引"""
    count = len(mesh.loops)
    loops_vertex = np.empty(count, dtype=np.int32)
    attribute = mesh.attributes.get(".corner_vert")
    if attribute is not None and len(attribute.data) == count:
        attribute.data.foreach_get('value', loops_vertex)
    elif count:
        mesh.loops.foreach_get('vertex_index', loops_vertex)
    return loops_vertex


def get_visible_vertex_mask(obj):
    """
    按材质透明度求可见顶点掩码

    返回长度等于顶点数的 bool 数组：True 表示该顶点属于至少一个可见面。
    只被完全透明材质（alpha = 0，如隐藏的尾巴、影子）覆盖的顶点判为不可见。
    """
    mesh = obj.data
    count = len(mesh.vertices)
    # 默认全部可见；没有顶点或没有面时无从判断，直接返回全 True
    visible = np.ones(count, dtype=bool)
    if count == 0 or len(mesh.polygons) == 0:
        return visible

    # 每个材质槽是否可见（alpha > 0）——按槽位顺序得到 bool 数组
    material_flags = np.array([is_material_visible(slot.material) for slot in obj.material_slots], dtype=bool)
    # 每个面的材质索引（索引为面id，值为材质id）
    indices = get_face_material_indices(mesh)
    if len(material_flags):
        # 面的材质索引可能超出槽位数量（材质被删过），补到最大索引，超出的位置按可见处理
        flags = np.ones(max(len(material_flags), int(indices.max()) + 1), dtype=bool)
        flags[:len(material_flags)] = material_flags
        # 面索引 → 该面是否可见，用 indices 作为下标到 flags 里查表
        face_visible = flags[indices]
    else:
        face_visible = np.ones(len(mesh.polygons), dtype=bool)

    # 没有透明面，所有顶点可见，直接返回
    if face_visible.all():
        return visible

    # 顶点不可见只能通过“它所属的面全部不可见”判定：
    # loop 是面的拐角，loops_vertex 记录每个 loop 指向的顶点索引
    loops_vertex, _, loop_total = get_mesh_loops(mesh)
    # 把每个面的“是否可见”按 loop 数展开成“第 i 个 loop 所在面是否可见”
    loop_visible = np.repeat(face_visible, loop_total)
    # 取可见面覆盖的全部 loop 指向的顶点，一次性标记为可见
    visible = np.zeros(count, dtype=bool)
    visible[loops_vertex[loop_visible]] = True
    return visible


def has_transparent_material(obj):
    """网格是否含有透明（完全不可见）材质的材质槽"""
    return any(slot.material is not None and not is_material_visible(slot.material)
               for slot in obj.material_slots)


def build_visible_masks(mesh_objs, world_vertices, warnings):
    """
    可见顶点掩码：只对含透明材质的网格做可见性过滤

    生成类修改器（镜像、布尔、细分等）改变顶点数量时，该网格无法按原始顶点索引过滤，
    只有它自己回退为“全部可见”，其它网格照常过滤；
    受影响的网格汇总成一条警告，避免一个网格的问题影响整个模型。
    """
    masks = {}
    affected = []
    for obj in mesh_objs:
        count = len(obj.data.vertices)
        # 没有透明材质的网格不需要过滤，直接全部可见
        if not has_transparent_material(obj):
            masks[obj] = np.ones(count, dtype=bool)
            continue
        mask = get_visible_vertex_mask(obj)
        positions = world_vertices.get(obj)
        if positions is not None and len(positions) != len(mask):
            masks[obj] = np.ones(count, dtype=bool)
            affected.append(obj.name)
        else:
            masks[obj] = mask
    if affected:
        warnings.append(translate("检测到生成类修改器导致网格顶点数量发生变化，相关对象将按全部可见处理。"
                                  "涉及对象：{}。").format("、".join(affected)))
    return masks


def robust_center(values):
    """
    分位中心：取坐标值 2%~98% 区间的中点，作为横向居中位置

    直接取 (最小值 + 最大值) / 2 时，光环、露出的一小截尾巴这类稀疏几何会把中心拉偏
    这里先用 np.percentile 掐掉两端各 THREE_VIEW_CENTER_PERCENTILE%的顶点，再取中点，让中心跟着顶点密集的主体部分走。

    values 是某一条轴上的顶点坐标（世界坐标），返回浮点中心值。
    """
    if len(values) == 0:
        return 0.0
    # 掐掉两端的极值分位点，再取中点
    lower, upper = np.percentile(values, [THREE_VIEW_CENTER_PERCENTILE,
                                          100.0 - THREE_VIEW_CENTER_PERCENTILE])
    return float((lower + upper) / 2)


def visible_world_vertices(world, masks):
    """按可见掩码筛选世界坐标；顶点数对不上时按全部顶点可见处理"""
    result = {}
    for obj, vertices in world.items():
        mask = masks.get(obj)
        # 修改器改变了评估后的顶点数时，原始索引的掩码无法使用，只能整块按可见处理
        if mask is None or len(vertices) != len(mask):
            result[obj] = vertices
            continue
        result[obj] = vertices[mask]
    return result


def get_vertex_masks(obj, left_names, right_names, excluded_names, head_names, eye_names=None):
    """一次 bmesh 遍历，按顶点组生成左右手、身体、头部及眼部的顶点掩码"""
    mesh = obj.data
    count = len(mesh.vertices)
    masks = {key: np.zeros(count, dtype=bool) for key in ('l', 'r', 'body', 'head', 'eye')}
    if count == 0:
        return masks
    vg_name_map = {vg.index: vg.name for vg in obj.vertex_groups}
    left_vg_indexes = {index for index, name in vg_name_map.items() if name in left_names}
    right_vg_indexes = {index for index, name in vg_name_map.items() if name in right_names}
    excluded_vg_indexes = {index for index, name in vg_name_map.items() if name in excluded_names}
    head_vg_indexes = {index for index, name in vg_name_map.items() if name in head_names}
    eye_vg_indexes = {index for index, name in vg_name_map.items() if name in (eye_names or ())}
    if not (left_vg_indexes or right_vg_indexes or head_vg_indexes or eye_vg_indexes):
        return masks

    bm = bmesh.new()
    bm.from_mesh(mesh)
    deform = bm.verts.layers.deform.active
    if deform is not None:
        for vert in bm.verts:
            vg_indexes = {index for index, weight in vert[deform].items() if weight > 0}
            if not vg_indexes:
                continue
            index = vert.index
            is_left = bool(vg_indexes & left_vg_indexes)
            is_right = bool(vg_indexes & right_vg_indexes)
            if is_left:
                masks['l'][index] = True
            if is_right:
                masks['r'][index] = True
            if not (is_left or is_right) and (vg_indexes - excluded_vg_indexes):
                masks['body'][index] = True
            if vg_indexes & head_vg_indexes:
                masks['head'][index] = True
            if eye_vg_indexes and vg_indexes & eye_vg_indexes:
                masks['eye'][index] = True
    bm.free()
    return masks


def collect_head_masks(vg_data):
    return {obj: masks['head'] for obj, masks in vg_data.items()}


def collect_eye_masks(vg_data):
    return {obj: masks['eye'] for obj, masks in vg_data.items()}

def get_mesh_loops(mesh):
    loops_vertex = get_loop_vertices(mesh)
    loop_start = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_start', loop_start)
    loop_total = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_total', loop_total)
    return loops_vertex, loop_start, loop_total


def count_face_hits(loops_vertex, loop_start, loop_total, vertex_flags):
    """统计每个面有多少个拐角满足 vertex_flags

    vertex_flags：每个顶点一个布尔值（例如“属于该顶点组”“高于某高度”）。
    reduceat 以 loop_start 为切分点分段累加，把“按顶点的值”汇总成“按面的数量”。
    """
    if len(loop_total) == 0:
        return np.zeros(0, dtype=np.int32)
    return np.add.reduceat(vertex_flags[loops_vertex].astype(np.int32), loop_start)


def select_faces(loops_vertex, loop_start, loop_total, vertex_mask, world_z, max_z):
    """选出所有顶点都属于指定顶点组、且不高于 max_z 的面

    loops_vertex：第 i 个 loop（面的拐角）指向的顶点索引
    loop_start ：每个面的第一个 loop 在 loops_vertex 里的下标
    loop_total ：每个面的 loop 数（三角形为 3，四边形为 4）
    vertex_mask：每个顶点是否属于该顶点组
    world_z    ：每个顶点的世界 Z 坐标，可为 None
    max_z      ：面内顶点允许的最高 Z，超过则排除（用于忽略头部以上顶点）
    """
    # 每个拐角都命中 → 该面的所有顶点都在顶点组内
    inside_hits = count_face_hits(loops_vertex, loop_start, loop_total, vertex_mask)
    faces = inside_hits == loop_total
    if max_z is not None and world_z is not None:
        # 面内有顶点高于 max_z → 排除该面
        above_hits = count_face_hits(loops_vertex, loop_start, loop_total, world_z > max_z)
        faces &= above_hits == 0
    return faces


def compact_faces(loops_vertex, loop_start, loop_total, face_mask):
    """
    把选中的面压缩为局部顶点索引，供 BVH 使用

    返回 {'verts': 用到的全局顶点索引, 'faces': 以局部下标表示的多边形}
    """
    selected = np.nonzero(face_mask)[0]
    if len(selected) == 0:
        return None
    starts = loop_start[selected]
    totals = loop_total[selected]
    loop_count = int(totals.sum())
    # 选中面的 loop 是连续的，这里把它们在 loops_vertex 里的下标拼成一维：
    # repeat(starts) 给出每个面起点，再逐个面加上 0,1,2... 的偏移
    offsets = np.repeat(starts, totals)
    offsets += np.arange(loop_count) - np.repeat(np.cumsum(totals) - totals, totals)
    vertex_indices = loops_vertex[offsets]
    # 顶点去重并重映射为 0..n-1 的局部索引
    unique, inverse = np.unique(vertex_indices, return_inverse=True)
    # 按每个面的 loop 数切分 inverse，得到以局部索引表示的面
    faces = [tuple(face.tolist()) for face in np.split(inverse.reshape(-1), np.cumsum(totals)[:-1])]
    return {'verts': unique, 'faces': faces}


def split_names(text):
    """按中英文逗号拆分名称，去掉空白与空项"""
    return [name.strip() for name in text.replace('，', ',').split(',') if name.strip()]


def existing_bone_names(armature, names):
    """过滤出骨架中实际存在的骨骼名称；保持填写顺序并去重，避免同一骨骼被重复旋转"""
    result = []
    for name in names:
        if name in armature.data.bones and name not in result:
            result.append(name)
    return result


def collect_arm_bone_names(armature, upper_arm_names, forearm_names):
    """
    按大臂、小臂骨骼收集顶点组名称

    返回 (collision_names, excluded_names, collision_chains)：
    - collision_names：小臂及其全部子孙骨骼，参与穿模检测
    - excluded_names ：大臂及其全部子孙骨骼减去小臂子树，不计入“身体”，避免手臂穿模误判
    - collision_chains：按小臂分组的手臂链（小臂 + 其全部子孙），同一条链的左右一定相同
    """
    collision = set()
    upper_chain = set()
    collision_chains = []
    for name in forearm_names:
        forearm = armature.data.bones.get(name)
        if forearm is None:
            continue
        chain = {forearm.name}
        chain.update(child.name for child in forearm.children_recursive)
        collision |= chain
        collision_chains.append(chain)
    for name in upper_arm_names:
        upper = armature.data.bones.get(name)
        if upper is None:
            continue
        upper_chain.add(upper.name)
        upper_chain.update(child.name for child in upper.children_recursive)
    return collision, upper_chain - collision, collision_chains


def split_arm_chains_by_position(obj, chains):
    """
    顶点组名称没有 .L/.R 后缀时，按顶点位置判断**每条手臂链**的左右

    同一条手臂链（小臂及其子孙）上的骨骼都在同一侧，所以整条链只做一次判定：
    取链上所有顶点横向坐标 2%~98% 分位区间内的均值（排除两端极值顶点），
    再与整块网格的横向分位中心比较，偏 +X 侧算左手，偏 -X 侧算右手。
    """
    left, right = set(), set()
    if not chains:
        return left, right
    mesh = obj.data
    if len(mesh.vertices) == 0:
        return left, right
    # 顶点组索引 → 所属手臂链下标
    index_map = {vertex_group.index: chain_index
                 for chain_index, chain in enumerate(chains)
                 for vertex_group in obj.vertex_groups if vertex_group.name in chain}
    if not index_map:
        return left, right

    bm = bmesh.new()
    bm.from_mesh(mesh)
    deform = bm.verts.layers.deform.active
    if deform is None:
        bm.free()
        return left, right
    chain_x = [[] for _ in chains]
    all_x = []
    for vert in bm.verts:
        all_x.append(vert.co.x)
        for index, weight in vert[deform].items():
            chain_index = index_map.get(index)
            if weight > 0 and chain_index is not None:
                chain_x[chain_index].append(vert.co.x)
    bm.free()

    center_x = robust_center(np.array(all_x, dtype=np.float32))
    for chain, values in zip(chains, chain_x):
        if not values:
            continue
        points = np.array(values, dtype=np.float32)
        # 去掉两端极值后求均值，作为整条手臂链的横向中心
        lower, upper = np.percentile(points, [THREE_VIEW_CENTER_PERCENTILE,
                                              100.0 - THREE_VIEW_CENTER_PERCENTILE])
        band = points[(points >= lower) & (points <= upper)]
        chain_center = float(band.mean()) if len(band) else float(points.mean())
        (left if chain_center >= center_x else right).update(chain)
    return left, right


def classify_arm_sides(obj, chains):
    """把每条手臂链整体归到左手或右手：后缀优先（一条链同一侧），没有后缀时按顶点位置判断"""
    left, right = set(), set()
    unsuffixed = []
    for chain in chains:
        if any(name.endswith('.L') for name in chain):
            left |= chain
        elif any(name.endswith('.R') for name in chain):
            right |= chain
        else:
            unsuffixed.append(chain)
    if unsuffixed:
        left_extra, right_extra = split_arm_chains_by_position(obj, unsuffixed)
        left |= left_extra
        right |= right_extra
    return left, right


def collect_vertex_vg_data(mesh_objs, collision_names, excluded_names, head_names,
                           visible_masks=None, collision_chains=None, eye_names=None):
    """
    一次遍历得到穿模/身体/头部顶点掩码，供手臂角度与头部尺寸共用

    collision_names ：参与穿模检测的手臂顶点组（小臂及其子孙）
    excluded_names  ：不计入身体的手臂顶点组（大臂子树减去小臂子树）
    head_names      ：头部顶点组，用于特写取景与穿模高度过滤
    collision_chains：按小臂分组的手臂链，用于整体判断左右（没有 .L/.R 后缀时按位置判断）
    eye_names       ：眼部顶点组，用于限制头部包围盒的横向范围
    """
    collision = set(collision_names)
    excluded = set(excluded_names) | ARM_EXCLUDED_GROUP_NAMES
    data = {}
    for obj in mesh_objs:
        left, right = classify_arm_sides(obj, collision_chains or [])
        data[obj] = get_vertex_masks(obj, left, right, collision | excluded, set(head_names),
                                     eye_names)
    for obj, masks in data.items():
        visible = visible_masks.get(obj) if visible_masks else None
        if visible is None:
            visible = get_visible_vertex_mask(obj)
        if not visible.all():
            for key in masks:
                masks[key] &= visible
    return data


def build_arm_collision_data(mesh_objs, world, vg_data, need_body=True):
    """按顶点组把网格拆分为左右手部、身体与头部，用于穿模检测"""
    # 头部顶部 Z：手部/身体的面若含高于此处的顶点则不计入，避免头发、头饰干扰穿模判断
    head_top = None
    for obj in mesh_objs:
        masks = vg_data[obj]
        positions = world.get(obj)
        if positions is not None and len(positions) == len(obj.data.vertices) and masks['head'].any():
            top = float(positions[masks['head']][:, 2].max())
            head_top = top if head_top is None else max(head_top, top)

    items = []
    for obj in mesh_objs:
        masks = vg_data[obj]
        loops_vertex, loop_start, loop_total = get_mesh_loops(obj.data)
        positions = world.get(obj)
        vertex_count = len(obj.data.vertices)
        # 顶点数与世界坐标对不上时放弃高度过滤，只按顶点组划分
        world_z = positions[:, 2] if positions is not None and len(positions) == vertex_count else None
        item = {'obj': obj, 'count': vertex_count, 'head_mask': masks['head']}
        parts = [('hand_l', masks['l']), ('hand_r', masks['r'])]
        if need_body:
            # 求手臂的最大不穿模角度时才需要身体参与检测
            parts.append(('body', masks['body']))
        for key, mask in parts:
            # 先筛出该部位的面，再压缩成局部顶点索引，供后续建 BVH
            face_mask = select_faces(loops_vertex, loop_start, loop_total, mask, world_z, head_top)
            part = compact_faces(loops_vertex, loop_start, loop_total, face_mask)
            item[key] = part if part is not None else {'verts': np.zeros(0, dtype=np.int64), 'faces': []}
        items.append(item)
    return items


def build_item_bvhs(items, key, world):
    bvhs = []
    for item in items:
        part = item[key]
        positions = world.get(item['obj'])
        if not part['faces'] or positions is None or len(positions) != item['count']:
            continue
        vertices = positions[part['verts']].tolist()
        bvhs.append(BVHTree.FromPolygons(vertices, part['faces'], all_triangles=False))
    return bvhs


def has_collision(hand_bvhs, body_bvhs):
    for hand_bvh in hand_bvhs:
        for body_bvh in body_bvhs:
            if hand_bvh.overlap(body_bvh):
                return True
    return False


def evaluate_hand_world(items, side):
    """只评估包含手部面的网格，减少顶点读取开销"""
    objects = [item['obj'] for item in items if item[f'hand_{side}']['faces']]
    return evaluate_world_vertices(objects)


def get_hand_center(items, side, world):
    """手部中心点：把手部所有面用到的顶点世界坐标取平均

    items：build_arm_collision_data 的结果
    side ：'l' 或 'r'
    world：{网格: (n, 3) 世界坐标}，没有手部面或顶点数对不上时跳过该网格
    返回 mathutils.Vector；完全没有手部几何时返回 None
    """
    arrays = []
    for item in items:
        part = item[f'hand_{side}']
        positions = world.get(item['obj'])
        if not part['faces'] or positions is None or len(positions) != item['count']:
            continue
        # part['verts'] 是手部用到的顶点全局下标，直接取出它们的坐标
        arrays.append(positions[part['verts']])
    if not arrays:
        return None
    points = np.concatenate(arrays)
    # 先把各网格的点拼起来再求质心，避免顶点少的网格被放大权重
    return mathutils.Vector((
        float(points[:, 0].mean()), float(points[:, 1].mean()), float(points[:, 2].mean())))


def get_bone_world_direction(armature, bone_name):
    """腕骨骼 head → tail 的世界方向向量；骨骼不存在或长度过短时返回 None"""
    pose_bone = armature.pose.bones.get(bone_name)
    if pose_bone is None:
        return None
    direction = (armature.matrix_world @ pose_bone.tail
                 - armature.matrix_world @ pose_bone.head)
    return direction if direction.length > 1e-6 else None


def get_bone_side(bone_name, direction):
    """
    判断骨骼属于哪一侧手臂：'l' 或 'r'

    顶点组按名称后缀 .L/.R 划分为左右手，所以骨骼也优先按后缀判断，保证两边一致；
    没有后缀时退回按朝向判断：head → tail 在 XZ 平面指向 +X 侧视为左臂。
    """
    if bone_name.endswith(".L"):
        return 'l'
    if bone_name.endswith(".R"):
        return 'r'
    if direction is not None and math.atan2(direction.x, direction.z) <= 0:
        return 'r'
    return 'l'


def apply_t_pose_arm_rotation(armature, arm_names):
    """
    把双臂绕世界 Y 轴旋转到水平，得到 T 字姿态

    直接看腕骨骼 head → tail 在 XZ 平面的投影与 X 轴的夹角，把它转成水平
    """
    applied = {}
    for bone_name in arm_names:
        pose_bone = armature.pose.bones.get(bone_name)
        if pose_bone is None:
            continue
        # 旋转前的世界矩阵：作为旋转支点
        base_world = armature.matrix_world @ pose_bone.matrix
        direction = get_bone_world_direction(armature, bone_name)
        if direction is None:
            continue
        # 当前方向角（XZ 平面投影）；水平目标：朝 +X 是 0，朝 -X 是 π
        current = math.atan2(direction.z, direction.x)
        target = 0.0 if direction.x >= 0 else math.pi
        delta = current - target
        # 归一化到 (-π, π]，避免绕远路旋转
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta < -math.pi:
            delta += 2 * math.pi
        # 已接近水平，无需旋转
        if abs(math.degrees(delta)) < 0.05:
            continue
        rotate_arm_bone(armature, bone_name, math.degrees(abs(delta)), 1 if delta > 0 else -1, base_world)
        applied[bone_name] = round(math.degrees(abs(delta)), 1)
    bpy.context.view_layer.update()
    return applied


def compute_auto_arm_angle(armature, bone_name, items, side, sign, body_bvhs):
    """
    先按 ARM_ANGLE_STEP 步进找到穿模角度，再以 1° 为粒度二分，返回不穿模的最大角度

    返回 0 表示任何角度都会穿模（或没有可检测的手部几何）。
    """
    # 没有手部几何时无法判断穿模，保持静置
    if not any(item[f'hand_{side}']['faces'] for item in items):
        return 0

    pose_bone = armature.pose.bones[bone_name]
    base_matrix = pose_bone.matrix_basis.copy()
    base_world = armature.matrix_world @ pose_bone.matrix

    def collides(angle):
        """把手臂转到 angle 度，检测手部与身体是否相交"""
        rotate_arm_bone(armature, bone_name, angle, sign, base_world)
        bpy.context.view_layer.update()
        hand_bvhs = build_item_bvhs(items, f'hand_{side}', evaluate_hand_world(items, side))
        return has_collision(hand_bvhs, body_bvhs)

    # 粗搜索：按 ARM_ANGLE_STEP 递增，记录最后一个不穿模的角度
    last_good = 0
    for angle in range(ARM_ANGLE_STEP, ARM_ANGLE_LIMIT + 1, ARM_ANGLE_STEP):
        if not collides(angle):
            last_good = angle
            continue
        # 首个穿模角度落在 (last_good, angle] 区间内，二分到 1° 精度
        low, high = last_good, angle
        while high - low > 1:
            middle = (low + high) // 2
            if collides(middle):
                high = middle
            else:
                low = middle
        last_good = low
        break
    # 恢复试算造成的姿态变化
    pose_bone.matrix_basis = base_matrix
    bpy.context.view_layer.update()
    return last_good


def apply_auto_arm_rotation(armature, items, body_bvhs, arm_names):
    """自动计算不穿模的最大内旋角度并旋转双臂"""
    # 旋转前的世界矩阵，作为每个骨骼的旋转支点与初始朝向
    base_world = {
        name: armature.matrix_world @ armature.pose.bones[name].matrix for name in arm_names
        if name in armature.pose.bones
    }

    applied = {}
    for bone_name in arm_names:
        if bone_name not in armature.pose.bones:
            continue
        # 内旋方向：head → tail 在 XZ 平面的投影与 +Z 轴夹角为正说明在 +X 侧（左臂），绕 Y 轴正转
        direction = get_bone_world_direction(armature, bone_name)
        sign = 1 if direction is None or math.atan2(direction.x, direction.z) > 0 else -1
        # 左右不能按填写顺序推断，否则先右后左或只填一侧时会与手部几何错配
        side = get_bone_side(bone_name, direction)
        angle = compute_auto_arm_angle(armature, bone_name, items, side, sign, body_bvhs)
        if angle > 0:
            rotate_arm_bone(armature, bone_name, angle, sign, base_world[bone_name])
        else:
            # 任何角度都会穿模时保持静置
            armature.pose.bones[bone_name].matrix_basis = mathutils.Matrix.Identity(4)
        bpy.context.view_layer.update()
        applied[bone_name] = angle
    return applied


def apply_arm_rotation(armature, meshes, angle_setting, arm_names, world_vertices=None, vg_data=None,
                       auto_enabled=True):
    """按参数旋转双臂；返回实际旋转角度"""
    arm_bone_names = [name for name in arm_names if name in armature.pose.bones]
    # 未找到腕骨骼，跳过手臂旋转。（后续统一整合提示）
    if not arm_bone_names:
        return {}

    # 静置姿态（因为一开始全部骨骼都复位了，所以不用 KEEP 而是 REST）
    if angle_setting == 'REST':
        return {name: 0 for name in arm_bone_names}

    # 旋转手臂直至 T-pose
    if angle_setting == 'T_POSE':
        applied = apply_t_pose_arm_rotation(armature, arm_names)
        return applied or {name: 0 for name in arm_bone_names}

    # 缺少小臂骨骼时无法做穿模检测，自动姿态退化为不旋转
    if not auto_enabled:
        return {name: 0 for name in arm_bone_names}

    if world_vertices is None:
        world_vertices = evaluate_world_vertices(meshes)

    # 旋转手臂 直至再旋转会使手臂与身体发生穿模
    items = build_arm_collision_data(meshes, world_vertices, vg_data, True)
    body_bvhs = build_item_bvhs(items, 'body', world_vertices)
    return apply_auto_arm_rotation(armature, items, body_bvhs, arm_names)


def get_evaluated_vertex_group_mask(obj, names):
    """
    在评估后的网格上重新读取顶点组掩码

    生成类修改器（镜像、细分、布尔等）会改变顶点数量与顺序，原始网格的掩码无法直接使用；
    评估后的网格仍然保留顶点组权重，按同样的组名重新生成掩码即可（细分会插值权重）。
    这里用 to_mesh 取一份独立的临时网格：直接对 depsgraph 的评估结果建 bmesh 会偶发崩溃。
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        count = len(mesh.vertices)
        mask = np.zeros(count, dtype=bool)
        indexes = {vertex_group.index for vertex_group in obj.vertex_groups if vertex_group.name in names}
        if count == 0 or not indexes:
            return mask
        bm = bmesh.new()
        bm.from_mesh(mesh)
        deform = bm.verts.layers.deform.active
        if deform is not None:
            for vert in bm.verts:
                for index, weight in vert[deform].items():
                    if weight > 0 and index in indexes:
                        mask[vert.index] = True
                        break
        bm.free()
        return mask
    finally:
        eval_obj.to_mesh_clear()


def symmetric_head_span(min_x, max_x):
    """
    头部包围盒左右不对称时，改用较短一侧的宽度作为左右边界

    单侧头饰会把包围盒撑向一边，直接取中点会让特写偏离面部中心；
    左右宽度差超过头部宽度的 THREE_VIEW_HEAD_SYMMETRY_TOLERANCE 时按短侧对称。
    """
    width = max_x - min_x
    left = abs(min_x)
    right = abs(max_x)
    if width <= 0 or abs(left - right) <= width * THREE_VIEW_HEAD_SYMMETRY_TOLERANCE:
        return min_x, max_x
    short = min(left, right)
    return -short, short


def limit_head_span_by_eye(min_x, max_x, eye_bounds, range_ratio=None):
    """头部横向范围超过眼部网格的 range_ratio 倍时，按眼部范围收缩

    两侧的头发、发饰会把头部包围盒撑得很宽，取中点会让特写偏离面部；
    眼部网格最贴近面部，用它的横向范围作为参照，收缩后以原点为对称中心。
    """
    if not eye_bounds:
        return min_x, max_x
    ratio = THREE_VIEW_HEAD_EYE_RANGE_RATIO if range_ratio is None else range_ratio
    eye_left = abs(eye_bounds[0])
    eye_right = abs(eye_bounds[1])
    # 取眼部较外侧的一侧计算边界：部分模型只有单眼有权重，用较短一侧会把眼睛裁到画面外
    limit = max(eye_left, eye_right) * ratio
    if limit <= 0:
        return min_x, max_x
    if -min_x > eye_left * ratio or max_x > eye_right * ratio:
        return -limit, limit
    return min_x, max_x


def get_eye_bounds(meshes, world, eye_masks, eye_names=None):
    """用眼部顶点组中权重大于 0 的顶点计算包围盒 (min_x, max_x, min_z, max_z)"""
    arrays = []
    for obj in meshes:
        positions = world.get(obj)
        if positions is None:
            continue
        mask = eye_masks.get(obj) if eye_masks else None
        # 顶点数对不上：说明存在改变网格的修改器，改在评估后的网格上重新取眼部顶点组
        if eye_names and (mask is None or len(mask) != len(positions)):
            mask = get_evaluated_vertex_group_mask(obj, eye_names)
        if mask is None or len(mask) != len(positions) or not mask.any():
            continue
        arrays.append(positions[mask])
    if not arrays:
        return None
    return points_bounds(np.concatenate(arrays))


def get_eye_group_names(armature, eye_names):
    """眼部顶点组名称：填写名称对应的骨骼及其全部子孙骨骼"""
    names = list(eye_names)
    if armature is None:
        return names
    for name in eye_names:
        bone = armature.data.bones.get(name)
        if bone is None:
            continue
        stack = list(bone.children)
        while stack:
            child = stack.pop()
            names.append(child.name)
            stack.extend(child.children)
    return names


def get_eye_bone_bounds(armature, eye_names):
    """
    眼部顶点组没有权重时，用眼部骨骼位置估算眼部范围

    眼部骨骼的头部位于眼球中心，按固定倍数外扩得到眼部范围，
    让眼睛是贴图、没有权重的模型也能按面部取景，而不是按整头宽度取景。
    """
    if armature is None:
        return None
    xs = []
    zs = []
    for name in eye_names:
        bone = armature.pose.bones.get(name)
        if bone is None:
            continue
        position = armature.matrix_world @ bone.head
        xs.append(position.x)
        zs.append(position.z)
    if not xs:
        return None
    extent = max(abs(x) for x in xs) * THREE_VIEW_EYE_BONE_RANGE_RATIO
    return -extent, extent, 0.0, 0.0, min(zs), max(zs)


def get_eye_anchor_z(armature, eye_names, eye_bounds, head_bounds=None):
    """特写垂直锚点（眼睛高度）：优先用眼部网格中心，没有权重时用眼部骨骼位置"""
    if eye_bounds:
        return (eye_bounds[4] + eye_bounds[5]) / 2
    if armature is None:
        return None
    heights = []
    for name in eye_names:
        bone = armature.pose.bones.get(name)
        if bone is not None:
            heights.append((armature.matrix_world @ bone.head).z)
    if not heights:
        return None
    anchor = sum(heights) / len(heights)
    # 骨骼错位时锚点会落在头部之外，此时不做眼部锚定
    if head_bounds is not None and not head_bounds[2] <= anchor <= head_bounds[3]:
        return None
    return anchor


def get_head_bounds(meshes, world, head_masks, head_names=None, eye_bounds=None,
                    eye_range_ratio=None):
    """用「頭」顶点组中权重大于 0 的顶点计算头部包围盒（含姿态）"""
    arrays = []
    for obj in meshes:
        mask = head_masks.get(obj)
        positions = world.get(obj)
        if positions is None:
            continue
        # 顶点数对不上：说明存在改变网格的修改器，改在评估后的网格上重新取头部顶点组
        if head_names and (mask is None or len(mask) != len(positions)):
            mask = get_evaluated_vertex_group_mask(obj, head_names)
        if mask is None or len(mask) != len(positions) or not mask.any():
            continue
        arrays.append(positions[mask])
    if not arrays:
        return None
    # 头部只需要横向与纵向包围盒
    min_x, max_x, _, _, min_z, max_z = points_bounds(np.concatenate(arrays))
    # 横向明显宽于眼部网格时按眼部范围收缩，再做左右不对称修正
    min_x, max_x = limit_head_span_by_eye(min_x, max_x, eye_bounds, eye_range_ratio)
    min_x, max_x = symmetric_head_span(min_x, max_x)
    return min_x, max_x, min_z, max_z


def get_rotated_bounds(bounds, angle_degrees):
    """把包围盒绕世界 Z 轴旋转后重新求包围盒"""
    min_x, max_x, min_y, max_y, min_z, max_z = bounds
    corners = [(x, y, z) for x in (min_x, max_x) for y in (min_y, max_y) for z in (min_z, max_z)]
    rotation = mathutils.Matrix.Rotation(math.radians(angle_degrees), 3, 'Z')
    points = [rotation @ mathutils.Vector(corner) for corner in corners]
    return (
        min(point.x for point in points), max(point.x for point in points),
        min(point.y for point in points), max(point.y for point in points),
        min(point.z for point in points), max(point.z for point in points),
    )


def collect_model_armatures(meshes):
    armatures = set()
    for mesh in meshes:
        for modifier in mesh.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object is not None:
                armatures.add(modifier.object)
        node = mesh.parent
        while node is not None:
            if node.type == 'ARMATURE':
                armatures.add(node)
                break
            node = node.parent
    return armatures


def truncate_name(name, max_bytes):
    """按字节截断名称，且不切断 UTF-8 字符"""
    encoded = name.encode('utf-8')
    if len(encoded) <= max_bytes:
        return name
    return encoded[:max_bytes].decode('utf-8', errors='ignore')


def make_copy_name(name, label):
    """
    生成副本对象名：“原名称 + 视图 + 副本”，如“Rio 侧视图副本”

    同一角色内重名时再追加 .001、.002……；
    名称过长（Blender 对象名上限 63 字节）时只截断原名称部分，
    保证“ XXX副本”和“.001”这类后缀始终完整显示。
    """
    number = 1
    while True:
        # 第一个不加编号，重名时依次追加 .001、.002……
        tail = "" if number == 1 else f".{number - 1:03d}"
        suffix = " " + label + tail
        reserved = len(suffix.encode('utf-8'))
        candidate = truncate_name(name, OBJECT_NAME_MAX_BYTES - reserved) + suffix
        if bpy.data.objects.get(candidate) is None:
            return candidate
        number += 1


def duplicate_model_objects(mesh_objs, matrix, collection, source_root_name, label, root=None):
    """
    复制模型层级（最外层对象 / 骨架 / 网格），用于生成侧视图、后视图与特写

    root 是模型最外层的对象，不限定类型：MMD 模型通常是空物体，其它模型可能是骨架或网格。
    root 副本承载整体变换，其下的物体只需重新挂到副本下并保留局部变换。

    obj.copy() 只复制对象，mesh 与 armature 数据仍是共享的，共用数据既省内存也省时间。
    """
    mesh_objs = list(mesh_objs)
    armature_map = {}
    copies = []

    # 最外层对象副本承载整体变换
    root_copy = None
    if root is not None:
        root_copy = root.copy()
        root_copy.name = make_copy_name(root.name, label)
        root_copy.parent = None
        root_copy.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        root_copy.matrix_world = matrix @ root.matrix_world
        show_object(root_copy)
        collection.objects.link(root_copy)
        mark_temp_object(root_copy, source_root_name)
        copies.append(root_copy)
        if root_copy.type == 'ARMATURE':
            # 最外层就是骨架时，隐藏视口显示避免骨架线遮挡，并登记到映射表供网格绑定修改器
            root_copy.hide_set(True)
            armature_map[root] = root_copy

    # 骨架：视口隐藏（避免遮挡模型）
    for armature in collect_model_armatures(mesh_objs):
        if armature in armature_map:
            continue
        copy = armature.copy()
        copy.name = make_copy_name(armature.name, label)
        if root_copy is not None and armature.parent is root:
            # 原本直接挂在 root 下：保持局部变换，整体变换已由 root 副本承担
            copy.parent = root_copy
            copy.matrix_parent_inverse = armature.matrix_parent_inverse.copy()
            copy.matrix_basis = armature.matrix_basis.copy()
        else:
            # 不挂在 root 下：断开父级，直接把整体变换写到世界矩阵
            copy.parent = None
            copy.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            copy.matrix_world = matrix @ armature.matrix_world
        collection.objects.link(copy)
        copy.hide_set(True)
        copy.hide_render = True
        mark_temp_object(copy, source_root_name)
        armature_map[armature] = copy
        copies.append(copy)

    for mesh in mesh_objs:
        # 最外层对象就是网格时，它已经作为 root 副本复制过
        if mesh is root:
            continue
        copy = mesh.copy()
        copy.name = make_copy_name(mesh.name, label)
        # 网格通过骨架修改器关联骨架，复制后要把修改器重新指向复制出的骨架
        parent_armature = None
        for modifier in mesh.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object in armature_map:
                parent_armature = armature_map[modifier.object]
                break
        if parent_armature is not None and mesh.parent is not None:
            # 原本绑在骨架上：挂到副本骨架下并保持局部变换
            copy.parent = parent_armature
            copy.matrix_parent_inverse = mesh.matrix_parent_inverse.copy()
            copy.matrix_basis = mesh.matrix_basis.copy()
        else:
            # 没有骨架或原本无父级：断开父级，整体变换直接写进世界矩阵
            copy.parent = None
            copy.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            copy.matrix_world = matrix @ mesh.matrix_world
        collection.objects.link(copy)
        show_object(copy)
        mark_temp_object(copy, source_root_name)
        copies.append(copy)

    # 所有副本的骨架修改器统一指向副本骨架（含最外层本身是网格/骨架的情况）
    for copy in copies:
        for modifier in copy.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object in armature_map:
                modifier.object = armature_map[modifier.object]
    return copies


def create_clip_cube(collection, location, dimensions, source_root_name):
    """创建用于特写裁剪的透明正方体；尺寸直接烘进网格，避免缩放未提交导致布尔失效"""
    mesh = bpy.data.meshes.new(THREE_VIEW_CLIP_CUBE_NAME)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=mathutils.Vector(dimensions), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    cube = bpy.data.objects.new(THREE_VIEW_CLIP_CUBE_NAME, mesh)
    collection.objects.link(cube)
    cube.location = location
    cube.hide_render = True
    cube.hide_set(True)
    cube.display_type = 'WIRE'
    mark_temp_object(cube, source_root_name)
    return cube


def place_layout_camera(camera, frame_width, center_z, min_y, max_y):
    camera.data.type = 'ORTHO'
    camera.data.sensor_fit = 'HORIZONTAL'
    camera.data.ortho_scale = frame_width
    camera.rotation_mode = 'XYZ'
    camera.rotation_euler = (math.radians(90), 0.0, 0.0)
    depth = max(max_y - min_y, 0.001)
    distance = depth + THREE_VIEW_CAMERA_DISTANCE_MARGIN
    camera.location = (0.0, min_y - distance, center_z)
    camera.data.clip_start = 0.01
    camera.data.clip_end = distance + depth + THREE_VIEW_CAMERA_CLIP_MARGIN


def get_layout_bounds(world_vertices, visible_masks, head_bounds, report, warnings):
    """
    计算布局所需的尺寸数据，数据不可用时返回 None

    返回 (full_bounds, model_bounds, head_bounds, model_height, head_height)：
    - full_bounds ：全部顶点的包围盒，含透明隐藏部位（特写裁剪的 Y 向深度用它）
    - model_bounds ：可见顶点的包围盒，用于居中与统一缩放；可见点为空时退回完整包围盒
    - head_bounds ：头部包围盒，没有「頭」顶点组时按模型高度估算，警告写入 warnings，
      由调用方在执行结束时统一输出
    - model_height / head_height：角色与头部的高度，用于计算画面尺寸与校验
    """
    full_bounds = bounds_from_vertices(world_vertices)
    model_bounds = bounds_from_vertices(visible_world_vertices(world_vertices, visible_masks)) or full_bounds
    if model_bounds is None:
        report({'ERROR'}, translate("未找到可渲染的网格。"))
        return None

    if head_bounds is None:
        # 没有「頭」顶点组：取可见包围盒顶部的固定比例作为头部区域
        min_x, max_x, _, _, min_z, max_z = model_bounds
        height = max_z - min_z
        head_bounds = ((min_x + max_x) / 2, (min_x + max_x) / 2,
                       max_z - height * THREE_VIEW_HEAD_FALLBACK_RATIO, max_z)
        warnings.append(translate("未找到头部顶点组，已按模型高度估算头部区域。"))

    model_height = model_bounds[5] - model_bounds[4]
    head_height = head_bounds[3] - head_bounds[2]
    # 高度非正说明包围盒退化，无法计算布局
    if model_height <= 0 or head_height <= 0:
        report({'ERROR'}, translate("未找到可渲染的网格。"))
        return None
    return full_bounds, model_bounds, head_bounds, model_height, head_height


def build_three_view_setup(props, report, ancestor):
    """创建三视图布局"""
    # 记录执行前选中的临时对象；临时对象会在下面被删除重建，结束时按名字恢复选中
    temp_names = capture_temp_selection()
    scene = bpy.context.scene

    # 1. 清理上次执行产生的临时对象与手臂姿态；root 归零，避免重复执行累积缩放/位移
    #    reset_root_transform 会更新依赖图，所以复位姿态时不单独更新，省一次全场景求值
    cleanup_three_view_collection()
    reset_poses(ancestor, update=False)
    reset_root_transform(ancestor)

    # 2. 获取参与渲染的网格
    mesh_objs = get_renderable_meshes(ancestor)

    # 3. 获取可见顶点掩码：False 时使用全部顶点
    #    warnings 收集过程中的警告，等执行结束再统一输出
    warnings = []
    armature = get_armature(ancestor)
    world_vertices = evaluate_world_vertices(mesh_objs)
    if props.visible_only:
        # 只对含透明材质的网格做过滤；改变网格的修改器只影响它自己的那个网格
        visible_masks = build_visible_masks(mesh_objs, world_vertices, warnings)
    else:
        visible_masks = {obj: np.ones(len(obj.data.vertices), dtype=bool) for obj in mesh_objs}

    # 4. 获取顶点组数据与头部包围盒（名称取自面板的进阶参数）
    upper_arm_bones = existing_bone_names(armature, split_names(props.upper_arm_names))
    forearm_bones = existing_bone_names(armature, split_names(props.forearm_names))
    if not upper_arm_bones:
        warnings.append(translate("未找到大臂骨骼，已跳过手臂姿态调整。"))
    elif not forearm_bones:
        warnings.append(translate("未找到小臂骨骼，已跳过手臂姿态自动调整。"))
    collision_names, excluded_names, collision_chains = collect_arm_bone_names(
        armature, upper_arm_bones, forearm_bones)
    head_names = split_names(props.head_vg_names)
    eye_names = split_names(props.eye_vg_names)
    # 眼部按「目」及其全部子孙骨骼的顶点组统计
    eye_group_names = get_eye_group_names(armature, eye_names)
    vg_data = collect_vertex_vg_data(mesh_objs, collision_names, excluded_names, head_names,
                                     visible_masks, collision_chains, eye_group_names)
    head_masks = collect_head_masks(vg_data)
    head_bounds = get_head_bounds(mesh_objs, world_vertices, head_masks, head_names)
    eye_bounds = get_eye_bounds(mesh_objs, world_vertices, collect_eye_masks(vg_data),
                                eye_group_names)
    if eye_bounds is None:
        # 眼睛是贴图、没有权重时改用眼部骨骼估算，避免按整头宽度取景导致脸太小；
        # 个别模型眼部骨骼错位（高度远在头部之外），此时视为无效，退回按头部取景
        bone_bounds = get_eye_bone_bounds(armature, eye_names)
        if bone_bounds and head_bounds and head_bounds[2] <= bone_bounds[4] <= head_bounds[3]:
            eye_bounds = bone_bounds
    if eye_bounds is not None:
        # 面部宽度比例以 1 为基准：调大时眼部范围收窄、裁掉更多两侧头发
        eye_range_ratio = THREE_VIEW_HEAD_EYE_RANGE_RATIO / max(props.closeup_face_width_ratio, 1e-4)
        head_bounds = get_head_bounds(mesh_objs, world_vertices, head_masks, head_names, eye_bounds,
                                      eye_range_ratio)

    # 4.1 自动姿态依赖穿模检测用的顶点组（小臂及其子孙）；某侧没有这些顶点组时该侧保持静置，并提示原因
    if props.arm_angle == 'AUTO' and forearm_bones:
        collision_sides = {side: any(masks[side].any() for masks in vg_data.values())
                           for side in ('l', 'r')}
        for bone_name in upper_arm_bones:
            side = get_bone_side(bone_name, get_bone_world_direction(armature, bone_name))
            if not collision_sides[side]:
                warnings.append(translate("未找到“{}”的手部顶点组，已保持静置。").format(bone_name))

    # 5. 旋转手臂，然后重新评估顶点，得到最终包围盒；没有大臂骨骼时整体跳过
    if upper_arm_bones:
        arm_angles = apply_arm_rotation(armature, mesh_objs, props.arm_angle, upper_arm_bones,
                                        world_vertices, vg_data,
                                        auto_enabled=bool(forearm_bones)) or {}
    else:
        arm_angles = {}
    bpy.context.view_layer.update()
    if any(angle > 0 for angle in arm_angles.values()):
        world_vertices = evaluate_world_vertices(mesh_objs)

    # 5.1 统计完整/可见包围盒与头部包围盒，缺头部顶点组时按模型高度估算
    bounds = get_layout_bounds(world_vertices, visible_masks, head_bounds, report, warnings)
    if bounds is None:
        return None
    full_bounds, model_bounds, head_bounds, model_height, head_height = bounds
    min_x, max_x, min_y, max_y, min_z, max_z = model_bounds

    # 6. 画面尺寸：角色高度占画面高度的 height_margin（留白一些距离）；
    #    特写占左侧 closeup_scale 宽度，剩余宽度三等分给主视图/侧视图/后视图
    resolution_x = scene.render.resolution_x
    resolution_y = scene.render.resolution_y
    resolution_percentage = scene.render.resolution_percentage
    total_width = max(4, round(resolution_x * resolution_percentage / 100))
    total_height = max(1, round(resolution_y * resolution_percentage / 100))

    frame_height = model_height / props.height_margin
    # 正交相机在投影方向上是线性映射：1 个世界单位对应固定像素数。
    # 要让横纵比例一致，必须让 frame_width / frame_height = total_width / total_height （像素比）
    frame_width = frame_height * total_width / total_height
    frame_half_width = frame_width / 2
    closeup_world = frame_width * props.closeup_scale
    show_closeup = props.closeup_scale > 0.0
    show_views = props.closeup_scale < 1.0
    remaining_world = frame_width - closeup_world
    column_world = remaining_world / 3 if show_views else 0.0

    # 7. 三视图统一缩放：取宽/高约束下最小比例，保证三视图高度一致
    side_angle = math.degrees(props.side_view_angle)
    rotated_bounds = [get_rotated_bounds(model_bounds, angle) for angle in (0, side_angle, 180)]
    view_scale = 1.0
    if show_views:
        for bounds in rotated_bounds:
            width = bounds[1] - bounds[0]
            height = bounds[5] - bounds[4]
            # 缩放后的尺寸不能超过可用尺寸，求 scale，width 为包围盒（实际）宽度，column_world * width_margin 为可用宽度
            # scale * width <= column_world * width_margin
            # height 同理
            # 注意 column_world 与 width 同语义，而非像素
            scale = min(column_world * props.width_margin / width,
                        frame_height * props.width_margin / height, 1.0)
            view_scale = min(view_scale, scale)

    # 8. 横向居中用分位中心（只统计可见顶点），避免稀疏部件（如薄光环、露出的一小截尾巴）把主体挤偏
    # 相机 rotation_euler = (90°, 0, 0)，本地 -Z 指向世界 +Y：画面横向 = 世界 X，纵向 = 世界 Z，
    # 因此“横向中心”就是模型中心在世界 X 上的坐标。
    # 侧视图/后视图是绕世界 Z 轴旋转的副本（见步骤 10 的 Rotation(angle, 'Z')），绕 Z 转 θ 时
    # x' = x·cosθ - y·sinθ，于是中心 (center_x, center_y) 旋转后落到横向 cosθ·center_x - sinθ·center_y：
    #   0°     ：center_x
    #   90°    ：-center_y
    #   180°   ：-center_x
    # 侧视图角度可配置，θ 取侧视图角度
    # 纵向 Z 不受绕 Z 旋转影响，三种视图共用 view_center_z
    visible_groups = [points for points in
                      visible_world_vertices(world_vertices, visible_masks).values()
                      if len(points)]
    if visible_groups:
        visible_points = np.concatenate(visible_groups)
        # 中心点 center_x, center_y 是相对世界原点的坐标，本身就可能是正数或负数。
        center_x = robust_center(visible_points[:, 0])
        center_y = robust_center(visible_points[:, 1])
    else:
        # 没有可见顶点（整模透明或顶点掩码对不上）时，退回可见包围盒中心
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

    def rotated_center_x(angle_degrees):
        """绕世界 Z 轴旋转后，模型中心落在画面横向上的位置"""
        radians = math.radians(angle_degrees)
        return math.cos(radians) * center_x - math.sin(radians) * center_y

    view_centers = {0: center_x, side_angle: rotated_center_x(side_angle), 180: rotated_center_x(180)}

    # 纵向：以可见包围盒底部对齐，画面中心按缩放后的高度居中
    view_center_z = min_z + view_scale * model_height / 2  # 模型缩放后的竖向中点
    frame_top = view_center_z + frame_height / 2  # 相机中心加半个画面高就是画面的上边界，给特写用

    # 9. 建立临时集合；已存在则复用，避免连带删除用户放进该集合的物体
    collection = get_collection(THREE_VIEW_COLLECTION_NAME)
    source_root_name = ancestor.name

    closeup_objects = []
    try:
        # 10. 侧视图与后视图使用共享数据副本，
        #     缩放/旋转/位移由复制出的 root 承载，只按 min_z 对齐、不做垂直居中
        if show_views:
            for index, angle in enumerate((side_angle, 180)):
                # 副本按视图角色命名：第一列是侧视图，第二列是后视图
                label = THREE_VIEW_SIDE_COPY_LABEL if index == 0 else THREE_VIEW_BACK_COPY_LABEL
                # 模型 x 位置 target_x = 左侧边界 + 特写宽度 + (index + 1.5) * 单模型可用宽度
                target_x = -frame_half_width + closeup_world + (index + 1.5) * column_world
                # 旋转/缩放后模型中心位于 view_centers[angle] * view_scale，平移量 = 目标列中心 - 该位置
                translate_x = target_x - view_centers[angle] * view_scale
                # 缩放与旋转都以世界原点为中心，模型底部会随之抬到 min_z * view_scale，补回差量对齐到 min_z
                translate_z = min_z * (1 - view_scale)
                # 矩阵左乘依次作用于顶点：先缩放（对齐三视图高度），再绕世界 Z 轴旋转（换视角），
                # 最后平移到目标列，所以写作 Translation @ Rotation @ Scale
                matrix = (
                    mathutils.Matrix.Translation((translate_x, 0.0, translate_z))
                    @ mathutils.Matrix.Rotation(math.radians(angle), 4, 'Z')
                    @ mathutils.Matrix.Scale(view_scale, 4))
                duplicate_model_objects(mesh_objs, matrix, collection, source_root_name, label, ancestor)

        # 11. 特写：以头部包围盒（上边取头部/子孙顶部，左右取 ±1.8 眼距）整体放大填满特写栏，
        #     包围盒上边贴合画面上边界
        closeup_scale = 1.0
        if show_closeup:
            head_center_x = (head_bounds[0] + head_bounds[1]) / 2
            head_width = head_bounds[1] - head_bounds[0]
            # 没有眼部数据时按「特写头部占比」缩放，头部过宽允许横向超出特写栏被裁
            closeup_scale = (frame_height * props.closeup_head_ratio) / head_height
            if head_width > 0 and eye_bounds:
                # 眼部范围已把横向边界收窄到面部，按包围盒宽度整体放大；
                # 高度可能超出画面，由上边贴合画面上边界来保证头顶完整
                closeup_scale = closeup_world * props.width_margin / head_width
            target_x = -frame_half_width + closeup_world / 2
            translate_x = target_x - head_center_x * closeup_scale
            eye_anchor_z = get_eye_anchor_z(armature, eye_names, eye_bounds, head_bounds)
            if eye_anchor_z is not None:
                # 眼部锚定：眼睛中心固定在画面高度的一定比例处（特写面部高度比例越大越靠上），
                # 角、发饰、发丝的位置自然
                eye_height_ratio = min(max(
                    THREE_VIEW_CLOSEUP_EYE_HEIGHT_RATIO
                    / max(props.closeup_face_height_ratio, 1e-4), 0.02), 1.0)
                translate_z = (frame_top - frame_height * eye_height_ratio
                               - eye_anchor_z * closeup_scale)
            else:
                translate_z = frame_top - head_bounds[3] * closeup_scale
            closeup_matrix = (
                mathutils.Matrix.Translation((translate_x, 0.0, translate_z))
                @ mathutils.Matrix.Scale(closeup_scale, 4))
            closeup_objects = duplicate_model_objects(
                mesh_objs, closeup_matrix, collection, source_root_name,
                THREE_VIEW_CLOSEUP_COPY_LABEL, ancestor)

        # 12. 原模型作为主视图缩放到第一列；仅特写模式则把原模型整体右移出相机视野
        if show_views:
            front_target_x = -frame_half_width + closeup_world + 0.5 * column_world
            front_translate_x = front_target_x - center_x * view_scale
            front_translate_z = min_z * (1 - view_scale)
            front_matrix = (
                mathutils.Matrix.Translation((front_translate_x, 0.0, front_translate_z))
                @ mathutils.Matrix.Scale(view_scale, 4))
            ancestor.matrix_world = front_matrix
        else:
            # 相机横向覆盖 [-frame_half_width, frame_half_width]，把模型左边缘推到右边界之外
            offscreen_gap = frame_width * THREE_VIEW_OFFSCREEN_GAP
            # 目标位置 − 当前左边缘L
            # L + shift_x = frame_half_width + offscreen_gap
            shift_x = frame_half_width + offscreen_gap - min(full_bounds[0], min_x)
            ancestor.matrix_world = mathutils.Matrix.Translation((shift_x, 0.0, 0.0))

        # 13. 特写裁剪：立方体 X 方向为列宽、Y 方向用完整包围盒并跟随特写缩放，
        #     每个特写网格都与立方体求交集，只保留列内部分
        if show_closeup and show_views:
            full_depth = full_bounds[3] - full_bounds[2]
            cube_center_y = (full_bounds[2] + full_bounds[3]) / 2 * closeup_scale
            cube_depth = max(full_depth * closeup_scale * THREE_VIEW_CLIP_DEPTH_MARGIN, 1.0)
            cube = create_clip_cube(
                collection,
                (-frame_half_width + closeup_world / 2, cube_center_y, view_center_z),
                (closeup_world, cube_depth, frame_height * 2),
                source_root_name)
            for obj in closeup_objects:
                if obj.type != 'MESH':
                    continue
                modifier = obj.modifiers.new(THREE_VIEW_CLIP_MODIFIER_NAME, 'BOOLEAN')
                modifier.operation = 'INTERSECT'
                # 快速解算：4.x 为 FAST，5.x 重命名为 FLOAT
                solvers = modifier.bl_rna.properties['solver'].enum_items.keys()
                modifier.solver = 'FAST' if 'FAST' in solvers else 'FLOAT'
                modifier.object = cube
            bpy.context.view_layer.update()
    except Exception:
        reset_three_view(ancestor)
        raise

    # 14. 布局相机：一张正交相机覆盖特写+三视图，景深按模型高度估算（特写副本可能放大）
    depth = model_height * max(2.0, closeup_scale)
    camera = gen_three_view_camera()
    place_layout_camera(camera, frame_width, view_center_z, -depth / 2, depth / 2)
    # 15. 恢复执行前的选中，避免下次执行提示“请选择对象”
    restore_temp_selection(temp_names, ancestor)
    return {'camera': camera, 'collection': collection, 'arm_angles': arm_angles,
            'warnings': warnings}


def preview_three_view(props, report, ancestor):
    setup = build_three_view_setup(props, report, ancestor)
    if setup is None:
        return None
    bpy.context.scene.camera = setup['camera']
    if not bpy.app.background:
        switch_to_camera_view()
    # 执行结束时统一输出警告（多条合并为一条），避免中途打断操作
    if setup['warnings']:
        report({'WARNING'}, "\n".join(setup['warnings']))
    return setup


def render_three_view(props, report, ancestor, output_filepath=None, cleanup=False):
    """预览布局后执行 F12 渲染"""
    scene = bpy.context.scene
    setup = build_three_view_setup(props, report, ancestor)
    if setup is None:
        return False
    original_camera = scene.camera
    original_filepath = scene.render.filepath
    try:
        scene.camera = setup['camera']
        if output_filepath is not None:
            scene.render.filepath = output_filepath.replace("{", "{{").replace("}", "}}")
            # 批量渲染必须写入文件，不弹出渲染窗口
            bpy.ops.render.render("EXEC_DEFAULT", write_still=True)
        else:
            show = not bpy.app.background
            bpy.ops.render.render("INVOKE_DEFAULT" if show else "EXEC_DEFAULT", write_still=not show)
            if show:
                bpy.ops.render.view_show()
        return True
    except (RuntimeError, ValueError, OSError) as exc:
        report({'ERROR'}, translate("三视图渲染失败：{}").format(exc))
        return False
    finally:
        scene.render.filepath = original_filepath
        if cleanup:
            reset_three_view()
            scene.camera = original_camera
        else:
            scene.camera = setup['camera']
        # 执行结束时统一输出警告（多条合并为一条），避免中途打断操作
        if setup['warnings']:
            report({'WARNING'}, "\n".join(setup['warnings']))

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
