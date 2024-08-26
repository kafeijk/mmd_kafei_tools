from ..utils import *


class GenDisplayItemFrameOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.gen_display_item_frame"
    bl_label = "生成"
    # todo 引导用户在空场景下执行，空场景下2个pmx要20s，非空场景测了下2个要120s，待后续调查
    bl_description = "生成显示枠"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_gen_display_item_frame
        if not self.check_props(props):
            return
        batch = props.batch
        batch_flag = batch.flag
        if batch_flag:
            batch_process(gen_display_frame, props, f_flag=False)
        else:
            active_object = bpy.context.active_object
            pmx_root = find_ancestor(active_object)
            gen_display_frame(pmx_root, props)

    def check_props(self, props):
        batch = props.batch
        batch_flag = batch.flag
        if batch_flag:
            if not check_batch_props(self, batch):
                return False
        else:
            active_object = bpy.context.active_object
            if not active_object:
                self.report(type={'ERROR'}, message=f'请选择MMD模型')
                return False
            pmx_root = find_ancestor(active_object)
            if pmx_root.mmd_type != "ROOT":
                self.report(type={'ERROR'}, message=f'请选择MMD模型')
                return False
            armature = find_pmx_armature(pmx_root)
            if not armature:
                self.report(type={'ERROR'}, message=f'请选择MMD模型')
                return False
        return True


def gen_display_frame(pmx_root, props):
    """生成显示枠"""
    mmd_root = pmx_root.mmd_root
    armature = find_pmx_armature(pmx_root)

    bone_flag = props.bone_flag
    exp_flag = props.exp_flag

    # 激活骨架对象并进入姿态模式
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode='OBJECT')
    show_object(armature)
    deselect_all_objects()
    select_and_activate(armature)

    # 骨骼jp名称 -> 是否处理完毕
    jp_processed_map = {}
    # 骨骼jp名称 -> 骨骼
    jp_bone_map = {}
    # 骨骼jp名称 -> 骨骼blender名称
    jp_bl_map = {}
    # 骨骼blender名称 -> 骨骼jp名称
    bl_jp_map = {}

    # 构建字典
    for bone in armature.pose.bones:
        jp_bone_map[bone.mmd_bone.name_j] = bone
        bl_jp_map[bone.name] = bone.mmd_bone.name_j
        jp_bl_map[bone.mmd_bone.name_j] = bone.name
        jp_processed_map[bone.mmd_bone.name_j] = False

    # 获取显示枠内元素预设
    common_items = get_common_items()
    # 常用显示枠 -> 常用显示枠内元素
    frame_items = OrderedDict()
    for common_item in common_items:
        if common_item.display_panel not in frame_items:
            frame_items[common_item.display_panel] = []
        frame_items[common_item.display_panel].append(common_item.jp_name)

    if exp_flag:
        # 重置表情显示枠
        reset_expression_frame(mmd_root)
        # 添加显示枠内元素（表情）
        bpy.ops.mmd_tools.display_item_quick_setup(type='FACIAL')

    if bone_flag:
        # 重置骨骼显示枠
        reset_bone_frame(mmd_root)

        # 新建显示枠
        common_frame_names = get_common_frame_names()
        for common_frame_name in common_frame_names:
            add_frame(pmx_root, common_frame_name)

        # 添加显示枠内元素（常用）
        add_common_item(mmd_root, jp_bone_map, jp_bl_map, jp_processed_map, frame_items)
        # 添加显示枠内元素（物理）
        add_physical_item(pmx_root, armature, bl_jp_map, jp_processed_map)
        # 添加显示枠内元素（剩余未添加的骨骼）
        add_other_item(armature, jp_bl_map, bl_jp_map, mmd_root, jp_processed_map)
        # 移除不包含元素的显示枠
        remove_empty_frame(mmd_root)


def create_expression_frame(frames):
    frame_expression = frames.add()
    # 在显示枠的日文名称是“表情”，对应英文为“Exp”，看意思是“expression”的缩写，但实际上“expression”并无此缩写，这里为了与pmx保持一致名称为“Exp”
    frame_expression.name = '表情'
    frame_expression.name_e = 'Exp'
    frame_expression.is_special = True
    frames.move(frames.find('表情'), 1)
    return frame_expression


def reset_bone_frame(mmd_root):
    """重置骨骼显示枠"""
    frames = mmd_root.display_item_frames
    for i in range(len(frames) - 1, -1, -1):
        frame = frames[i]
        if frame.name != '表情':
            print(frame.name)
            frames.remove(i)

    frame_root = frames.add()
    frame_root.name = 'Root'
    frame_root.name_e = 'Root'
    frame_root.is_special = True

    frames.move(frames.find('Root'), 0)


def reset_expression_frame(mmd_root):
    """重置表情显示枠"""
    frames = mmd_root.display_item_frames
    for i in range(len(frames) - 1, -1, -1):
        frame = frames[i]
        if frame.name == '表情':
            frames.remove(i)

    create_expression_frame(frames)


def add_common_item(mmd_root, jp_bone_map, jp_bl_map, jp_processed_map, frame_items):
    """添加显示枠内元素（常用）"""
    frames = mmd_root.display_item_frames
    for i, frame in enumerate(frames):
        # 跳过表情显示枠
        if i == 1:
            continue
        jp_names = frame_items.get(frame.name, None)
        # 如"物理"，"その他"等显示枠元素不一定存在于frame_map中
        if jp_names is None:
            continue
        for jp_name in jp_names:
            bone = jp_bone_map.get(jp_name, None)
            # 常用预设中的骨骼并不一定存在于当前骨架中
            if bone is None:
                continue
            bl_name = jp_bl_map[jp_name]
            do_add_item(frame, 'BONE', bl_name, order=-1)
            jp_processed_map[jp_name] = True


def add_frame(pmx_root, frame_name):
    """增加指定名称的显示枠"""
    mmd_root = pmx_root.mmd_root
    frames = mmd_root.display_item_frames
    item, index = ItemOp.add_after(frames, len(frames) - 1)
    item.name = frame_name
    mmd_root.active_display_item_frame = index


def add_other_item(armature, jp_bl_map, bl_jp_map, mmd_root, jp_processed_map):
    """添加显示枠内元素（剩余未添加的骨骼）"""
    # 其它未添加的内容
    items = []

    # 寻找'その他'显示枠
    other_frame = get_frame_by_name(mmd_root, "その他")

    for processing_bone, flag in jp_processed_map.items():
        if flag:
            continue
        items.append(jp_bl_map[processing_bone])

    # 按照pose bone的顺序对骨骼排序
    pose_bones = armature.pose.bones
    items.sort(
        key=lambda bone_name: pose_bones.find(bone_name)
    )

    for bl_name in items:
        do_add_item(other_frame, 'BONE', bl_name, order=-1)
        jp_name = bl_jp_map[bl_name]
        jp_processed_map[jp_name] = True


def remove_empty_frame(mmd_root):
    """如果显示枠内无元素，则移除该显示枠（跳过root和表情的显示枠）"""
    frames = mmd_root.display_item_frames
    for i in range(len(frames) - 1, 1, -1):
        if not frames[i].data:
            frames.remove(i)


def add_physical_item(pmx_root, armature, bl_jp_map, jp_processed_map):
    """添加显示枠内元素（物理），需要屏蔽blender中骨骼名称对jp骨骼名称排序的影响"""
    rigid_grp_obj = find_rigid_body_parent(pmx_root)
    if rigid_grp_obj is None:
        return
    mmd_root = pmx_root.mmd_root
    rigid_bodies = rigid_grp_obj.children
    # 受刚体物理影响的骨骼名称列表（blender名称）
    affected_bone_bl_names = []
    for rigid_body in rigid_bodies:
        # 存在有刚体但没有关联骨骼的情况
        if rigid_body.mmd_rigid.bone == '':
            continue
        # common时处理过的这里不处理
        if jp_processed_map[bl_jp_map[rigid_body.mmd_rigid.bone]]:
            continue
        # 0:骨骼 1:物理 2:物理+骨骼
        if rigid_body.mmd_rigid.type not in ('1', '2'):
            continue
        affected_bone_bl_names.append(rigid_body.mmd_rigid.bone)

    # 按照pose bone的顺序对骨骼排序
    pose_bones = armature.pose.bones
    affected_bone_bl_names.sort(
        key=lambda bone_name: pose_bones.find(bone_name)
    )

    # 寻找物理显示枠索引（肯定有）
    physical_frame = get_frame_by_name(mmd_root, "物理")

    for bl_name in affected_bone_bl_names:
        do_add_item(physical_frame, 'BONE', bl_name, order=-1)
        jp_name = bl_jp_map[bl_name]
        jp_processed_map[jp_name] = True


def get_frame_by_name(mmd_root, frame_name):
    frames = mmd_root.display_item_frames
    for frame in frames:
        if frame.name != frame_name:
            continue
        return frame
    return None


class Item:
    def __init__(self, jp_name, eng_name, display_panel):
        self.jp_name = jp_name
        self.eng_name = eng_name
        self.display_panel = display_panel


def get_common_items():
    # 常用的骨骼（不限类型）按照预设分组 参考 https://note.com/mamepika/n/n9b8a6d55f0bb
    # 剩余的受物理影响的骨骼自动放到"物理"显示枠中
    # 剩余的其它的骨骼自动移动到"その他"中
    # todo 暂时采用硬编码的方式，之后考虑如何让用户方便的修改预设值
    return [
        Item("操作中心", "view cnt", 'Root'),

        Item("全ての親", "root", 'センター'),
        Item("センター", "center", "センター"),
        Item("グルーブ", "groove", 'センター'),

        Item("左足IK親", "leg IKP_L", 'ＩＫ'),
        Item("左足ＩＫ", "leg IK_L", "ＩＫ"),
        Item("左つま先ＩＫ", "toe IK_L", "ＩＫ"),
        Item("左足先ＩＫ", "toe2 IK_L", "ＩＫ"),
        Item("右足IK親", "leg IKP_R", 'ＩＫ'),
        Item("右足ＩＫ", "leg IK_R", 'ＩＫ'),
        Item("右つま先ＩＫ", "toe IK_R", "ＩＫ"),
        Item("右足先ＩＫ", "toe2 IK_R", "ＩＫ"),

        Item("上半身", "upper body", "体(上)"),
        Item("上半身3", "upper body", "体(上)"),
        Item("上半身2", "upper body", "体(上)"),
        Item("首", "neck", "体(上)"),
        Item("頭", "head", "体(上)"),
        Item("左目", "eye_L", "体(上)"),
        Item("右目", "eye_R", "体(上)"),
        Item("両目", "eyes", "体(上)"),

        Item("左肩P", "shoulderP_L", "腕"),
        Item("左肩", "shoulder_L", "腕"),
        Item("左腕", "arm_L", "腕"),
        Item("左腕捩", "arm twist_L", "腕"),
        Item("左ひじ", "elbow_L", "腕"),
        Item("左手捩", "wrist twist_L", "腕"),
        Item("左手首", "wrist_L", "腕"),
        Item("左ダミー", "dummy_L", "腕"),
        Item("右肩P", "shoulderP_R", "腕"),
        Item("右肩", "shoulder_R", "腕"),
        Item("右腕", "arm_R", "腕"),
        Item("右腕捩", "arm twist_R", "腕"),
        Item("右ひじ", "elbow_R", "腕"),
        Item("右手捩", "wrist twist_R", "腕"),
        Item("右手首", "wrist_R", "腕"),
        Item("右ダミー", "dummy_R", "腕"),

        Item("調整ボーン親", "", "_調整ボーン"),
        Item("センター調整", "", "_調整ボーン"),
        Item("グルーブ調整", "", "_調整ボーン"),
        Item("下半身調整", "", "_調整ボーン"),
        Item("上半身調整", "", "_調整ボーン"),
        Item("上半身2調整", "", "_調整ボーン"),
        Item("首調整", "", "_調整ボーン"),
        Item("頭調整", "", "_調整ボーン"),
        Item("両目調整", "", "_調整ボーン"),
        Item("左肩調整", "", "_調整ボーン"),
        Item("左腕調整", "", "_調整ボーン"),
        Item("左腕捩調整", "", "_調整ボーン"),
        Item("左ひじ調整", "", "_調整ボーン"),
        Item("左手捩調整", "", "_調整ボーン"),
        Item("左手首調整", "", "_調整ボーン"),
        Item("右肩調整", "", "_調整ボーン"),
        Item("右腕調整", "", "_調整ボーン"),
        Item("右腕捩調整", "", "_調整ボーン"),
        Item("右ひじ調整", "", "_調整ボーン"),
        Item("右手捩調整", "", "_調整ボーン"),
        Item("右手首調整", "", "_調整ボーン"),
        Item("左足ＩＫ調整", "", "_調整ボーン"),
        Item("左つま先ＩＫ調整", "", "_調整ボーン"),
        Item("右足ＩＫ調整", "", "_調整ボーン"),
        Item("右つま先ＩＫ調整", "", "_調整ボーン"),

        Item("左親指０", "", "指"),
        Item("左親指１", "thumb1_L", "指"),
        Item("左親指２", "thumb2_L", "指"),
        Item("左人指１", "fore1_L", "指"),
        Item("左人指２", "fore2_L", "指"),
        Item("左人指３", "fore3_L", "指"),
        Item("左中指１", "middle1_L", "指"),
        Item("左中指２", "middle2_L", "指"),
        Item("左中指３", "middle3_L", "指"),
        Item("左薬指１", "third1_L", "指"),
        Item("左薬指２", "third2_L", "指"),
        Item("左薬指３", "third3_L", "指"),
        Item("左小指１", "little1_L", "指"),
        Item("左小指２", "little2_L", "指"),
        Item("左小指３", "little3_L", "指"),
        Item("右親指０", "", "指"),
        Item("右親指１", "thumb1_R", "指"),
        Item("右親指２", "thumb2_R", "指"),
        Item("右人指１", "fore1_R", "指"),
        Item("右人指２", "fore2_R", "指"),
        Item("右人指３", "fore3_R", "指"),
        Item("右中指１", "middle1_R", "指"),
        Item("右中指２", "middle2_R", "指"),
        Item("右中指３", "middle3_R", "指"),
        Item("右薬指１", "third1_R", "指"),
        Item("右薬指２", "third2_R", "指"),
        Item("右薬指３", "third3_R", "指"),
        Item("右小指１", "little1_R", "指"),
        Item("右小指２", "little2_R", "指"),
        Item("右小指３", "little3_R", "指"),

        Item("腰", "waist", '体(下)'),
        Item("下半身", "lower body", "体(下)"),

        Item("左足", "leg_L", "足"),
        Item("左ひざ", "knee_L", "足"),
        Item("左足首", "ankle_L", "足"),
        Item("左足先", "toe2_L", "足"),
        Item("左つま先", "", "足"),
        Item("右足", "leg_R", "足"),
        Item("右ひざ", "knee_R", "足"),
        Item("右足首", "ankle_R", "足"),
        Item("右足先", "toe2_R", "足"),
        Item("右つま先", "", "足"),
        Item("左足D", "", "足"),
        Item("左ひざD", "", "足"),
        Item("左足首D", "", "足"),
        Item("左足先EX", "", "足"),
        Item("右足D", "", "足"),
        Item("右ひざD", "", "足"),
        Item("右足首D", "", "足"),
        Item("右足先EX", "", "足"),

        Item("足_親指1.L", "Toe_Thumb1.L", "足指"),
        Item("足_親指2.L", "Toe_Thumb2.L", "足指"),
        Item("足_人差指1.L", "Toe_IndexFinger1.L", "足指"),
        Item("足_人差指2.L", "Toe_IndexFinger2.L", "足指"),
        Item("足_中指1.L", "Toe_MiddleFinger1.L", "足指"),
        Item("足_中指2.L", "Toe_MiddleFinger2.L", "足指"),
        Item("足_薬指1.L", "Toe_RingFinger1.L", "足指"),
        Item("足_薬指2.L", "Toe_RingFinger2.L", "足指"),
        Item("足_小指1.L", "Toe_LittleFinger1.L", "足指"),
        Item("足_小指2.L", "Toe_LittleFinger2.L", "足指"),
        Item("足_親指1.R", "Toe_Thumb1.R", "足指"),
        Item("足_親指2.R", "Toe_Thumb2.R", "足指"),
        Item("足_人差指1.R", "Toe_IndexFinger1.R", "足指"),
        Item("足_人差指2.R", "Toe_IndexFinger2.R", "足指"),
        Item("足_中指1.R", "Toe_MiddleFinger1.R", "足指"),
        Item("足_中指2.R", "Toe_MiddleFinger2.R", "足指"),
        Item("足_薬指1.R", "Toe_RingFinger1.R", "足指"),
        Item("足_薬指2.R", "Toe_RingFinger2.R", "足指"),
        Item("足_小指1.R", "Toe_LittleFinger1.R", "足指"),
        Item("足_小指2.R", "Toe_LittleFinger2.R", "足指"),
    ]


def get_common_frame_names():
    return ["センター", "ＩＫ", "体(上)", "腕", "_調整ボーン", "指", "体(下)", "足", "足指", "物理", "その他"]
