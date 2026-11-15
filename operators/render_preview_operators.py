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
    ARM_BONE_NAMES,
    ARM_CHAIN_GROUP_NAMES,
    ARM_EXCLUDED_GROUP_NAMES,
    ARM_SIGN_TEST_ANGLE,
    BATCH_TASK_RENDER_PREVIEW,
    HAND_GROUP_NAMES,
    HEAD_GROUP_NAMES,
    IMG_TYPE_EXT_MAP,
    MATERIAL_ALPHA_EPSILON,
    THREE_VIEW_CAMERA_CLIP_MARGIN,
    THREE_VIEW_CAMERA_DISTANCE_MARGIN,
    THREE_VIEW_CAMERA_NAME,
    THREE_VIEW_CENTER_PERCENTILE,
    THREE_VIEW_CLIP_CUBE_NAME,
    THREE_VIEW_CLIP_DEPTH_MARGIN,
    THREE_VIEW_CLIP_MODIFIER_NAME,
    THREE_VIEW_CLOSEUP_HEAD_RATIO,
    THREE_VIEW_COLLECTION_NAME,
    THREE_VIEW_COLUMN_FIT,
    THREE_VIEW_FRAME_MARGIN,
    THREE_VIEW_HEAD_FALLBACK_RATIO,
    THREE_VIEW_OFFSCREEN_GAP,
    THREE_VIEW_TEMP_FLAG,
    THREE_VIEW_TEMP_SOURCE,
)

from ..utils import (
    check_batch_props,
    convertNameToLR,
    deselect_all_objects,
    find_ancestor,
    find_armature,
    find_children,
    find_pmx_armature,
    find_pmx_objects,
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
        if is_three_view(props):
            ancestor = self.check_three_view_props(props)
            # 校验失败直接返回
            if ancestor is None:
                return {'CANCELLED'}
            if not preview_three_view(props, self.report, ancestor):
                return {'CANCELLED'}
            return {'FINISHED'}

        if not self.check_props():
            return {'CANCELLED'}

        reset_three_view()
        if not self.check_props():
            return {'CANCELLED'}
        camera_to_view_selected(props)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_three_view_props(self, props):
        return check_three_view_props(props, self.report)

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

        if is_three_view(self.props):
            if not render_three_view(self.props, self.report, pmx_root,
                                     output_filepath=new_filepath, cleanup=True):
                raise RuntimeError(translate("三视图渲染失败"))
            return

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
        if is_three_view(props):
            ancestor = check_three_view_props(props, self.report)
            if ancestor is None:
                # 模型可能已被删除，清理残留的临时对象并恢复状态
                reset_three_view()
                return False
            return render_three_view(props, self.report, ancestor)
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
                self.report(type={'ERROR'}, message=f'Unsupported output format! Use image format instead.')
                return False
        else:
            objs = bpy.context.selected_objects
            if len(objs) == 0 and not is_three_view(props):
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
    reset_three_view()
    do_camera_to_view_selected(props.type,
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


def do_camera_to_view_selected(camera_type,
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


def is_three_view(props):
    return props.type == 'ORTHOGRAPHIC' and props.view == 'THREE_VIEW'


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


def check_three_view_props(props, report):
    """
    三视图参数校验：解析并返回要渲染的模型，校验失败返回 None

    必须选中模型才能执行；选中临时对象时，按临时对象记录的 root 名找回原模型。
    """
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


def reset_poses(ancestor=None):
    """把骨架姿态复位为静置姿态"""
    armature = get_armature(ancestor)
    if not armature:
        return

    identity = mathutils.Matrix.Identity(4)
    for pose_bone in armature.pose.bones:
        if pose_bone.matrix_basis != identity:
            pose_bone.matrix_basis = identity
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


def create_three_view_collection():
    """返回三视图临时集合；已存在则复用，避免连带删除用户放进该集合的物体"""
    collection = bpy.data.collections.get(THREE_VIEW_COLLECTION_NAME)
    if collection is not None:
        return collection
    collection = bpy.data.collections.new(THREE_VIEW_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(collection)
    return collection


def get_armature(ancestor=None):
    """获取模型骨架：当前激活对象是骨架时直接用，否则从 ancestor 向下查找"""
    active = bpy.context.view_layer.objects.active
    if active is not None and active.type == 'ARMATURE' and not active.get(THREE_VIEW_TEMP_FLAG):
        return active
    if ancestor is None:
        return None
    return find_armature(ancestor)


def find_bone_name(armature, japanese_name):
    converted = convertNameToLR(japanese_name)
    for name in (converted, japanese_name):
        if name in armature.pose.bones:
            return name
    return None


def expand_vg_names(names):
    names = set(names)
    for name in list(names):
        names.add(convertNameToLR(name))
    return names


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


def bounds_from_vertices(vertex_map):
    arrays = [vertices for vertices in vertex_map.values() if len(vertices)]
    if not arrays:
        return None
    points = np.concatenate(arrays)
    return (
        float(points[:, 0].min()), float(points[:, 0].max()),
        float(points[:, 1].min()), float(points[:, 1].max()),
        float(points[:, 2].min()), float(points[:, 2].max()),
    )


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
    loops_vertex = get_loop_vertices(mesh)
    loop_total = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_total', loop_total)
    # 把每个多边形重复其 loop 数，得到“第 i 个 loop 属于哪个面”的映射
    face_of_loop = np.repeat(np.arange(len(mesh.polygons)), loop_total)
    # 取可见面覆盖的全部 loop 指向的顶点，一次性标记为可见
    visible = np.zeros(count, dtype=bool)
    visible[loops_vertex[face_visible[face_of_loop]]] = True
    return visible


def collect_visible_masks(objs):
    """可见顶点掩码（{网格: bool 数组}）：True 表示该顶点属于可见面"""
    return {obj: get_visible_vertex_mask(obj) for obj in objs}


def robust_center(values):
    """分位中心：忽略两端的稀疏离群几何"""
    if len(values) == 0:
        return 0.0
    lower, upper = np.percentile(values, [THREE_VIEW_CENTER_PERCENTILE,
                                          100.0 - THREE_VIEW_CENTER_PERCENTILE])
    return float((lower + upper) / 2)


def visible_world_vertices(world, masks):
    result = {}
    for obj, vertices in world.items():
        mask = masks.get(obj)
        if mask is None or len(vertices) != len(mask):
            continue
        result[obj] = vertices[mask]
    return result


def get_vertex_masks(obj, left_names, right_names, excluded_names, head_names):
    """一次 bmesh 遍历，按顶点组生成左右手、身体与头部的顶点掩码"""
    mesh = obj.data
    count = len(mesh.vertices)
    masks = {key: np.zeros(count, dtype=bool) for key in ('l', 'r', 'body', 'head')}
    if count == 0:
        return masks
    vg_name_map = {vg.index: vg.name for vg in obj.vertex_groups}
    left_vg_indexes = {index for index, name in vg_name_map.items() if name in left_names}
    right_vg_indexes = {index for index, name in vg_name_map.items() if name in right_names}
    excluded_vg_indexes = {index for index, name in vg_name_map.items() if name in excluded_names}
    head_vg_indexes = {index for index, name in vg_name_map.items() if name in head_names}
    if not (left_vg_indexes or right_vg_indexes or head_vg_indexes):
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
    bm.free()
    return masks


def collect_head_masks(vg_data):
    return {obj: masks['head'] for obj, masks in vg_data.items()}

def get_mesh_loops(mesh):
    loops_vertex = get_loop_vertices(mesh)
    loop_start = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_start', loop_start)
    loop_total = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_total', loop_total)
    return loops_vertex, loop_start, loop_total


def select_faces(loops_vertex, loop_start, loop_total, vertex_mask, world_z, max_z):
    """选出所有顶点都属于指定顶点组、且不高于 max_z 的面"""
    if len(loop_total) == 0:
        return np.zeros(0, dtype=bool)
    face_hits = np.add.reduceat(vertex_mask[loops_vertex].astype(np.int32), loop_start)
    faces = face_hits == loop_total
    if max_z is not None and world_z is not None:
        above = np.add.reduceat((world_z[loops_vertex] > max_z).astype(np.int32), loop_start)
        faces &= above == 0
    return faces


def compact_faces(loops_vertex, loop_start, loop_total, face_mask):
    """把选中的面压缩为局部顶点索引，供 BVH 使用"""
    selected = np.nonzero(face_mask)[0]
    if len(selected) == 0:
        return None
    starts = loop_start[selected]
    totals = loop_total[selected]
    loop_count = int(totals.sum())
    offsets = np.repeat(starts, totals)
    offsets += np.arange(loop_count) - np.repeat(np.cumsum(totals) - totals, totals)
    vertex_indices = loops_vertex[offsets]
    unique, inverse = np.unique(vertex_indices, return_inverse=True)
    faces = [tuple(face.tolist()) for face in np.split(inverse.reshape(-1), np.cumsum(totals)[:-1])]
    return {'verts': unique, 'faces': faces}


def collect_vertex_vg_data(meshe_objs, visible_masks=None):
    """一次遍历得到手部/身体/头部顶点掩码，供手臂角度与头部尺寸共用"""
    hand_names = expand_vg_names(HAND_GROUP_NAMES)
    hand_left = expand_vg_names(name for name in HAND_GROUP_NAMES if '左' in name)
    hand_right = expand_vg_names(name for name in HAND_GROUP_NAMES if '右' in name)
    excluded = expand_vg_names(ARM_CHAIN_GROUP_NAMES) | ARM_EXCLUDED_GROUP_NAMES
    data = {
        obj: get_vertex_masks(obj, hand_left, hand_right, hand_names | excluded, HEAD_GROUP_NAMES)
        for obj in meshe_objs
    }
    for obj, masks in data.items():
        visible = visible_masks.get(obj) if visible_masks else None
        if visible is None:
            visible = get_visible_vertex_mask(obj)
        if not visible.all():
            for key in masks:
                masks[key] &= visible
    return data


def build_arm_collision_data(meshes, world, vg_data=None, need_body=True):
    """按顶点组把网格拆分为左右手部、身体与头部，用于穿模检测"""
    if vg_data is None:
        vg_data = collect_vertex_vg_data(meshes)

    head_top = None
    for obj in meshes:
        masks = vg_data[obj]
        positions = world.get(obj)
        if positions is not None and len(positions) == len(obj.data.vertices) and masks['head'].any():
            top = float(positions[masks['head']][:, 2].max())
            head_top = top if head_top is None else max(head_top, top)

    items = []
    for obj in meshes:
        masks = vg_data[obj]
        loops_vertex, loop_start, loop_total = get_mesh_loops(obj.data)
        positions = world.get(obj)
        vertex_count = len(obj.data.vertices)
        world_z = positions[:, 2] if positions is not None and len(positions) == vertex_count else None
        item = {'obj': obj, 'count': vertex_count, 'head_mask': masks['head']}
        parts = [('hand_l', masks['l']), ('hand_r', masks['r'])]
        if need_body:
            parts.append(('body', masks['body']))
        for key, mask in parts:
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


def get_hand_center_x(items, side, world):
    arrays = []
    for item in items:
        part = item[f'hand_{side}']
        positions = world.get(item['obj'])
        if not part['faces'] or positions is None or len(positions) != item['count']:
            continue
        arrays.append(positions[part['verts'], 0])
    if not arrays:
        return None
    return float(np.concatenate(arrays).mean())


def get_hand_center(items, side, world):
    arrays = []
    for item in items:
        part = item[f'hand_{side}']
        positions = world.get(item['obj'])
        if not part['faces'] or positions is None or len(positions) != item['count']:
            continue
        arrays.append(positions[part['verts']])
    if not arrays:
        return None
    points = np.concatenate(arrays)
    return mathutils.Vector((
        float(points[:, 0].mean()), float(points[:, 1].mean()), float(points[:, 2].mean())))


def apply_arm_t_pose(armature, items, world):
    """把双臂绕世界 Y 轴旋转到水平，得到 T 字姿态"""
    applied = {}
    for side, japanese_name in (('l', '左腕'), ('r', '右腕')):
        bone_name = find_bone_name(armature, japanese_name)
        if bone_name is None:
            continue
        pose_bone = armature.pose.bones[bone_name]
        base_world = armature.matrix_world @ pose_bone.matrix
        center = get_hand_center(items, side, world)
        if center is None:
            continue
        direction = center - base_world.translation
        if direction.length < 1e-6:
            continue
        current = math.atan2(direction.z, direction.x)
        target = 0.0 if direction.x >= 0 else math.pi
        delta = current - target
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta < -math.pi:
            delta += 2 * math.pi
        if abs(math.degrees(delta)) < 0.05:
            continue
        rotate_arm_bone(armature, bone_name, math.degrees(abs(delta)),
                        1 if delta > 0 else -1, base_world)
        applied[bone_name] = round(math.degrees(abs(delta)), 1)
    bpy.context.view_layer.update()
    return applied


def determine_inward_sign(armature, bone_name, items, side, body_center_x):
    pose_bone = armature.pose.bones[bone_name]
    base_matrix = pose_bone.matrix_basis.copy()
    base_world = armature.matrix_world @ pose_bone.matrix
    best_sign = 1
    best_distance = None
    for sign in (1, -1):
        rotate_arm_bone(armature, bone_name, ARM_SIGN_TEST_ANGLE, sign, base_world)
        bpy.context.view_layer.update()
        center_x = get_hand_center_x(items, side, evaluate_hand_world(items, side))
        distance = abs(center_x - body_center_x) if center_x is not None else None
        if distance is not None and (best_distance is None or distance < best_distance):
            best_distance = distance
            best_sign = sign
    pose_bone.matrix_basis = base_matrix
    bpy.context.view_layer.update()
    return best_sign


def compute_auto_arm_angle(armature, bone_name, items, side, sign, body_bvhs):
    """先按 ARM_ANGLE_STEP 步进找到穿模角度，再以 1° 为粒度二分，返回不穿模的最大角度"""
    pose_bone = armature.pose.bones[bone_name]
    base_matrix = pose_bone.matrix_basis.copy()
    base_world = armature.matrix_world @ pose_bone.matrix

    def collides(angle):
        rotate_arm_bone(armature, bone_name, angle, sign, base_world)
        bpy.context.view_layer.update()
        hand_bvhs = build_item_bvhs(items, f'hand_{side}', evaluate_hand_world(items, side))
        return has_collision(hand_bvhs, body_bvhs)

    last_good = 0
    for angle in range(ARM_ANGLE_STEP, ARM_ANGLE_LIMIT + 1, ARM_ANGLE_STEP):
        if not collides(angle):
            last_good = angle
            continue
        low, high = last_good, angle
        while high - low > 1:
            middle = (low + high) // 2
            if collides(middle):
                high = middle
            else:
                low = middle
        last_good = low
        break
    pose_bone.matrix_basis = base_matrix
    bpy.context.view_layer.update()
    return last_good


def apply_arm_rotation(armature, meshes, angle_setting, world_vertices=None, vg_data=None):
    """按参数旋转双臂；返回实际旋转角度"""
    bone_names = [name for name in (find_bone_name(armature, jp) for jp in ARM_BONE_NAMES) if name]
    if not bone_names:
        # 未找到腕骨骼，已跳过手臂旋转。（提示后续统一整合）
        return {}
    if angle_setting == '0':
        return {name: 0 for name in bone_names}

    if world_vertices is None:
        world_vertices = evaluate_world_vertices(meshes)
    if angle_setting == 'T_POSE':
        items = build_arm_collision_data(meshes, world_vertices, vg_data, False)
        applied = apply_arm_t_pose(armature, items, world_vertices)
        return applied or {name: 0 for name in bone_names}

    items = build_arm_collision_data(meshes, world_vertices, vg_data, angle_setting == 'AUTO')
    body_bvhs = build_item_bvhs(items, 'body', world_vertices) if angle_setting == 'AUTO' else []
    bounds = bounds_from_vertices(world_vertices)
    body_center_x = (bounds[0] + bounds[1]) / 2
    base_world = {
        name: armature.matrix_world @ armature.pose.bones[name].matrix for name in bone_names
    }

    applied = {}
    for side, japanese_name in (('l', '左腕'), ('r', '右腕')):
        bone_name = find_bone_name(armature, japanese_name)
        if bone_name is None:
            continue
        sign = determine_inward_sign(armature, bone_name, items, side, body_center_x)
        if angle_setting == 'AUTO':
            angle = compute_auto_arm_angle(armature, bone_name, items, side, sign, body_bvhs)
        else:
            angle = int(angle_setting)
        if angle > 0:
            rotate_arm_bone(armature, bone_name, angle, sign, base_world[bone_name])
        else:
            armature.pose.bones[bone_name].matrix_basis = mathutils.Matrix.Identity(4)
        bpy.context.view_layer.update()
        applied[bone_name] = angle
    return applied


def get_head_bounds(meshes, world, head_masks):
    """用「頭」顶点组中权重大于 0 的顶点计算头部包围盒（含姿态）"""
    arrays = []
    for obj in meshes:
        mask = head_masks.get(obj)
        positions = world.get(obj)
        if mask is None or positions is None or len(positions) != len(obj.data.vertices):
            continue
        if mask.any():
            arrays.append(positions[mask])
    if not arrays:
        return None
    # 把多个网格的顶点坐标合并成一个数组，例如
    # [
    #     [1, 2, 3],
    #     [2, 3, 4],
    #     [3, 4, 5],
    #     [4, 5, 6]
    # ]
    points = np.concatenate(arrays)
    # points[:, 0]，: 表示选取所有行，0 表示选取第 0 列。
    return (float(points[:, 0].min()), float(points[:, 0].max()),
            float(points[:, 2].min()), float(points[:, 2].max()))


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


def duplicate_model_objects(meshes, matrix, collection, source_root_name, root=None):
    """复制 root/骨架/网格（共享数据）；缩放旋转由复制出的 root 承载"""
    meshes = list(meshes)
    armature_map = {}
    copies = []

    root_copy = None
    if root is not None and root.type == 'EMPTY':
        root_copy = root.copy()
        root_copy.parent = None
        root_copy.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        root_copy.matrix_world = matrix @ root.matrix_world
        collection.objects.link(root_copy)
        mark_temp_object(root_copy, source_root_name)
        copies.append(root_copy)

    for armature in collect_model_armatures(meshes):
        copy = armature.copy()
        if root_copy is not None and armature.parent is root:
            copy.parent = root_copy
            copy.matrix_parent_inverse = armature.matrix_parent_inverse.copy()
            copy.matrix_basis = armature.matrix_basis.copy()
        else:
            copy.parent = None
            copy.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            copy.matrix_world = matrix @ armature.matrix_world
        copy.hide_render = False
        collection.objects.link(copy)
        copy.hide_set(True)
        mark_temp_object(copy, source_root_name)
        armature_map[armature] = copy
        copies.append(copy)

    for mesh in meshes:
        copy = mesh.copy()
        parent_armature = None
        for modifier in mesh.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object in armature_map:
                parent_armature = armature_map[modifier.object]
                break
        if parent_armature is not None and mesh.parent is not None:
            copy.parent = parent_armature
            copy.matrix_parent_inverse = mesh.matrix_parent_inverse.copy()
            copy.matrix_basis = mesh.matrix_basis.copy()
        else:
            copy.parent = None
            copy.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            copy.matrix_world = matrix @ mesh.matrix_world
        copy.hide_render = False
        collection.objects.link(copy)
        for modifier in copy.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object in armature_map:
                modifier.object = armature_map[modifier.object]
        mark_temp_object(copy, source_root_name)
        copies.append(copy)
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
    bpy.context.view_layer.update()
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


def build_three_view_setup(props, report, ancestor):
    """
    创建三视图布局。

    处理步骤：
    1. 清理上次的临时对象，手臂姿态恢复为静置，原模型 root 归零为恒等变换
    2. 收集 root 下参与渲染的网格
    3. 计算可见顶点掩码（「仅可见网格」决定是否忽略透明隐藏部位）
    4. 收集顶点组数据（左右手/身体/頭）与头部包围盒
    5. 应用手臂姿态，重新评估顶点，得到完整与可见包围盒
    6. 按输出分辨率计算画面尺寸、特写宽度与三视图列宽
    7. 计算三视图统一缩放，保证各视图高度一致
    8. 计算各视图的横向分位中心，避免稀疏部件把主体挤偏
    9. 建立临时集合
    10. 创建侧视图、后视图副本（缩放/旋转由复制出的 root 承载）
    11. 创建特写副本（头部占画面竖向比例、顶部对齐）
    12. 原模型缩放归位作为主视图；仅特写模式则把原模型整体右移出相机视野
    13. 用透明立方体布尔求交，裁掉特写超出列宽的部分
    14. 创建布局相机并记录到临时集合

    ancestor 由调用方（execute 中的 check_three_view_props）解析后传入。
    """
    scene = bpy.context.scene

    # 1. 清理上次执行产生的临时对象与手臂姿态；root 归零，避免重复执行累积缩放/位移
    cleanup_three_view_collection()
    reset_poses(ancestor)
    reset_root_transform(ancestor)

    # 2. 获取参与渲染的网格
    mesh_objs = get_renderable_meshes(ancestor)

    # 3. 获取可见顶点掩码：False 时使用全部顶点
    armature = get_armature(ancestor)
    world_vertices = evaluate_world_vertices(mesh_objs)
    if props.visible_only:
        visible_masks = collect_visible_masks(mesh_objs)
    else:
        visible_masks = {obj: np.ones(len(obj.data.vertices), dtype=bool) for obj in mesh_objs}

    # 4. 获取顶点组数据与头部包围盒
    vg_data = collect_vertex_vg_data(mesh_objs, visible_masks)
    head_bounds = get_head_bounds(mesh_objs, world_vertices, collect_head_masks(vg_data))

    # 5. 旋转手臂，然后重新评估顶点，得到最终包围盒
    arm_angles = apply_arm_rotation(armature, mesh_objs, props.arm_angle, world_vertices, vg_data) or {}
    bpy.context.view_layer.update()
    if any(angle > 0 for angle in arm_angles.values()):
        world_vertices = evaluate_world_vertices(mesh_objs)
    full_bounds = bounds_from_vertices(world_vertices)
    body_bounds = bounds_from_vertices(visible_world_vertices(world_vertices, visible_masks)) or full_bounds
    if body_bounds is None:
        report({'ERROR'}, translate("未找到可渲染的网格。"))
        return None
    if head_bounds is None:
        # 没有「頭」顶点组时，按模型高度估算头部区域
        min_x, max_x, _, _, min_z, max_z = body_bounds
        height = max_z - min_z
        head_bounds = ((min_x + max_x) / 2, (min_x + max_x) / 2,
                       max_z - height * THREE_VIEW_HEAD_FALLBACK_RATIO, max_z)
        report({'WARNING'}, translate("未找到「頭」顶点组，已按模型高度估算头部区域。"))

    min_x, max_x, min_y, max_y, min_z, max_z = body_bounds
    model_height = max_z - min_z
    head_height = head_bounds[3] - head_bounds[2]
    if model_height <= 0 or head_height <= 0:
        report({'ERROR'}, translate("未找到可渲染的网格。"))
        return None

    # 6. 画面尺寸：角色高度占画面高度的 THREE_VIEW_FRAME_MARGIN；
    #    特写占左侧 closeup_scale 宽度，剩余宽度三等分给主视图/侧视图/后视图
    resolution_x = scene.render.resolution_x
    resolution_y = scene.render.resolution_y
    resolution_percentage = scene.render.resolution_percentage
    total_width = max(4, round(resolution_x * resolution_percentage / 100))
    total_height = max(1, round(resolution_y * resolution_percentage / 100))

    frame_height = model_height / THREE_VIEW_FRAME_MARGIN
    frame_width = frame_height * total_width / total_height
    frame_half_width = frame_width / 2
    closeup_world = frame_width * props.closeup_scale
    show_closeup = props.closeup_scale > 0.0
    show_views = props.closeup_scale < 1.0
    remaining_world = frame_width - closeup_world
    column_world = remaining_world / 3 if show_views else 0.0

    # 7. 三视图统一缩放：取宽/高约束下最小比例，保证三栏高度一致
    rotated_bounds = [get_rotated_bounds(body_bounds, angle) for angle in (0, 90, 180)]
    view_scale = 1.0
    if show_views:
        for bounds in rotated_bounds:
            width = bounds[1] - bounds[0]
            height = bounds[5] - bounds[4]
            scale = min(column_world * THREE_VIEW_COLUMN_FIT / width,
                        frame_height * THREE_VIEW_COLUMN_FIT / height, 1.0)
            view_scale = min(view_scale, scale)

    # 8. 横向居中用分位中心，避免稀疏部件（如薄光环、露出的一小截尾巴）把主体挤偏；
    #    绕世界 Z 轴旋转后，90° 视图的横向中心等于 -center_y，180° 等于 -center_x
    visible_points = np.concatenate([points for points in
                                     visible_world_vertices(world_vertices, visible_masks).values()
                                     if len(points)]) if body_bounds else None
    if visible_points is not None and len(visible_points):
        center_x = robust_center(visible_points[:, 0])
        center_y = robust_center(visible_points[:, 1])
    else:
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
    view_centers = {0: center_x, 90: -center_y, 180: -center_x}

    # 纵向：以可见包围盒底部对齐，画面中心按缩放后的高度居中
    view_center_z = min_z + view_scale * model_height / 2
    frame_top = view_center_z + frame_height / 2

    # 9. 建立临时集合
    collection = create_three_view_collection()
    source_root_name = ancestor.name

    closeup_objects = []
    try:
        # 10. 侧视图（90°）与后视图（180°）使用共享数据副本，
        #     缩放/旋转/位移由复制出的 root 承载，只按 min_z 对齐、不做垂直居中
        if show_views:
            for index, angle in enumerate((90, 180)):
                target_x = -frame_half_width + closeup_world + (index + 1.5) * column_world
                translate_x = target_x - view_centers[angle] * view_scale
                translate_z = min_z * (1 - view_scale)
                matrix = (
                    mathutils.Matrix.Translation((translate_x, 0.0, translate_z))
                    @ mathutils.Matrix.Rotation(math.radians(angle), 4, 'Z')
                    @ mathutils.Matrix.Scale(view_scale, 4))
                duplicate_model_objects(mesh_objs, matrix, collection, source_root_name, ancestor)

        # 11. 特写：头部（「頭」顶点组）占画面竖向 THREE_VIEW_CLOSEUP_HEAD_RATIO，顶部对齐
        closeup_scale = 1.0
        if show_closeup:
            head_center_x = (head_bounds[0] + head_bounds[1]) / 2
            closeup_scale = (frame_height * THREE_VIEW_CLOSEUP_HEAD_RATIO) / head_height
            target_x = -frame_half_width + closeup_world / 2
            translate_x = target_x - head_center_x * closeup_scale
            translate_z = frame_top - head_bounds[3] * closeup_scale
            closeup_matrix = (
                mathutils.Matrix.Translation((translate_x, 0.0, translate_z))
                @ mathutils.Matrix.Scale(closeup_scale, 4))
            closeup_objects = duplicate_model_objects(
                mesh_objs, closeup_matrix, collection, source_root_name, ancestor)

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

    # 14. 布局相机：一张正交相机覆盖四栏，景深按模型高度估算（特写副本可能放大）
    depth = model_height * max(2.0, closeup_scale)
    camera_data = bpy.data.cameras.new(THREE_VIEW_CAMERA_NAME)
    camera = bpy.data.objects.new(THREE_VIEW_CAMERA_NAME, camera_data)
    collection.objects.link(camera)
    mark_temp_object(camera, source_root_name)
    place_layout_camera(camera, frame_width, view_center_z, -depth / 2, depth / 2)
    return {'camera': camera, 'collection': collection, 'arm_angles': arm_angles}


def preview_three_view(props, report, ancestor):
    setup = build_three_view_setup(props, report, ancestor)
    if setup is None:
        return None
    bpy.context.scene.camera = setup['camera']
    if not bpy.app.background:
        switch_to_camera_view()
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
