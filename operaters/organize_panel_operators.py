from collections import defaultdict

from ..utils import *


class OrganizePanelOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.organize_panel"
    bl_label = "执行"
    bl_description = "整理面板"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_organize_panel
        if not self.check_props(props):
            return
        batch = props.batch
        batch_flag = batch.flag
        if batch_flag:
            batch_process(organize_panel, props, f_flag=False)
        else:
            active_object = bpy.context.active_object
            pmx_root = find_ancestor(active_object)
            organize_panel(pmx_root, props)

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


def organize_panel(pmx_root, props):
    reorder_bone_panel(pmx_root, props)
    reorder_morph_panel(pmx_root, props)
    reorder_rigid_body_panel(pmx_root, props)
    reorder_display_panel(pmx_root, props)


def reorder_bone_panel(pmx_root, props):
    """
    整理骨骼面板

    在预设中的骨骼：
        主要按照预设顺序排序，过程中会参考父级赋予亲等关系进行修正
    不在预设中的骨骼：
        按照原来的相对顺序输出

    处理可以修复因预设导致的排序错误，但如果涉及到排序本身就有问题（逻辑错误，如亲的变形阶层大于子的变形阶层），则无法处理

    pe和blender中，对于骨骼的排序不一样，pe中是按照层分组，blender是按照兄弟分组。
    其中，受物理影响的骨骼，是MMD模型制作者调整过的，这部分内容，后续使用者和修改者基本上用不到,
    为了保持分组模式的统一（即按层分组），需要参考已有的排序，而不是pose.bones的顺序
    """
    bone_panel_flag = props.bone_panel_flag
    if bone_panel_flag is False:
        return

    armature = find_pmx_armature(pmx_root)
    objs = find_pmx_objects(armature)

    # 首个拥有骨架修改器的Mesh对象
    pmx_obj = next((obj for obj in objs if obj.modifiers.get('mmd_bone_order_override')), objs[0])
    # 顶点组名称列表
    vgs = get_vgs(pmx_obj)
    vgs_dict = {value: index for index, value in enumerate(vgs)}

    # 构建字典
    jp_bl_map = {}  # 骨骼jp名称 -> 骨骼blender名称
    bl_jp_map = {}  # 骨骼blender名称 -> 骨骼jp名称
    child_parent_map = {}  # 子骨骼 -> 父骨骼
    parent_children_map = {}  # 父骨骼 -> 子骨骼列表
    additional_parent_children_map = {}  # 赋予骨 -> 被赋予骨列表
    preset_bones = []  # 在预设中的骨骼名称
    non_preset_bones = []  # 不在预设中的骨骼名称

    for bone in armature.pose.bones:
        jp_name = bone.mmd_bone.name_j
        bl_name = bone.name
        if is_not_dummy_bone(bl_name):
            bl_jp_map[bl_name] = jp_name
            jp_bl_map[jp_name] = bl_name

            if jp_name in BONE_PANEL_ORDERS:
                preset_bones.append(jp_name)
            else:
                non_preset_bones.append(jp_name)
    for bone in armature.pose.bones:
        mmd_bone = bone.mmd_bone
        jp_name = mmd_bone.name_j
        bl_name = bone.name
        if is_not_dummy_bone(bl_name):
            if bone.parent:
                child_parent_map[bone] = bone.parent
            if bone.children:
                parent_children_map[jp_name] = [bl_jp_map[b.name] for b in bone.children if is_not_dummy_bone(b.name)]
            if mmd_bone.additional_transform_bone != '':
                additional_parent_jp_name = bl_jp_map[mmd_bone.additional_transform_bone]
                if additional_parent_children_map.get(additional_parent_jp_name, None):
                    additional_parent_children_map[additional_parent_jp_name].append(jp_name)
                else:
                    additional_parent_children_map[additional_parent_jp_name] = [jp_name]

    # 根据预设骨骼的相对顺序对existed_names排序
    bone_order_dict = {value: index for index, value in enumerate(BONE_PANEL_ORDERS)}
    preset_bones.sort(key=lambda x: bone_order_dict.get(x, 666888))

    # 遍历亲子关系，检测是否合法，如果不合法，则将亲及其parent移动到子骨前面
    for child, parent in child_parent_map.items():
        child_jp_name = bl_jp_map[child.name]
        parent_jp_name = bl_jp_map[parent.name]
        if child_jp_name in preset_bones and parent_jp_name in non_preset_bones:
            repair_relationship(armature, preset_bones, non_preset_bones, bone_order_dict, parent_jp_name,
                                child_jp_name, parent_children_map, jp_bl_map, bl_jp_map)

    # 如果赋予亲是被赋予骨的祖先，则上一步可顺带完成修复
    # 如果赋予亲是被赋予骨的子骨，则逻辑上本身就有问题，不予处理
    # 如果赋予亲和被赋予骨无亲子关系，则需要在这里进行处理

    # 遍历列表，检测其与赋予亲是否合法，如果不合法，则将赋予亲及其parent移动到被赋予骨前面
    for preset_name in preset_bones:
        pb = armature.pose.bones.get(jp_bl_map[preset_name], None)  # 这里pb肯定不为None
        mmd_bone = pb.mmd_bone
        # 获取预设骨骼赋予亲
        additional_parent_bl_name = mmd_bone.additional_transform_bone
        if additional_parent_bl_name == '':
            continue
        additional_parent_jp_name = bl_jp_map[additional_parent_bl_name]
        # 如果预设骨骼赋予亲在非预设列表中
        if additional_parent_jp_name in non_preset_bones:
            repair_relationship(armature, preset_bones, non_preset_bones, bone_order_dict, additional_parent_jp_name,
                                preset_name, additional_parent_children_map, jp_bl_map, bl_jp_map)

    # 不在预设中的骨骼，保持原始顺序
    non_preset_bones.sort(key=lambda x: vgs_dict.get(jp_bl_map[x], 666888))

    # 最终骨骼排序列表
    final_order_bones = preset_bones + non_preset_bones

    # 创建临时物体
    collection = pmx_obj.users_collection[0]
    tmp_obj = create_tmp_obj(armature, collection)

    # 为临时对象添加顶点组
    for jp_name in final_order_bones:
        tmp_obj.vertex_groups.new(name=jp_bl_map[jp_name])

    # 为物体添加顶点组
    # 通常情况下，只需要为第一个物体预先设置顶点组即可
    # 但是如果后续逻辑涉及到权重转换，或者是使用者修改了物体的顺序时，都可能会产生问题
    # 稳妥起见，为所有物体都设置上相应的顶点组
    for obj in objs:
        visibility = record_visibility(obj)
        show_object(obj)
        obj_name = obj.name
        current_tmp_obj = copy_obj(tmp_obj)
        # 将物体修改器拷贝到临时物体上以防丢失
        deselect_all_objects()
        select_and_activate(current_tmp_obj)
        select_and_activate(obj)
        bpy.ops.object.make_links_data(type='MODIFIERS')
        # 合并物体
        deselect_all_objects()
        select_and_activate(obj)
        select_and_activate(current_tmp_obj)
        bpy.ops.object.join()
        current_obj = bpy.context.active_object
        current_obj.name = obj_name
        set_visibility(current_obj, visibility)

    # 删除临时对象
    bpy.data.objects.remove(tmp_obj)


def repair_relationship(armature, existed_names, not_existed_names, bone_order_dict, parent_jp_name, child_jp_name,
                        parent_children_map, jp_bl_map, bl_jp_map):
    child_bl_name = jp_bl_map[child_jp_name]
    parent_bl_name = jp_bl_map[parent_jp_name]
    child_pb = armature.pose.bones.get(child_bl_name, None)  # 这里pb肯定不为None
    parent_pb = armature.pose.bones.get(parent_bl_name, None)  # 这里pb肯定不为None
    # 获取parent的所有子骨
    children = parent_children_map[parent_jp_name]
    # 将所有子骨按照预设顺序排序
    children.sort(key=lambda x: bone_order_dict.get(x, 6666))

    is_valid = is_parent_valid_by_id(child_pb, parent_pb)
    # 合法则跳过
    if is_valid:
        return
    # 不合法则将赋予亲及其parent移动到被赋予骨前面
    first_child_jp_name = children[0]
    ancestors = get_ancestors(parent_pb, True)
    for ancestor in ancestors:
        bl_name = ancestor.name
        jp_name = bl_jp_map[bl_name]
        if jp_name in existed_names:
            continue
        not_existed_names.remove(jp_name)
        index = existed_names.index(first_child_jp_name)
        existed_names.insert(index, jp_name)


def is_parent_valid_by_id(child, additional_parent):
    """在骨骼ID已知的情况下（前者小于后者）校验赋予亲顺序是否合法"""
    cm = child.mmd_bone
    apm = additional_parent.mmd_bone

    if cm.transform_after_dynamics == apm.transform_after_dynamics:
        if child.mmd_bone.transform_order > additional_parent.mmd_bone.transform_order:
            return True
        else:
            return False
    if cm.transform_after_dynamics:
        return True
    return False


def get_ancestors(pose_bone, include_self=False):
    ancestors = []

    # 如果 include_self 为 True，首先添加自身
    if include_self:
        ancestors.insert(0, pose_bone)

    current_bone = pose_bone

    # 逐级向上遍历父骨骼
    while current_bone.parent:
        current_bone = current_bone.parent
        ancestors.insert(0, current_bone)

    return ancestors


def is_not_dummy_bone(name):
    return not name.startswith("_dummy_") and not name.startswith("_shadow_")


def get_vgs(obj):
    """获取顶点组名称列表"""
    if obj and obj.type == 'MESH':
        vgs = obj.vertex_groups
        vg_names = [vg.name for vg in vgs]
        return vg_names
    else:
        return []


def reorder_morph_panel(pmx_root, props):
    """
    整理表情面板。

    各分类面板内，预设表情按照相对顺序置顶。

    预设构成
        - 目：tda常用内容
        - 嘴：あいうえおん置顶 + あいうえおん差分 + tda常用内容 + tda常用内容差分（差分为原表情与半角0-9/全角０-９之间的所有组合）
        - 眉：tda常用内容
        - 其它：tda常用内容
    预设外其余表情
        - 目：按名称排序
        - 嘴：按名称排序
        - 眉：按名称排序
        - 其它：如果含有指定名称后缀（如XXめる, XX消等），则将这些内容按照后缀分组，组内按名称排序，将分组内容置底，再将剩余的表情按名称排序置于中间位置
    名称排序时，左优先于右
    """
    morph_panel_flag = props.morph_panel_flag
    if morph_panel_flag is False:
        return

    mmd_root = pmx_root.mmd_root

    # 获取表情内容，按照面板分组
    panel_morphs_map = defaultdict(list)
    MORPH_TYPES = ['group_morphs', 'vertex_morphs', 'bone_morphs', 'uv_morphs', 'material_morphs']
    for morph_type in MORPH_TYPES:
        morphs = getattr(mmd_root, morph_type)
        for morph in morphs:
            morph_name = morph.name
            panel_morphs_map[morph.category].append((morph_name, morph.category, morph_type))

    # 面板分组内表情排序，然后按照 EYE,MOUTH,EYEBROW,OTHER,SYSTEM 的顺序合并
    # categories = ['SYSTEM', 'EYEBROW', 'EYE', 'MOUTH', 'OTHER']
    for category, morphs in panel_morphs_map.items():
        if category == 'EYE':
            sort_morphs(morphs, get_eye_preset())
        if category == 'MOUTH':
            sort_morphs(morphs, get_mouth_preset())
        if category == 'EYEBROW':
            sort_morphs(morphs, get_eyebrow_preset())
        if category == 'OTHER':
            sort_other_morphs(morphs, get_other_preset())
    final_morphs = panel_morphs_map['EYE'] + panel_morphs_map['MOUTH'] + panel_morphs_map['EYEBROW'] + panel_morphs_map[
        'OTHER'] + panel_morphs_map['SYSTEM']

    # 记录激活状态
    active_morph_type = mmd_root.active_morph_type
    # 表情重排序
    for morph in final_morphs:
        morph_type = morph[2]
        # 激活表情类型面板
        mmd_root.active_morph_type = morph_type
        # 获取表情当前索引
        morphs = getattr(mmd_root, morph_type)
        morpy_name = morph[0]
        index = next((i for i, m in enumerate(morphs) if m.name == morpy_name), None)
        if index is None:
            continue
        # 激活表情
        mmd_root.active_morph = index
        bpy.ops.mmd_tools.morph_move(type='BOTTOM')
    mmd_root.active_morph_type = active_morph_type


def get_mouth_preset():
    """口型表情预设"""
    lip_preset_list = []

    main_preset_list = ['あ', 'い', 'う', 'え', 'お', 'ん']
    other_preset_list = ['▲', '∧', '□', 'ワ', 'ω', 'ω□', 'にやり', 'にっこり', 'ぺろっ', 'てへぺろ', '口角上げ',
                         '口角下げ', '口横広げ', '歯無し上', '歯無し下', 'ハンサム']
    half_width_digits = [str(i) for i in range(0, 10)]
    full_width_digits = [chr(i) for i in range(ord('０'), ord('９') + 1)]

    def append_morphs(preset_list, include=False):
        for morph in preset_list:
            if include:
                lip_preset_list.append(morph)
            for index, full_width_digit in enumerate(full_width_digits):
                half_width_digit = half_width_digits[index]
                lip_preset_list.append(morph + half_width_digit)
                lip_preset_list.append(morph + full_width_digit)

    # あいうえおん置顶
    lip_preset_list.extend(main_preset_list)
    # あいうえおん差分表情
    append_morphs(main_preset_list)
    # 其它预设表情及差分
    append_morphs(other_preset_list, include=True)
    return lip_preset_list


def get_eye_preset():
    """眼睛表情预设"""
    main_preset_list = ['まばたき', '笑い', 'ウィンク', 'ウィンク右', 'ウィンク２', 'ウィンク２右', 'ｳｨﾝｸ２右', 'なごみ',
                        'はぅ', 'びっくり', 'じと目', 'ｷﾘｯ', '瞳小', '瞳縦潰れ', '光下', 'ハイライト消', '映り込み消',
                        '恐ろしい子！', 'はちゅ目', '星目', 'はぁと', 'はちゅ目縦潰れ', 'はちゅ目横潰れ']
    return main_preset_list


def get_eyebrow_preset():
    """眉毛表情预设"""
    main_preset_list = ['真面目', '困る', 'にこり', '怒り', '上', '下', '前', '眉頭左', '眉頭右']
    return main_preset_list


def get_other_preset():
    """其它表情预设"""
    main_preset_list = ['照れ', '涙', 'がーん', 'みっぱい', 'メガネ']
    return main_preset_list


def sort_morphs(morphs, preset_list):
    """表情排序，预设内容置顶，其余内容按名称排序"""
    preset_set = set(preset_list)
    preset_dict = {value: index for index, value in enumerate(preset_list)}

    # 剔除预设外元素
    remaining = []
    for morph in reversed(morphs):
        if morph[0] in preset_set:
            continue
        remaining.append(morph)
        morphs.remove(morph)
    # 预设内元素排序
    morphs.sort(key=lambda x: preset_dict.get(x[0], 666888))
    # 预设外元素排序
    remaining.sort(key=lambda x: x[0].replace('左', '史'))
    # 添加预设外元素
    morphs.extend(remaining)


def sort_other_morphs(morphs, preset_list):
    """その他表情排序，预设内容置顶，分组内容置底，其余内容置于中间"""
    preset_set = set(preset_list)
    preset_dict = {value: index for index, value in enumerate(preset_list)}

    # 分组后缀
    suffixes = ['める', '消', '未使用']
    suffix_morphs_map = OrderedDict()
    for suffix in suffixes:
        suffix_morphs_map[suffix] = []

    # 剔除预设外元素
    remaining1 = []
    for morph in reversed(morphs):
        if morph[0] in preset_set:
            continue
        remaining1.append(morph)
        morphs.remove(morph)
    # 预设内元素排序
    morphs.sort(key=lambda x: preset_dict.get(x[0], 666888))

    # 元素分类
    remaining2 = []
    for morph in remaining1:
        morph_name = morph[0]
        for suffix in suffixes:
            if morph_name.endswith(suffix):
                suffix_morphs_map[suffix].append(morph)
            else:
                remaining2.append(morph)
    # 分类元素排序
    for suffix, ms in suffix_morphs_map.items():
        ms.sort(key=lambda x: x[0].replace('左', '史'))

    # 剩余元素排序
    remaining2.sort(key=lambda x: x[0].replace('左', '史'))

    # 最终排序结果
    morphs.extend(remaining2)
    for suffix, ms in suffix_morphs_map.items():
        morphs.extend(ms)


def reorder_rigid_body_panel(pmx_root, props):
    """
    整理刚体面板

    如果同一不冲突群组内均为追踪骨骼类型的刚体，则将他们按照关联骨骼顺序排序，如果具有相同关联骨骼，则按照名称排序。
    然后将他们整体移动到该类型首次出现的位置。
    其他情况下：
     - 物理刚体按名称排序？各个模型刚体名称不规范，不适用
     - 物理刚体按不冲突群组排序，组内不变？即使刚体处于同一层（参数一致），所属冲突组也有可能不同，不适用
    综上所述，不作改动
    """
    rigid_body_panel_flag = props.rigid_body_panel_flag
    if rigid_body_panel_flag is False:
        return

    armature = find_pmx_armature(pmx_root)
    objs = find_pmx_objects(armature)

    # 首个拥有骨架修改器的Mesh对象
    pmx_obj = next((obj for obj in objs if obj.modifiers.get('mmd_bone_order_override')), objs[0])
    # 顶点组名称列表
    vgs = get_vgs(pmx_obj)
    vgs_dict = {value: index for index, value in enumerate(vgs)}

    # 激活骨架对象
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode='OBJECT')
    show_object(armature)
    deselect_all_objects()
    select_and_activate(armature)

    # 获取刚体
    rigid_body_parent = find_rigid_body_parent(pmx_root)
    if rigid_body_parent is None:
        return
    rigid_bodies = rigid_body_parent.children
    if not rigid_bodies:
        return

    # 初始化刚体顺序map
    rigid_body_order_map = OrderedDict()
    rigid_body_any_physical_map = {}
    for i in range(16):
        rigid_body_order_map[i] = []
        rigid_body_any_physical_map[i] = False

    # 记录分组内元素
    final_order_list = []
    for rigid_body in rigid_bodies:
        mmd_rigid = rigid_body.mmd_rigid
        if not mmd_rigid:
            continue
        final_order_list.append(rigid_body)
        collision_group_number = mmd_rigid.collision_group_number
        rigid_type = mmd_rigid.type
        rigid_body_order_map[collision_group_number].append(rigid_body)
        if rigid_type in ('1', '2'):
            rigid_body_any_physical_map[collision_group_number] = True

    def get_original_name(n):
        m = RIGID_BODY_PREFIX_REGEXP.match(n)
        name = m.group('name') if m else n
        return name

    # 追踪骨骼类型刚体排序
    for number, rigid_bodies in rigid_body_order_map.items():
        if not rigid_bodies:
            continue
        any_physical = rigid_body_any_physical_map[number]
        if any_physical:
            continue
        rigid_bodies.sort(key=lambda x: (vgs_dict.get(x.mmd_rigid.bone, 666888), get_original_name(x.name)))

        last_removed_index = -1
        for i in range(len(final_order_list) - 1, -1, -1):
            a = final_order_list[i]
            for b in rigid_bodies:
                if a.name == b.name:
                    final_order_list.pop(i)
                    last_removed_index = i
                    break
        if last_removed_index != -1:
            final_order_list[last_removed_index:last_removed_index] = rigid_bodies

    def set_index(obj, index):
        m = RIGID_BODY_PREFIX_REGEXP.match(obj.name)
        name = m.group('name') if m else obj.name
        obj.name = '%s_%s' % (int2base(index, 36, 3), name)

    for index, rigid_body in enumerate(final_order_list):
        set_index(rigid_body, index)


def reorder_display_panel(pmx_root, props):
    """整理显示枠面板"""
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


def reset_expression_frame(mmd_root):
    """重置表情显示枠"""
    frames = mmd_root.display_item_frames
    for i in range(len(frames) - 1, -1, -1):
        frame = frames[i]
        if frame.name == '表情':
            frames.remove(i)

    create_expression_frame(frames)


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
            frames.remove(i)

    frame_root = frames.add()
    frame_root.name = 'Root'
    frame_root.name_e = 'Root'
    frame_root.is_special = True

    frames.move(frames.find('Root'), 0)


def add_frame(pmx_root, frame_name):
    """增加指定名称的显示枠"""
    mmd_root = pmx_root.mmd_root
    frames = mmd_root.display_item_frames
    item, index = ItemOp.add_after(frames, len(frames) - 1)
    item.name = frame_name
    mmd_root.active_display_item_frame = index


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
