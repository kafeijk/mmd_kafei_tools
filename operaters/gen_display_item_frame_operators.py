from collections import OrderedDict

from ..utils import *


class GenDisplayItemFrameOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.gen_display_item_frame"
    bl_label = "生成"
    # todo 引导用户在空场景下执行，空场景下2个pmx要20s，非空场景测了下2个要120s，待后续调查
    bl_description = "生成显示枠，如果同一目录下（不含级联）存在多个符合条件的文件，只会处理修改时间最新的那个文件"
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
        directory = batch.directory
        abs_path = bpy.path.abspath(directory)
        threshold = batch.threshold
        suffix = batch.suffix
        if batch_flag:
            get_collection(TMP_COLLECTION_NAME)
            start_time = time.time()
            file_list = recursive_search(abs_path, suffix, threshold)
            file_count = len(file_list)
            for index, filepath in enumerate(file_list):
                file_base_name = os.path.basename(filepath)
                ext = os.path.splitext(filepath)[1]
                new_filepath = os.path.splitext(filepath)[0] + suffix + ext
                curr_time = time.time()
                import_pmx(filepath)
                pmx_root = bpy.context.active_object
                gen_display_frame(pmx_root)
                export_pmx(new_filepath)
                clean_scene()
                print(
                    f"文件 \"{file_base_name}\" 处理完成，进度{index + 1}/{file_count}，耗时{time.time() - curr_time}秒，总耗时: {time.time() - start_time} 秒")
            print(f"目录\"{abs_path}\" 渲染完成，总耗时: {time.time() - start_time} 秒")
        else:
            active_object = bpy.context.active_object
            pmx_root = find_ancestor(active_object)
            gen_display_frame(pmx_root)

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


def gen_display_frame(pmx_root):
    """生成显示枠"""
    mmd_root = pmx_root.mmd_root
    armature = find_pmx_armature(pmx_root)

    # 激活骨架对象并进入姿态模式
    show_object(armature)
    deselect_all_objects()
    select_and_activate(armature)
    bpy.ops.object.mode_set(mode='POSE')

    # 骨骼jp名称 -> 是否处理完毕
    jp_processed_map = {}
    # 骨骼jp名称 -> 骨骼
    jp_bone_map = {}
    # 骨骼jp名称 -> 骨骼blender名称
    jp_bl_map = {}
    # 骨骼blender名称 -> 骨骼jp名称
    bl_jp_name_map = {}

    # 构建字典
    for bone in armature.pose.bones:
        jp_bone_map[bone.mmd_bone.name_j] = bone
        bl_jp_name_map[bone.name] = bone.mmd_bone.name_j
        jp_bl_map[bone.mmd_bone.name_j] = bone.name
        # 操作中心在root显示枠中，默认true
        jp_processed_map[bone.mmd_bone.name_j] = False
    # 常用显示枠内元素预设
    common_items = get_common_items()
    # 常用显示枠内元素jp名称预设
    common_item_jp_names = [item.jp_name for item in common_items]
    # 常用显示枠 -> 常用显示枠内元素
    frame_items = OrderedDict()
    for common_item in common_items:
        if common_item.display_panel not in frame_items:
            frame_items[common_item.display_panel] = []
        frame_items[common_item.display_panel].append(common_item.jp_name)

    # 重置已有显示枠及显示枠内元素 # todo 表情是否处理下，如果有没有添加进来的表情则添加进来？
    bpy.ops.mmd_tools.display_item_quick_setup(type='RESET')
    # 载入面部项目
    bpy.ops.mmd_tools.display_item_quick_setup(type='FACIAL')
    # 清除root显示枠内元素
    root_frame = mmd_root.display_item_frames[0]
    root_frame.data.clear()

    # 新建显示枠
    common_frame_names = get_common_frame_names()
    for common_frame_name in common_frame_names:
        add_frame(pmx_root, common_frame_name)

    # 添加显示枠内元素（操作中心）
    mmd_root.active_display_item_frame = 0
    view_center_bl = jp_bl_map.get('操作中心', None)
    if view_center_bl:
        bpy.ops.pose.select_all(action='DESELECT')
        add_item(armature, [view_center_bl], jp_processed_map)
    # 添加显示枠内元素（常用）
    add_item_common(mmd_root, armature, jp_bone_map, jp_bl_map, jp_processed_map, frame_items)
    # 添加显示枠内元素（物理）
    rigid_group = find_rigid_group(pmx_root)
    if rigid_group:
        add_item_physical(mmd_root, rigid_group, armature, jp_bl_map, bl_jp_name_map, jp_processed_map,
                          common_item_jp_names)
    # 添加显示枠内元素（剩余未添加的骨骼）
    add_item_other(armature, jp_bl_map, mmd_root, jp_processed_map)
    # 移除不包含元素的显示枠
    remove_frame(mmd_root)
    # 结束时回到物体模式
    bpy.ops.object.mode_set(mode='OBJECT')


def add_item_common(mmd_root, armature, jp_bone_map, jp_bl_map, jp_processed_map, frame_items):
    """添加显示枠内元素（常用）"""
    frames = mmd_root.display_item_frames
    # 跳过root和表情的显示枠
    frame_range = range(2, len(frames))
    for i in frame_range:
        frame = frames[i]
        jp_names = frame_items.get(frame.name, None)
        # 如"物理"，"その他"等显示枠元素不一定存在于frame_map中
        if jp_names is None:
            continue
        mmd_root.active_display_item_frame = i

        items = []
        for jp_name in jp_names:
            bone = jp_bone_map.get(jp_name, None)
            # 常用预设中的骨骼并不一定存在于当前骨架中
            if bone is None:
                continue
            items.append(jp_bl_map[jp_name])
        add_item(armature, items, jp_processed_map)


def add_frame(pmx_root, frame_name):
    """增加指定名称的显示枠"""
    bpy.ops.mmd_tools.display_item_frame_add()
    index = pmx_root.mmd_root.active_display_item_frame
    pmx_root.mmd_root.display_item_frames[index].name = frame_name


def add_item_other(armature, jp_bl_name_map, mmd_root, processed_bones):
    """添加显示枠内元素（剩余未添加的骨骼）"""
    # 其它未添加的内容
    items = []

    # 寻找'その他'显示枠并激活
    frames = mmd_root.display_item_frames
    for i, frame in enumerate(frames):
        if frame.name != 'その他':
            continue
        mmd_root.active_display_item_frame = i

    # 取消骨骼选中如果每次循环都调用的话，非常浪费时间，这里仅每次处理前调用一次
    bpy.ops.pose.select_all(action='DESELECT')
    for processing_bone, flag in processed_bones.items():
        if flag:
            continue
        items.append(jp_bl_name_map[processing_bone])

    # 按照pose bone的顺序对骨骼排序
    pose_bones = armature.pose.bones
    items.sort(
        key=lambda bone_name: pose_bones.find(bone_name)
    )

    add_item(armature, items, processed_bones)


def remove_frame(mmd_root):
    """如果显示枠内无元素，则移除该显示枠（跳过root和表情的显示枠）"""
    frames = mmd_root.display_item_frames
    for i in range(len(frames) - 1, 1, -1):
        if not frames[i].data:
            frames.remove(i)


def add_item_physical(mmd_root, rigid_grp_obj, armature, jp_bl_name_map,
                      bl_jp_name_map, processed_bones, common_bone_jp_names):
    """添加显示枠内元素（物理），需要屏蔽blender中骨骼名称对jp骨骼名称排序的影响"""
    rigid_bodies = rigid_grp_obj.children
    # 受刚体物理影响的骨骼名称列表（blender名称）
    affected_bone_bl_names = []
    for rigid_body in rigid_bodies:
        # 存在有刚体但没有关联骨骼的情况
        if rigid_body.mmd_rigid.bone == '':
            continue
        # common时处理过的这里不处理
        if processed_bones[bl_jp_name_map[rigid_body.mmd_rigid.bone]]:
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
    frames = mmd_root.display_item_frames
    physical_frame_index = -1
    for i in range(len(frames)):
        if frames[i].name != '物理':
            continue
        physical_frame_index = i

    mmd_root.active_display_item_frame = physical_frame_index
    add_item(armature, affected_bone_bl_names, processed_bones)


def find_rigid_group(root):
    """寻找刚体对象"""
    return next(filter(lambda o: o.type == 'EMPTY' and o.mmd_type == 'RIGID_GRP_OBJ', root.children), None)


def add_item(armature, items, processed_bones):
    """添加显示枠内元素"""
    # 取消骨骼选中，如果每次循环都调用的话，非常浪费时间，这里仅每次循环前调用一次
    bpy.ops.pose.select_all(action='DESELECT')
    for item in items:
        do_add_item(armature, item, processed_bones)


def do_add_item(armature, item, processed_bones):
    """添加显示枠内元素"""
    # 选中并激活目标骨骼
    bone = armature.pose.bones[item]
    bone.bone.select = True
    armature.data.bones.active = bone.bone
    # 添加为显示枠内元素
    bpy.ops.mmd_tools.display_item_add()
    # 标记骨骼已添加到显示枠中
    processed_bones[bone.mmd_bone.name_j] = True
    # 取消选中和激活状态
    bone.bone.select = False
    armature.data.bones.active = None


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
        Item("センター2", "", "センター"),
        Item("グルーブ", "groove", 'センター'),
        Item("グルーブ2", "", 'センター'),

        Item("左足IK親", "leg IKP_L", 'ＩＫ'),
        Item("左足ＩＫ", "leg IK_L", "ＩＫ"),
        Item("左つま先ＩＫ", "toe IK_L", "ＩＫ"),
        Item("左足先ＩＫ", "toe2 IK_L", "ＩＫ"),
        Item("右足IK親", "leg IKP_R", 'ＩＫ'),
        Item("右足ＩＫ", "leg IK_R", 'ＩＫ'),
        Item("右つま先ＩＫ", "toe IK_R", "ＩＫ"),
        Item("右足先ＩＫ", "toe2 IK_R", "ＩＫ"),

        Item("上半身", "upper body", "体(上)"),
        Item("上半身2", "upper body", "体(上)"),
        Item("上半身3", "upper body", "体(上)"),
        Item("首", "neck", "体(上)"),
        Item("頭", "head", "体(上)"),
        Item("左目", "eye_L", "体(上)"),
        Item("右目", "eye_R", "体(上)"),
        Item("両目", "eyes", "体(上)"),

        Item("左胸", "", "胸"),
        Item("左胸1", "", "胸"),
        Item("左胸2", "", "胸"),
        Item("左胸変形", "", "胸"),
        Item("右胸", "", "胸"),
        Item("右胸1", "", "胸"),
        Item("右胸2", "", "胸"),
        Item("右胸変形", "", "胸"),

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
        Item("右手捩調整", "", "_調整ボーン"),
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

        Item("tongue01", "tongue01", "舌"),
        Item("tongue02", "tongue02", "舌"),
        Item("tongue03", "tongue03", "舌"),
        Item("tongue04", "tongue04", "舌")

    ]


def get_common_frame_names():
    return ["センター", "ＩＫ", "体(上)", "胸", "腕", "_調整ボーン", "指", "体(下)", "足", "足指", "舌", "物理", "その他"]
