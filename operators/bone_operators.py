import re

import bpy

from ..constants import PMX_BAKE_BONES

from ..utils import (
    deselect_all_objects,
    find_joint_parent,
    find_pmx_armature,
    find_pmx_root_with_child,
    find_rigid_body_parent,
    get_physical_bone,
    is_mmd_tools_enabled,
    is_pose_bone_hidden,
    is_pose_bone_selected,
    select_and_activate,
    select_pose_bone,
    show_object,
    translate,
)


class BoneOperatorMixin:
    """骨骼操作公共逻辑：统一校验与执行"""

    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能
    option = ""

    def check_props(self, context):
        """公共校验"""
        if not is_mmd_tools_enabled():
            self.report(type={'ERROR'}, message=translate("未启用MMD Tools插件！"))
            return False
        active_object = context.active_object
        pmx_root = find_pmx_root_with_child(active_object)
        if not active_object or not pmx_root:
            self.report(type={'ERROR'}, message=translate("请选择MMD模型！"))
            return False
        armature = find_pmx_armature(pmx_root)
        if not armature:
            self.report(type={'ERROR'}, message=translate("未找到模型骨架！"))
            return False
        return True

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}
        self.run(context)
        return {'FINISHED'}

    def run(self, context):
        """默认执行逻辑：按 option 选择关联骨骼"""
        select_bone_by_input(context, self.option)


class FlipBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.flip_bone"
    bl_label = "翻转姿态"
    bl_description = "翻转姿态"
    option = "FLIP_BONE"

    def check_props(self, context):
        if not super().check_props(context):
            return False
        armature = find_pmx_armature(find_pmx_root_with_child(context.active_object))

        # 翻转姿态校验：需选中骨骼
        selected_pbs = [pb for pb in armature.pose.bones if is_pose_bone_selected(pb)]
        if not selected_pbs:
            self.report(type={'ERROR'}, message=translate("请至少选择一根骨骼！"))
            return False
        return True

    def run(self, context):
        pmx_root = find_pmx_root_with_child(context.active_object)
        flip_bone(context, find_pmx_armature(pmx_root))


class DeleteInvalidRigidbodyJointOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.delete_invalid_rigidbody_joint"
    bl_label = "清理无效刚体Joint"
    bl_description = "清理无效的刚体和关节。如果刚体所关联的骨骼不存在，则删除该刚体及与之关联的关节；如果刚体没有关联的骨骼，则不处理"
    option = "INVALID_RIGIDBODY_JOINT"

    def run(self, context):
        remove_invalid_rigidbody_joint(context)


class SelectPhysicalBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_physical_bone"
    bl_label = "物理骨骼"
    bl_description = "选择受物理影响的MMD骨骼"
    option = "PHYSICAL_BONE"

    def run(self, context):
        select_physical_bone(context)


class SelectBakeBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_bake_bone"
    bl_label = "K帧骨骼"
    bl_description = "选择用于K帧的MMD骨骼"
    option = "BAKE_BONE"

    def run(self, context):
        select_bake_bone(context)


class SelectLinkedBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_linked_bone"
    bl_label = "关联骨骼"
    bl_description = "选择以父/子关系关联到当前选中项的所有骨骼"
    option = "LINKED_BONE"


class SelectRingBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_ring_bone"
    bl_label = "并排骨骼"
    bl_description = "根据骨骼名称，选择当前选中项的环绕骨骼，例如选择裙子骨骼的一周"
    option = "RING_BONE"


class SelecExtendParentBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_extend_parent_bone"
    bl_label = "父 +"
    bl_description = "拓展选择当前选中项的父骨骼"
    option = "EXTEND_PARENT_BONE"


class SelectExtendChildrenBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_extend_children_bone"
    bl_label = "子 +"
    bl_description = "拓展选择当前选中项的子骨骼"
    option = "EXTEND_CHILDREN_BONE"


class SelectLessParentBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_less_parent_bone"
    bl_label = "父 -"
    bl_description = "从当前选中项的父级开始缩减选择"
    option = "LESS_PARENT_BONE"


class SelectLessChildrenBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_less_children_bone"
    bl_label = "子 -"
    bl_description = "从当前选中项的子级开始缩减选择"
    option = "LESS_CHILDREN_BONE"


class SelectMoreBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_more_bone"
    bl_label = "拓展选区"
    bl_description = "拓展选择当前选中项的父子骨骼"
    option = "MORE_BONE"


class SelectLessBoneOperator(BoneOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_less_bone"
    bl_label = "缩减选区"
    bl_description = "缩减选择当前选中项的父子骨骼"
    option = "LESS_BONE"


def is_valid_bone(bone_info, pb):
    eb_hide_map, original_mode, visible_bone_names = bone_info
    if not pb:
        return False
    # 骨骼被隐藏
    if original_mode == 'POSE' and is_pose_bone_hidden(pb):
        return False
    if original_mode == 'EDIT' and eb_hide_map.get(pb.name):
        return False

    # 骨骼不在显示层
    return pb.name in visible_bone_names


def traverse_parent_linked(bone_info, pb, pb_set):
    parent = pb.parent
    if is_valid_bone(bone_info, parent):
        # 如果父骨骼只有一个子骨骼，将其添加到列表
        if len(parent.children) == 1:
            pb_set.add(parent)
            traverse_parent_linked(bone_info, parent, pb_set)
        # 否则结束递归
        else:
            return


def traverse_parent(bone_info, pb, pb_set, once):
    parent = pb.parent
    if is_valid_bone(bone_info, parent):
        pb_set.add(parent)
        if once:
            return
        traverse_parent(bone_info, parent, pb_set, once)
    else:
        return


def traverse_children(bone_info, pb, pb_set, once):
    if len(pb.children) != 1:
        return
    do_traverse_children(bone_info, pb, pb_set, once)


def do_traverse_children(bone_info, pb, pb_set, once):
    # 子骨不可见/被隐藏时不加入，也不继续向下查找
    child = pb.children[0]
    if not is_valid_bone(bone_info, child):
        return
    pb_set.add(child)
    # 只遍历单链骨骼，子骨存在分叉时到此为止
    if once or len(child.children) != 1:
        return
    do_traverse_children(bone_info, child, pb_set, once)  # 继续递归子骨骼


def get_ring_bone(bone_info, selected_pbs, pbs, pb_set):
    prefix_set = set()
    for pb in selected_pbs:
        prefix = get_prefix(pb.name)
        if prefix:
            prefix_set.add(prefix)
    for pb in pbs:
        prefix = get_prefix(pb.name)
        if prefix in prefix_set and is_valid_bone(bone_info, pb):
            pb_set.add(pb)


def get_deselected_ancestor(bone_info, pb, selected_pbs):
    prev = pb
    parent = pb.parent
    while is_valid_bone(bone_info, parent) and parent in selected_pbs:
        prev = parent
        parent = parent.parent

    return prev


def get_prefix(bl_name):
    # 去除.xxx后缀
    basename = re.sub(r'\.\d+$', '', bl_name)
    # 去除LR
    if basename.endswith(('.L', '.R', '.l', '.r', '_L', '_R', '_l', '_r')):
        basename = basename[:-2]
    # 提取数字
    match = re.search(r'_(\d+)_(\d+)$', basename)
    if match:
        number1 = match.group(1)
        number2 = match.group(2)
        suffix = "_" + number1 + "_" + number2
        part_name = basename.replace(suffix, "")
        prefix = part_name + "_" + number1 + "_"
        return prefix
    return None


def flip_bone(context, armature):
    """翻转骨骼姿态，仅在姿态模式下生效"""
    selected_pbs = [pb for pb in armature.pose.bones if is_pose_bone_selected(pb)]
    # MMD Tools 需要 selected_pose_bones，但后台下 selected_pose_bones 为空
    with context.temp_override(active_object=armature, selected_pose_bones=selected_pbs):
        # 未启用 MMD Tools 或不是 PMX 模型时，使用 Blender 原生的复制/翻转粘贴
        if not is_mmd_tools_enabled() or not find_pmx_root_with_child(armature):
            bpy.ops.pose.copy()
            bpy.ops.pose.paste(flipped=True)
        else:
            bpy.ops.mmd_tools.flip_pose()


def remove_invalid_rigidbody_joint(context):
    """清理无效刚体Joint"""
    obj = context.active_object
    original_mode = obj.mode
    root = find_pmx_root_with_child(obj)
    armature = find_pmx_armature(root)
    rigidbody_parent = find_rigid_body_parent(root)
    joint_parent = find_joint_parent(root)
    # Joint 集合为空时，用空序列占位，后续无需再判空
    joints = joint_parent.children if joint_parent is not None else ()

    # 如果没有 rigidbody_parent，则关节无意义，此时关节的存在必然会导致MMD闪退
    if rigidbody_parent is None:
        for joint in reversed(joints):
            bpy.data.objects.remove(joint, do_unlink=True)
        return
    # 没有 joint_parent 时，刚体仍可能有效

    deselect_all_objects()
    show_object(armature)
    select_and_activate(armature)
    bpy.ops.object.mode_set(mode='POSE')  # 如果不进入POSE模式，armature.pose.bones无法获取到EDIT模式下对骨骼的修改

    # （预先）删除无效关节
    for joint in reversed(joints):
        rigidbody1 = joint.rigid_body_constraint.object1
        rigidbody2 = joint.rigid_body_constraint.object2
        if any(r not in rigidbody_parent.children for r in [rigidbody1, rigidbody2]):
            bpy.data.objects.remove(joint, do_unlink=True)

    # 处理刚体
    for rigidbody in reversed(rigidbody_parent.children):
        bl_name = rigidbody.mmd_rigid.bone
        # 当刚体没有关联的骨骼时，可能是本身设置错误，也可能是本来就没有关联的骨骼，这里不处理
        if not bl_name:
            continue
        # 关联骨骼不存在则删除这个刚体
        if bl_name not in armature.pose.bones:
            bpy.data.objects.remove(rigidbody, do_unlink=True)

    # 删除没有关联刚体的关节
    for joint in reversed(joints):
        rigidbody1 = joint.rigid_body_constraint.object1
        rigidbody2 = joint.rigid_body_constraint.object2
        if not rigidbody1 or not rigidbody2:
            bpy.data.objects.remove(joint, do_unlink=True)

    bpy.ops.object.mode_set(mode=original_mode)


def select_physical_bone(context):
    """选择物理骨骼"""
    root = find_pmx_root_with_child(context.active_object)
    bl_names = get_physical_bone(root)
    select_bone_by_predicate(context, lambda bone: bone.name in bl_names)


def select_bake_bone(context):
    """选择用于烘焙VMD的骨骼"""
    select_bone_by_predicate(context, lambda bone: bone.mmd_bone.name_j in PMX_BAKE_BONES)


def select_bone_by_predicate(context, predicate):
    """按给定条件选中/取消选中骨架中的骨骼，完成后恢复原模式"""
    obj = context.active_object
    original_mode = obj.mode
    pmx_root = find_pmx_root_with_child(obj)
    armature = find_pmx_armature(pmx_root)
    # 选中骨架并进入姿态模式
    deselect_all_objects()
    show_object(armature)
    select_and_activate(armature)
    bpy.ops.object.mode_set(mode='POSE')
    for bone in armature.pose.bones:
        select_pose_bone(bone, predicate(bone))

    if original_mode != "POSE":
        bpy.ops.object.mode_set(mode=original_mode)


def get_end_bones(bone_info, selected_pbs, pb_set):
    """获取末端子骨，即子骨数量为0或子骨均未被选中"""
    for pb in selected_pbs:
        if len(pb.children) == 0:
            pb_set.add(pb)
        else:
            selected_child_flag = False
            for child in pb.children:
                if is_pose_bone_selected(child) and is_valid_bone(bone_info, child):
                    selected_child_flag = True
                    break
            if not selected_child_flag:
                pb_set.add(pb)


def get_bone_info(armature, original_mode):
    """获取骨骼信息：编辑模式下骨骼的隐藏状态 初始模式 可见骨骼名称集合"""
    eb_hide_map = {}
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in armature.data.edit_bones:
        eb_hide_map[eb.name] = eb.hide
    bpy.ops.object.mode_set(mode='POSE')  # Warning: `Collection.bones` is not available in armature edit mode

    if bpy.app.version < (4, 0, 0):
        layers = armature.data.layers
        visible_bone_names = {
            bone.name for bone in armature.data.bones
            if any(layers[i] for i, layer in enumerate(bone.layers) if layer)
        }
    else:
        # https://docs.blender.org/api/current/bpy.types.BoneCollection.html#bpy.types.BoneCollection.is_visible_effectively
        visible_bone_names = {
            bone.name for collection in armature.data.collections_all
            if collection.is_visible_effectively for bone in collection.bones
        }
    return eb_hide_map, original_mode, visible_bone_names


def select_bone_by_input(context, option):
    """根据用户所选择的骨骼，来选择option相关骨骼

    关联骨骼：
        Blender原逻辑：向上寻找父级，向下寻找子级，遇到非关联项则结束寻找
        现逻辑：向上寻找父级，向下寻找子级，如果父级/子级存在分叉（多个子级）则结束查找
    并排骨骼：
        选择环绕骨骼，有点类似选择并排边，PE插件创建物理骨骼时名称存在“_纵向id_横向id”格式的后缀，以此来判别
        在通过MMM等方式烘焙骨骼动作时，可能需要对骨骼名称进行修复，这会破坏原有的“_纵向id_横向id”格式，这种情况暂不处理
    镜像骨骼：
        使用Blender原生函数，需根据姿态模式和编辑模式来选择具体函数（不同模式下函数不一样）
    父 +：
        向上一直寻找父级
    子 +：
        向下寻找子级，存在分叉（多个子级）则结束查找
    父 -：
        从选中项中的祖先节点开始缩减选择
    子 -：
        从选中项中的末端节点开始缩减选择

    Blender原逻辑：以激活的节点为范围
    现逻辑：以选中项为范围

    在查找过程中，骨骼不存在，骨骼被隐藏，骨骼所在层未被选中，都被视为骨骼不存在。
    在缩减选择时，若骨骼“不存在”，则需从选中项中排除这些骨骼，以防止这些骨骼对流程的影响。
    就算激活骨骼未被选中，他也可能是激活骨骼。
    """
    # 获取基本信息
    obj = context.active_object
    original_mode = obj.mode
    pmx_root = find_pmx_root_with_child(obj)
    armature = find_pmx_armature(pmx_root)

    deselect_all_objects()
    show_object(armature)
    select_and_activate(armature)

    # 获取骨骼信息：编辑模式下骨骼的隐藏状态 初始模式 骨骼所在层
    bone_info = get_bone_info(armature, original_mode)

    pbs = armature.pose.bones
    selected_pbs = []
    for pb in pbs:
        # Blender逻辑中，关联查找不考虑被选中的隐藏骨骼，而查找父级子级时考虑，这里统一不考虑
        if is_pose_bone_selected(pb) and is_valid_bone(bone_info, pb):
            selected_pbs.append(pb)

    # 没有骨骼被选择则直接返回
    if not selected_pbs:
        bpy.ops.object.mode_set(mode=original_mode)
        return

    # 拓展选择时，需维持当前激活骨骼的激活状态，缩减选择时，若激活骨骼为将被缩减选择的骨骼，则无需保持激活状态。
    active_pb = None
    if armature.data.bones.active:
        active_pb = pbs.get(armature.data.bones.active.name)

    # 获取将被选择/取消选择的集合
    selected_set = set()
    unselected_set = set()
    bpy.ops.object.mode_set(mode='POSE')
    if option == "LINKED_BONE":
        for selected_pb in selected_pbs:
            traverse_parent_linked(bone_info, selected_pb, selected_set)
            traverse_children(bone_info, selected_pb, selected_set, False)
    elif option == "RING_BONE":
        get_ring_bone(bone_info, selected_pbs, pbs, selected_set)
    elif option == "EXTEND_PARENT_BONE":
        for selected_pb in selected_pbs:
            traverse_parent(bone_info, selected_pb, selected_set, True)
    elif option == "EXTEND_CHILDREN_BONE":
        for selected_pb in selected_pbs:
            traverse_children(bone_info, selected_pb, selected_set, True)
    elif option == "MORE_BONE":
        for selected_pb in selected_pbs:
            traverse_parent(bone_info, selected_pb, selected_set, True)
            traverse_children(bone_info, selected_pb, selected_set, True)
    elif option == "LESS_PARENT_BONE":
        for pb in selected_pbs:
            ancestor = get_deselected_ancestor(bone_info, pb, selected_pbs)
            unselected_set.add(ancestor)
    elif option == "LESS_CHILDREN_BONE":
        get_end_bones(bone_info, selected_pbs, unselected_set)
    elif option == "LESS_BONE":
        for pb in selected_pbs:
            ancestor = get_deselected_ancestor(bone_info, pb, selected_pbs)
            unselected_set.add(ancestor)
        get_end_bones(bone_info, selected_pbs, unselected_set)

    # 选择/取消选择
    if option in ["LESS_PARENT_BONE", "LESS_CHILDREN_BONE", "LESS_BONE"]:
        unselect_bone(armature, unselected_set)
    else:
        for pb in selected_set:
            select_pose_bone(pb, True)
        if active_pb in selected_pbs:
            select_pose_bone(active_pb, True)

    # 返回初始模式
    bpy.ops.object.mode_set(mode=original_mode)


def unselect_bone(armature, pb_set):
    """取消选择骨骼（POSE / EDIT 各切换一次）"""
    if not pb_set:
        return
    bpy.ops.object.mode_set(mode="POSE")
    for pb in pb_set:
        select_pose_bone(pb, False)
    bpy.ops.object.mode_set(mode="EDIT")
    for pb in pb_set:
        eb = armature.data.edit_bones.get(pb.name)
        eb.select = False
        eb.select_head = False
        eb.select_tail = False
