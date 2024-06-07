import math
import shutil

from ..utils import *

# 日文名称到Blender名称的映射
jp_bl_map = {}
# Blender名称到日文名称的映射
bl_jp_map = {}


class AddSsbOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.add_ssb"
    bl_label = "执行"
    bl_description = "追加次标准骨骼，效果同PE"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self, props):
        model = props.model
        if not model:
            self.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        pmx_root = find_pmx_root_with_child(model)
        if not pmx_root:
            self.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        return True

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_add_ssb
        if not self.check_props(props):
            return
        model = props.model
        pmx_root = find_pmx_root_with_child(model)
        pmx_armature = find_pmx_armature(pmx_root)
        pmx_objects = find_pmx_objects(pmx_armature)
        gen_bone_name_map(pmx_armature)
        # 根据勾选的选项追加次标准骨骼
        create_root_bone(pmx_armature)


def create_root_bone(armature):
    name_j = '全ての親'
    name_e = 'root'
    name_b = convertNameToLR(name_j)

    # 如果已经包含全亲骨则直接返回
    if name_j in jp_bl_map.keys():
        print(f'“{armature}”已包含“{name_j}”，已跳过')
        return
    # 创建全亲骨
    root_bone = create_bone(armature, name_b)
    jp_bl_map[name_j] = name_b
    bl_jp_map[name_b] = name_j
    # 设置骨骼名称
    mmd_bone = armature.pose.bones.get(name_b).mmd_bone
    mmd_bone.name_j = name_j
    mmd_bone.name_e = name_e
    # 设置是否可见
    set_visible(armature, name_b, True)
    # 设置是否可移动
    set_movable(armature, name_b, True)
    # 设置是否可旋转
    set_rotatable(armature, name_b, True)
    # 设置是否可操作
    set_controllable(armature, name_b, True)
    # 设置末端指向
    # PE中的模型，至少会有一个center骨；从blender导出的骨骼，至少会有一个全亲骨
    # 通常来讲全亲骨的末端应该指向センター，但是参考代码及PE中的实际操作都表明，创建全亲骨无必要的骨骼，所以这里不做指向'センター'的优化。
    # 原逻辑是全亲骨指向骨骼面板中的首位，可是blender中是通过顶点组顺序来表示骨骼面板的
    # 获取排在首位的顶点组受到了骨架下有无物体以及物体顺序等方面的干扰
    # 应保证骨架下物体有且仅有1个才能最大程度上确保指向成功（PE中指向的结果是什么样这里就是什么样）
    # 但其它情况的话也无需拦截（按材质分开很普遍，这种情况通常也可以正常指向。后续可提供一个修复指向的功能）
    # todo 对每个物体首位的顶点组计数，取最多的那个顶点组作为首位？
    objs = find_pmx_objects(armature)
    first_vg = ''
    for obj in objs:
        for vg in obj.vertex_groups:
            if vg and vg.name and name_b != vg.name and armature.pose.bones.get(vg.name, None):
                first_vg = vg.name
                break
        if first_vg:
            break
    first_bone = armature.pose.bones.get(first_vg)
    set_tail(armature, name_b, first_vg)
    # 设置面板顺序
    for obj in objs:
        select_and_activate(obj)
        set_bone_panel_order(obj, name_b, 0)
    # 设置亲骨骼及末端指向
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    for edit_bone in edit_bones:
        parent_bone = edit_bone.parent
        target_bone = get_target_bone(armature, edit_bone)
        if not parent_bone:
            edit_bone.parent = edit_bones[root_bone.name]
        elif target_bone and target_bone == first_bone:
            # 如果骨骼的末端指向first_bone，则将其改为末端指向root_bone
            set_target_bone(edit_bone, edit_bones[root_bone.name])
    # 设置显示枠
    set_root_frame(armature, root_bone, first_bone)


def gen_bone_name_map(pmx_armature):
    global jp_bl_map
    global bl_jp_map
    jp_bl_map = {}
    bl_jp_map = {}
    for pose_bone in pmx_armature.pose.bones:
        # 如果导入模型的时候jp_name为空串，则blender会创建名称为Bone.xxx的骨骼
        # 如果导出模型的时候jp_name为空串，则插件会设置为 pmx_bone.name = mmd_bone.name_j or bone.name
        # 所以除非刻意设置为空串，否则基本上不会出现jp_name重复的情况
        name_j = pose_bone.mmd_bone.name_j
        name_b = pose_bone.name
        jp_bl_map[name_j] = name_b
        bl_jp_map[name_b] = name_j
    return jp_bl_map, bl_jp_map


def create_bone(armature, bone_name):
    """创建指定名称骨骼，并返回其对应的pose bone"""
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    edit_bone = armature.data.edit_bones.new(bone_name)
    # 设置新骨骼的头尾位置，如果不设置或者头尾位置一致则无法创建成功（回物体模式后骨骼被移除了）
    edit_bone.head = (0, 0, 0)
    edit_bone.tail = (0, 0, 1)
    bpy.ops.object.mode_set(mode='OBJECT')
    return armature.pose.bones[bone_name]


def set_visible(armature, bone_name, visible):
    """设置骨骼在blender和mmd中的可见性"""
    pose_bone = armature.pose.bones.get(bone_name, None)
    if not pose_bone:
        return
    pose_bone.bone.hide = not visible


def set_movable(armature, bone_name, movable):
    """设置骨骼在blender和mmd中是否可移动"""
    pose_bone = armature.pose.bones.get(bone_name, None)
    if not pose_bone:
        return
    pose_bone.lock_location[0] = not movable
    pose_bone.lock_location[1] = not movable
    pose_bone.lock_location[2] = not movable


def set_rotatable(armature, bone_name, rotatable):
    """设置骨骼在blender和mmd中是否可旋转"""
    pose_bone = armature.pose.bones.get(bone_name, None)
    if not pose_bone:
        return
    pose_bone.lock_rotation[0] = not rotatable
    pose_bone.lock_rotation[1] = not rotatable
    pose_bone.lock_rotation[2] = not rotatable


def set_controllable(armature, bone_name, controllable):
    """
    设置骨骼在blender和mmd中是否可操作,
    不可操作在mmd中代表了无法移动旋转，但是在blender中仅仅是打了个tag，无其它额外操作
    """

    pose_bone = armature.pose.bones.get(bone_name, None)
    if not pose_bone:
        return
    pose_bone.mmd_bone.is_controllable = controllable


def set_bone_panel_order(obj, vg_name, index):
    vgs = obj.vertex_groups
    if vg_name not in vgs:
        vg = vgs.new(name=vg_name)
    else:
        vg = vgs.get(vg_name, None)
        vgs.active_index = vg.index

    move_after_target_vg(obj, index - 1)


def set_root_frame(armature, root_bone, first_bone):
    pmx_root = find_pmx_root_with_child(armature)
    if first_bone and not find_bone_item(pmx_root, first_bone):
        # 创建センター显示枠
        frame = create_center_frame(pmx_root)
        # 创建first_bone元素并将其移动到第0位
        add_item(frame, 'BONE', bl_jp_map[first_bone.name], order=0)
    mmd_root = pmx_root.mmd_root
    frames = mmd_root.display_item_frames
    if frames:
        # 获取首位显示枠（root）
        first_frame = frames[0]
        # 移除root里面的元素
        first_frame.data.clear()
        first_frame.active_item = 0
        # 创建root_bone元素并将其移动到第0位
        add_item(first_frame, 'BONE', bl_jp_map[root_bone.name], order=0)


def create_center_frame(pmx_root):
    mmd_root = pmx_root.mmd_root
    # 创建センター显示枠
    name = "センター"
    # 如果存在该显示枠，则直接返回（名称并不唯一，返回最先遇到的）
    if name in mmd_root.display_item_frames:
        return mmd_root.display_item_frames[name]
    frame = create_frame(mmd_root, name)
    frame.name_e = "center"
    # 将其移动到索引为2的位置（Root、表情之后）
    frames = mmd_root.display_item_frames
    frames.move(mmd_root.active_display_item_frame, 2)
    return frame

def find_bone_item(pmx_root, bone):
    mmd_root = pmx_root.mmd_root
    for i, frame in enumerate(mmd_root.display_item_frames):
        for j, item in enumerate(frame.data):
            if bl_jp_map[bone.name] == item:
                return True
    return False

