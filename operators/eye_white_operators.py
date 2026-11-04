import math
import re
import time

import bmesh
import bpy
from mathutils import Quaternion, Vector

from ..utils import (
    copy_obj,
    deselect_all_objects,
    find_pmx_armature,
    find_pmx_root_with_child,
    get_collection,
    hide_object,
    is_mmd_tools_enabled,
    select_and_activate,
    show_object,
    translate, set_visibility,
)


# 眼白发黑修复：集合/顶点组名称、骨骼与旋转采样参数
EYE_WHITE_COLLECTION_NAME = "眼白代理集合"
EYE_WHITE_VERTEX_GROUP = "缩裹范围"
EYE_WHITE_HEAD_GROUP = "頭"
EYE_WHITE_SWEEP_BONE_NAME = "両目"
EYE_WHITE_SWEEP_BONES = ("目.R", "目.L")
# 绕世界坐标的 Z 轴旋转，避免骨骼局部轴朝向不同导致变成上下翻转
EYE_WHITE_SWEEP_AXIS = Vector((0.0, 0.0, 1.0))
# 除绕世界 Z 轴外，还需要绕世界 X 轴扫过
EYE_WHITE_SWEEP_AXIS_X = Vector((1.0, 0.0, 0.0))
EYE_WHITE_WELD_THRESHOLD = 1e-6
EYE_WHITE_SHRINKWRAP_OFFSET = 0.002
EYE_WHITE_DISPLACE_STRENGTH = 1.0
EYE_WHITE_DISPLACE_MID_LEVEL = 0.99
EYE_WHITE_SMOOTH_FACTOR = 1.0
EYE_WHITE_SMOOTH_ITERATIONS = 5
EYE_WHITE_MATERIAL_NAME = "默认眼白"
# 生成对象记录所属模型根对象名称的自定义属性
EYE_WHITE_ROOT_PROPERTY = "mmd_kafei_tools_fix_eye_white"
# 对象名称字节数上限
EYE_WHITE_NAME_MAX_BYTES = 63


def split_object_names(text):
    """拆分对象名称：中英文逗号均可作为分隔符"""
    return [name.strip() for name in re.split(r"[,，]", text) if name.strip()]


def get_mesh_objects(text):
    """按名称获取网格对象：不存在或不是网格对象的名称直接跳过"""
    objs = []
    for name in dict.fromkeys(split_object_names(text)):
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != 'MESH':
            continue
        objs.append(obj)
    return objs


def clear_parent_keep_transform(obj):
    """取消父子级关系，保留世界变换"""
    if obj.parent is None:
        return
    matrix_world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = matrix_world


def merge_vertices_by_distance(obj, threshold):
    """按距离合并顶点（bmesh 直接修改基础网格）"""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=threshold)
        bm.to_mesh(obj.data)
    finally:
        bm.free()
    obj.data.update()


def strip_modifiers(obj, keep_type):
    """移除除指定类型以外的修改器（复制体只保留骨架修改器，避免旧修改器叠加干扰）"""
    for modifier in list(obj.modifiers):
        if modifier.type != keep_type:
            obj.modifiers.remove(modifier)


def get_side_indices(obj, armature, positive):
    """按骨骼静置姿态下的 x 值筛选顶点索引"""
    inverse_armature = armature.matrix_world.inverted()
    matrix_world = obj.matrix_world
    return [
        vertex.index for vertex in obj.data.vertices
        if ((inverse_armature @ (matrix_world @ vertex.co)).x > 0) == positive
    ]


def delete_vertices(obj, indices):
    """删除指定顶点（bmesh 直接修改基础网格）"""
    if not indices:
        return

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[index] for index in indices], context='VERTS')
        bm.to_mesh(obj.data)
    finally:
        bm.free()
    obj.data.update()


def split_by_side(obj, armature):
    """按静置姿态 x 的正负拆分物体，返回 (左侧物体, 右侧物体)；某一侧没有顶点时返回 None"""
    left_indices = get_side_indices(obj, armature, positive=True)
    if not left_indices:
        return None, obj
    if len(left_indices) == len(obj.data.vertices):
        return obj, None

    left_obj = copy_obj(obj)
    delete_vertices(left_obj, get_side_indices(obj, armature, positive=False))
    delete_vertices(obj, left_indices)
    return left_obj, obj


def split_objects_by_side(objs, armature, left_name, right_name, counterparts=None):
    """批量左右拆分并重命名，无顶点的网格对象直接移除；counterparts 记录左右配对关系"""
    left_objs, right_objs = [], []
    for obj in objs:
        left_obj, right_obj = split_by_side(obj, armature)
        if left_obj is not None:
            if not left_obj.data.vertices:
                bpy.data.objects.remove(left_obj, do_unlink=True)
                left_obj = None
            else:
                left_obj.name = left_name
                left_objs.append(left_obj)
        if right_obj is not None:
            if not right_obj.data.vertices:
                bpy.data.objects.remove(right_obj, do_unlink=True)
                right_obj = None
            else:
                right_obj.name = right_name
                right_objs.append(right_obj)

        if counterparts is not None and left_obj is not None and right_obj is not None:
            counterparts[left_obj] = right_obj
            counterparts[right_obj] = left_obj
    return left_objs, right_objs


def select_eye_object(objs):
    """选择顶点数最多的眼睛对象"""
    if not objs:
        return None
    return max(objs, key=lambda obj: len(obj.data.vertices))


def get_eye_white_material():
    """获取/创建“默认眼白”材质：仅原理化BSDF（默认参数）连接材质输出"""
    material = bpy.data.materials.get(EYE_WHITE_MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(EYE_WHITE_MATERIAL_NAME)

    material.use_nodes = True
    node_tree = material.node_tree
    node_tree.nodes.clear()
    output = node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (0.0, 0.0)
    bsdf = node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (-300.0, 0.0)
    node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return material


def set_object_material(obj, material):
    """把物体材质替换为指定材质"""
    obj.data.materials.clear()
    obj.data.materials.append(material)


def join_objects(objs, name):
    """合并物体并重命名"""
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]

    deselect_all_objects()
    for obj in objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()

    result = bpy.context.view_layer.objects.active
    result.name = name
    return result


def get_sweep_bones(armature):
    """获取用于旋转采样的骨骼：优先“両目”，否则“目.R”与“目.L”"""
    if EYE_WHITE_SWEEP_BONE_NAME in armature.pose.bones:
        return [armature.pose.bones[EYE_WHITE_SWEEP_BONE_NAME]]

    bones = [armature.pose.bones.get(name) for name in EYE_WHITE_SWEEP_BONES]
    if all(bones):
        return bones
    return []


def get_world_axis_quaternion(armature, pose_bone, axis, angle):
    """绕过世界坐标轴旋转：把世界坐标轴换算到骨骼局部空间，再构造四元数"""
    # 骨骼在未施加自身旋转时的朝向（叠加父骨骼当前姿态）
    matrix = pose_bone.bone.matrix_local.to_3x3()
    parent = pose_bone.parent
    if parent is not None:
        matrix = (parent.matrix.to_3x3()
                  @ parent.bone.matrix_local.to_3x3().inverted()
                  @ matrix)

    axis_in_armature = armature.matrix_world.to_3x3().inverted() @ axis
    axis_in_bone = matrix.inverted() @ axis_in_armature
    axis_in_bone.normalize()
    return Quaternion(axis_in_bone, angle)


def get_eye_armatures(objs):
    """通过任意眼白或眼睛对象收集所属骨架，按骨架去重"""
    armatures = []
    for obj in objs:
        pmx_root = find_pmx_root_with_child(obj)
        if pmx_root is None:
            continue
        armature = find_pmx_armature(pmx_root)
        if armature is not None and armature not in armatures:
            armatures.append(armature)
    return armatures


def remove_previous_objects(root_name):
    """删除全场景中记录为当前模型根对象的旧对象"""
    for obj in list(bpy.context.scene.objects):
        if obj.get(EYE_WHITE_ROOT_PROPERTY) == root_name:
            bpy.data.objects.remove(obj, do_unlink=True)


def has_other_model_objects(root_name):
    """全场景中是否存在其他模型生成的旧对象"""
    return any(
        obj.get(EYE_WHITE_ROOT_PROPERTY) not in (None, root_name)
        for obj in bpy.context.scene.objects
    )


def truncate_utf8(text, max_bytes):
    """按 UTF-8 字节数截断字符串，不切断字符"""
    result = []
    total = 0
    for char in text:
        length = len(char.encode('utf-8'))
        if total + length > max_bytes:
            break
        result.append(char)
        total += length
    return "".join(result)


def prefix_object_name(name, root_name):
    """为对象名添加模型 root 前缀；超出名称长度时截断 root 前缀而不是对象名"""
    if not root_name:
        return name
    available = EYE_WHITE_NAME_MAX_BYTES - len(name.encode('utf-8')) - 1
    if available <= 0:
        return name
    return f"{truncate_utf8(root_name, available)}_{name}"


def bake_evaluated_mesh(source, collection, name):
    """把物体当前求值结果（含骨架变形）烘焙为新的网格对象"""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(source.evaluated_get(depsgraph))
    mesh.name = name
    obj = bpy.data.objects.new(name, mesh)
    obj.matrix_world = source.matrix_world
    collection.objects.link(obj)
    return obj


def get_sweep_samples(limit, limit_x, step):
    """旋转采样：绕世界 Z 轴 ±横向采样区域、绕世界 X 轴 ±竖向采样区域，按采样精度步进"""
    samples = []
    step_degrees = math.degrees(step)
    for axis, axis_limit in (
            (EYE_WHITE_SWEEP_AXIS, math.degrees(limit)),
            (EYE_WHITE_SWEEP_AXIS_X, math.degrees(limit_x)),
    ):
        count = int(round(2 * axis_limit / step_degrees)) + 1
        samples.extend(
            (axis, math.radians(-axis_limit + index * step_degrees))
            for index in range(count)
        )
    return samples


def build_swept_eyes(context, armature, left_sources, right_sources, collection, left_name, right_name,
                     limit, limit_x, step):
    """同时生成左右扫过区域：每档姿态只刷新一次视图层"""
    if not left_sources and not right_sources:
        return None, None

    bones = get_sweep_bones(armature)
    if not bones:
        return None, None

    states = [(bone, bone.rotation_mode, bone.matrix_basis.copy()) for bone in bones]
    left_parts, right_parts = [], []
    try:
        for bone in bones:
            bone.rotation_mode = 'QUATERNION'

        for index, (axis, angle) in enumerate(get_sweep_samples(limit, limit_x, step)):
            for bone in bones:
                bone.rotation_quaternion = get_world_axis_quaternion(
                    armature, bone, axis, angle)
            context.view_layer.update()

            for source in left_sources:
                left_parts.append(bake_evaluated_mesh(source, collection, f"{left_name}_b{index}"))
            for source in right_sources:
                right_parts.append(bake_evaluated_mesh(source, collection, f"{right_name}_b{index}"))
    finally:
        for bone, rotation_mode, matrix_basis in states:
            bone.rotation_mode = rotation_mode
            bone.matrix_basis = matrix_basis
        context.view_layer.update()

    left_target = join_objects(left_parts, left_name) if left_parts else None
    right_target = join_objects(right_parts, right_name) if right_parts else None
    return left_target, right_target


def setup_target_vertex_groups(obj):
    """扫过区域对象：移除除“缩裹范围”外的顶点组，并在首位新建“頭”顶点组（全部权重为 1）"""
    scope_indices = []
    scope = obj.vertex_groups.get(EYE_WHITE_VERTEX_GROUP)
    if scope is not None:
        scope_indices = [
            vertex.index for vertex in obj.data.vertices
            if any(group.group == scope.index for group in vertex.groups)
        ]
    for group in list(obj.vertex_groups):
        obj.vertex_groups.remove(group)

    head = obj.vertex_groups.new(name=EYE_WHITE_HEAD_GROUP)
    head.add([vertex.index for vertex in obj.data.vertices], 1.0, 'REPLACE')

    if scope_indices:
        scope = obj.vertex_groups.new(name=EYE_WHITE_VERTEX_GROUP)
        scope.add(scope_indices, 1.0, 'REPLACE')


def copy_armature_modifier(obj, source):
    """为物体添加与源物体一致的骨架修改器：按 RNA 属性逐个复制"""
    for modifier in source.modifiers:
        if modifier.type != 'ARMATURE':
            continue

        armature_modifier = obj.modifiers.new(name=modifier.name, type='ARMATURE')
        for prop in modifier.bl_rna.properties:
            if prop.identifier in ("rna_type", "name", "type") or prop.is_readonly:
                continue
            setattr(armature_modifier, prop.identifier, getattr(modifier, prop.identifier))
        return armature_modifier
    return None


def show_armature_modifiers(objs):
    """统一确保骨架修改器在视图与渲染中都可见"""
    for obj in objs:
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE':
                modifier.show_viewport = True
                modifier.show_render = True


def get_boundary_indices(obj):
    """获取边界顶点索引（骨架修改器只变形、不改变拓扑，直接读基础网格即可）"""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        return {
            vert.index
            for edge in bm.edges if edge.is_boundary
            for vert in edge.verts
        }
    finally:
        bm.free()


def add_shrinkwrap_vertex_group(obj):
    """创建“眼白缩裹”顶点组，成员为边界以外的所有顶点"""
    boundary_indices = get_boundary_indices(obj)
    indices = [
        vertex.index for vertex in obj.data.vertices
        if vertex.index not in boundary_indices
    ]

    group = obj.vertex_groups.get(EYE_WHITE_VERTEX_GROUP)
    if group is None:
        group = obj.vertex_groups.new(name=EYE_WHITE_VERTEX_GROUP)
    group.add(indices, 1.0, 'REPLACE')
    return group


def add_eye_white_modifiers(obj, target):
    """为眼白添加置换、缩裹、加权法向修改器"""
    displace = obj.modifiers.new(name="置换", type='DISPLACE')
    displace.direction = 'Y'
    displace.texture_coords = 'LOCAL'
    displace.strength = EYE_WHITE_DISPLACE_STRENGTH
    displace.mid_level = EYE_WHITE_DISPLACE_MID_LEVEL
    displace.vertex_group = EYE_WHITE_VERTEX_GROUP

    shrinkwrap = obj.modifiers.new(name="眼白缩裹", type='SHRINKWRAP')
    shrinkwrap.target = target
    shrinkwrap.offset = EYE_WHITE_SHRINKWRAP_OFFSET
    shrinkwrap.vertex_group = EYE_WHITE_VERTEX_GROUP
    #
    # smooth = obj.modifiers.new(name="平滑", type='SMOOTH')
    # smooth.factor = EYE_WHITE_SMOOTH_FACTOR
    # smooth.iterations = EYE_WHITE_SMOOTH_ITERATIONS
    # smooth.use_x = True
    # smooth.use_y = True
    # smooth.use_z = False
    # smooth.vertex_group = EYE_WHITE_VERTEX_GROUP

    obj.modifiers.new(name="加权法向", type='WEIGHTED_NORMAL')


class FixEyeWhiteOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fix_eye_white"
    bl_label = "执行"
    bl_description = "修复眼白发黑"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}

        self.repair(context)
        self.report(type={'INFO'}, message=translate("已修复眼白发黑"))
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self, context):
        """校验参数：MMD Tools、名称、对象、骨架与骨骼"""
        if not is_mmd_tools_enabled():
            self.report(type={'ERROR'}, message=translate("未启用MMD Tools插件！"))
            return False

        props = context.scene.mmd_kafei_tools_fix_eye_white
        if not split_object_names(props.eye_white):
            self.report(type={'ERROR'}, message=translate("请填写眼白对象名称！"))
            return False
        if not split_object_names(props.eye):
            self.report(type={'ERROR'}, message=translate("请填写眼睛对象名称！"))
            return False

        eye_white_objs = get_mesh_objects(props.eye_white)
        eye_objs = get_mesh_objects(props.eye)
        if not eye_white_objs:
            self.report(type={'ERROR'}, message=translate("未找到任何眼白对象！"))
            return False
        if not eye_objs:
            self.report(type={'ERROR'}, message=translate("未找到任何眼睛对象！"))
            return False

        eye_white_armatures = get_eye_armatures(eye_white_objs)
        if not eye_white_armatures:
            self.report(type={'ERROR'}, message=translate("未找到眼白所属的骨架！"))
            return False
        if len(eye_white_armatures) != 1:
            self.report(type={'ERROR'}, message=translate("眼白之间必须属于同一个骨架！"))
            return False

        eye_armatures = get_eye_armatures(eye_objs)
        if not eye_armatures:
            self.report(type={'ERROR'}, message=translate("未找到眼睛所属的骨架！"))
            return False
        if len(eye_armatures) != 1:
            self.report(type={'ERROR'}, message=translate("眼睛之间必须属于同一个骨架！"))
            return False

        if eye_white_armatures[0] != eye_armatures[0]:
            self.report(type={'ERROR'}, message=translate("眼白与眼睛之间必须属于同一个骨架！"))
            return False

        if not get_sweep_bones(eye_armatures[0]):
            self.report(type={'ERROR'}, message=translate("未找到名为「{}」的骨骼！").format(
                EYE_WHITE_SWEEP_BONE_NAME))
            return False
        return True

    def repair(self, context):
        """复制眼白与眼睛，按左右拆分后把眼白缩裹到眼睛旋转扫过的区域"""
        start_time = time.time()

        props = context.scene.mmd_kafei_tools_fix_eye_white
        eye_objs = get_mesh_objects(props.eye)
        eye_white_objs = get_mesh_objects(props.eye_white)

        armature = get_eye_armatures(eye_objs + eye_white_objs)[0]
        root_name = find_pmx_root_with_child(armature).name
        collection = get_collection(EYE_WHITE_COLLECTION_NAME)

        # 删除同一模型上次生成的旧对象
        remove_previous_objects(root_name)

        # 全场景存在其他模型的旧对象时，生成对象名添加 root 前缀以便区分
        prefix = root_name if has_other_model_objects(root_name) else ""
        white_left_name = prefix_object_name("眼白代理_左", prefix)
        white_right_name = prefix_object_name("眼白代理_右", prefix)
        target_left_name = prefix_object_name("眼白目标缩裹_左", prefix)
        target_right_name = prefix_object_name("眼白目标缩裹_右", prefix)

        # 拷贝眼白对象、眼睛对象
        eye_white_copies = [copy_obj(obj, "眼白代理", collection) for obj in eye_white_objs]
        eye_copies = [copy_obj(obj, "眼睛a", collection) for obj in eye_objs]
        for obj in eye_white_copies + eye_copies:
            show_object(obj)

        # 隐藏源眼白对象
        for obj in list(eye_white_objs):
            set_visibility(obj, (False, True, False, True))

        # 移除拷贝对象的父级，避免导出等操作时，被当成MMD模型，导致结果异常
        # 移除拷贝对象的骨架之外修改器，避免影响后续操作
        for obj in eye_white_copies + eye_copies:
            clear_parent_keep_transform(obj)
            strip_modifiers(obj, 'ARMATURE')

        # 眼白按距离合并，避免重合点干扰边界顶点的选取
        for obj in eye_white_copies:
            merge_vertices_by_distance(obj, EYE_WHITE_WELD_THRESHOLD)

        # 拆分左右眼白、左右眼
        left_whites, right_whites = split_objects_by_side(
            eye_white_copies, armature, white_left_name, white_right_name)
        eye_counterparts = {}
        left_eyes, right_eyes = split_objects_by_side(eye_copies, armature, "左眼a", "右眼a", eye_counterparts)
        # 确保左右眼白代理可见
        for obj in left_whites + right_whites:
            show_object(obj)

        # 每侧只取顶点数最多的眼睛对象；另一侧优先用同源拆分的对象
        left_eye = select_eye_object(left_eyes)
        right_eye = eye_counterparts.get(left_eye)
        if right_eye is None:
            right_eye = select_eye_object(right_eyes)

        # 构建缩裹对象：根据左右眼沿全局 Z、全局 X 扫过的区域生成
        left_target, right_target = build_swept_eyes(
            context, armature,
            [left_eye] if left_eye else [], [right_eye] if right_eye else [],
            collection, target_left_name, target_right_name,
            props.sweep_limit, props.sweep_limit_x, props.sweep_step)
        for target, whites in ((left_target, left_whites), (right_target, right_whites)):
            if target is None or not whites:
                continue
            setup_target_vertex_groups(target)
            copy_armature_modifier(target, whites[0])
            set_visibility(target, (False, True, False, True))

        # 生成对象记录所属模型根对象名称，便于下次执行时清理
        generated_objs = left_whites + right_whites + [
            target for target in (left_target, right_target) if target is not None]
        for obj in generated_objs:
            obj[EYE_WHITE_ROOT_PROPERTY] = root_name

        # 眼睛拷贝仅用于生成扫过区域，之后统一删除
        for obj in left_eyes + right_eyes:
            bpy.data.objects.remove(obj, do_unlink=True)
        left_eyes.clear()
        right_eyes.clear()

        for obj in left_whites:
            if left_target is None:
                break
            add_shrinkwrap_vertex_group(obj)
            add_eye_white_modifiers(obj, left_target)

        for obj in right_whites:
            if right_target is None:
                break
            add_shrinkwrap_vertex_group(obj)
            add_eye_white_modifiers(obj, right_target)

        # 统一确保眼白与扫过区域的骨架修改器在视图与渲染中可见
        show_armature_modifiers(
            left_whites + right_whites
            + [target for target in (left_target, right_target) if target is not None])

        # 关闭阴影射线可见性：源眼白/眼睛、眼白拷贝与扫过区域都不再投射阴影
        shadow_objs = list(eye_objs) + list(eye_white_objs) + left_whites + right_whites
        shadow_objs += [target for target in (left_target, right_target) if target is not None]
        for obj in shadow_objs:
            obj.visible_shadow = False

        # 左右眼白与扫过区域统一使用“默认眼白”材质
        material = get_eye_white_material()
        for obj in left_whites + right_whites:
            set_object_material(obj, material)
        for target in (left_target, right_target):
            if target is not None:
                set_object_material(target, material)

        print(f"修复眼白发黑总耗时：{time.time() - start_time:.2f}s")


class AddEyeWhiteObjectNameOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.add_eye_white_name"
    bl_label = "添加选中对象名称"
    bl_description = "将选中对象的名称添加到输入框"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    target: bpy.props.EnumProperty(
        name="目标",
        description="要添加到的输入框",
        items=[
            ("EYE_WHITE", "眼白", "添加到眼白输入框"),
            ("EYE", "眼睛", "添加到眼睛输入框"),
        ],
        default="EYE_WHITE",
    )

    def execute(self, context):
        names = [obj.name for obj in context.selected_objects]
        if not names:
            self.report(type={'ERROR'}, message=bpy.app.translations.pgettext_iface("请至少选择一个对象！"))
            return {'CANCELLED'}

        def append_names(text):
            """把选中对象名称追加到已有的名称串中，已存在的不重复添加"""
            current = split_object_names(text)
            for name in names:
                if name not in current:
                    current.append(name)
            return ",".join(current)

        props = context.scene.mmd_kafei_tools_fix_eye_white
        if self.target == "EYE_WHITE":
            props.eye_white = append_names(props.eye_white)
        else:
            props.eye = append_names(props.eye)
        return {'FINISHED'}
