from enum import auto, Enum

import numpy as np

from ..utils import *

# 日文名称到Blender名称的映射
jp_bl_map = {}
# Blender名称到日文名称的映射
bl_jp_map = {}


class SsbStatus(Enum):
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


class SsbResult:
    def __init__(self, status, result=None, message=""):
        self.status = status
        self.result = result
        self.message = message


class SelectAllSsbOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_all_ssb"
    bl_label = "全部选择"
    bl_description = "全部选择"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_add_ssb
        base_props = props.base
        force = props.force

        # 获取base_props对象的所有属性名
        all_props = dir(base_props)

        exclude_names = ["enable_gen_frame_checked"]
        if force:
            exclude_names.append("thumb0_checked")
            exclude_names.append("enable_thumb_local_axes_checked")

        # 如果所有值都为True，则将所有值都设置为False；只要有一个值不为True，则将所有值设置为True；不含enable属性
        set_to_true = False
        for prop_name in all_props:
            if all(value not in prop_name for value in exclude_names) and isinstance(getattr(base_props, prop_name),
                                                                                     bool):
                # 如果有任何一个属性不为True，则将所有符合条件的属性都设置为True
                if not getattr(base_props, prop_name):
                    set_to_true = True
                    break
                # 否则将所有符合条件的属性设置为False
                else:
                    set_to_true = False
        for prop_name in all_props:
            if all(value not in prop_name for value in exclude_names) and isinstance(getattr(base_props, prop_name),
                                                                                     bool):
                setattr(base_props, prop_name, set_to_true)

        if force:
            base_props.thumb0_checked = False


def pre_set_panel_order(armature, props):
    """通过与临时物体合并的方式预先创建顶点组（对应PE中的骨骼面板）"""
    objs = find_pmx_objects(armature)
    if has_all_ssb(armature, props):
        return

    # pmx模型中首个拥有骨架修改器的Mesh类型对象
    pmx_obj = objs[0]
    for obj in objs:
        if obj.modifiers.get('mmd_bone_order_override', None):
            pmx_obj = obj
            break

    # 当前要添加的ssb对象
    curr_ssb_list = get_ssb_to_add(props)
    # 创建临时物体
    collection = pmx_obj.users_collection[0]
    tmp_obj = create_tmp_obj(armature, collection)

    # 设置面板中位于前面的顶点组
    for name_jp in SSB_ORDER_TOP_LIST:
        name_bl = convertNameToLR(name_jp)
        # 名称属于本次应添加的ssb 且 名称于临时物体顶点组中不存在 且 名称于源物体顶点组中不存在（防止出现骨骼面板顺序问题）
        if name_jp in curr_ssb_list and name_bl not in tmp_obj.vertex_groups and name_bl not in pmx_obj.vertex_groups:
            tmp_obj.vertex_groups.new(name=convertNameToLR(name_jp))
    # 设置面板中位于中间的顶点组
    for vg in pmx_obj.vertex_groups:
        vg_name_b = vg.name
        # 顶点组如果不在当前骨架中则跳过
        if vg_name_b not in bl_jp_map.keys():
            continue
        vg_name_j = bl_jp_map[vg.name]
        # 如果当前顶点组触发了关键词
        if vg_name_j in SSB_ORDER_MAP.keys():
            items = SSB_ORDER_MAP[vg_name_j]

            # 如果待添加的顶点组全部在源obj中存在，则只添加触发key的当前顶点组
            # （主要是用来防止有些模型在次标准骨骼之上进行二次修改以导致骨骼面板顺序问题）
            all_existed = True
            for item_name_j in items:
                item_name_b = convertNameToLR(item_name_j)
                if item_name_b not in pmx_obj.vertex_groups:
                    all_existed = False
                    break
            if all_existed:
                tmp_obj.vertex_groups.new(name=vg_name_b)
            else:
                for item_name_j in items:
                    item_name_b = convertNameToLR(item_name_j)
                    if item_name_b not in tmp_obj.vertex_groups:
                        tmp_obj.vertex_groups.new(name=item_name_b)
        else:
            if vg_name_b not in tmp_obj.vertex_groups:
                tmp_obj.vertex_groups.new(name=vg_name_b)
    # 设置面板中位于底部的顶点组
    for name_jp in SSB_ORDER_BOTTOM_LIST:
        if name_jp in curr_ssb_list and convertNameToLR(name_jp) not in tmp_obj.vertex_groups:
            tmp_obj.vertex_groups.new(name=convertNameToLR(name_jp))

    # 为物体添加顶点组
    # 通常情况下，只需要为第一个物体预先设置顶点组即可
    # 但是如果后续逻辑涉及到权重转换，或者是使用者修改了物体的顺序时，都可能会产生问题
    # 稳妥起见，为所有物体都设置上相应的顶点组
    for obj in objs:
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

    # 从集合中移除对象
    collection.objects.unlink(tmp_obj)
    # 从场景中删除对象
    bpy.data.objects.remove(tmp_obj, do_unlink=True)


def has_all_ssb(armature, props):
    curr_ssb_list = get_ssb_to_add(props)
    count = 0
    for pb in armature.pose.bones:
        if bl_jp_map[pb.name] in curr_ssb_list:
            count += 1
    if count == len(curr_ssb_list):
        return True
    return False


def has_all_ssb_without_extra(armature, props):
    curr_ssb_list = set(get_ssb_to_add(props)) & set(SSB_BASE_NAMES)
    count = 0
    for pb in armature.pose.bones:
        if bl_jp_map[pb.name] in curr_ssb_list:
            count += 1
    if count == len(curr_ssb_list):
        return True
    return False


def create_tmp_obj(armature, collection):
    # 新建Mesh并删除所有顶点
    bpy.ops.object.mode_set(mode='OBJECT')
    deselect_all_objects()
    bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=True)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='VERT')
    bpy.ops.object.mode_set(mode='OBJECT')
    tmp_obj = bpy.context.active_object
    tmp_obj.name = "tmp_plane"
    # 设置parent为armature
    tmp_obj.parent = armature
    move_to_target_collection_recursive(tmp_obj, collection)
    return tmp_obj


def post_set_panel_order(armature):
    """移除名称为ssb且骨架中不含该骨骼的顶点组"""
    objs = find_pmx_objects(armature)
    # 当前所有骨骼名称
    pb_names = {pb.name for pb in armature.pose.bones}
    # 移除多余的顶点组
    for obj in objs:
        vgs = obj.vertex_groups
        for i in range(len(vgs) - 1, -1, -1):
            vg_name = vgs[i].name
            if vg_name in SSB_NAMES and vg_name not in pb_names:
                vgs.remove(vgs[i])


def copy_obj(obj):
    new_mesh = obj.data.copy()
    new_obj = obj.copy()
    new_obj.data = new_mesh
    col = obj.users_collection[0]
    col.objects.link(new_obj)
    return new_obj


def create_tmp_bones(armature):
    if armature.mode != 'EDIT':
        deselect_all_objects()
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    # SSB最多有41个
    for i in range(41):
        edit_bone = armature.data.edit_bones.new(KAFEI_TMP_BONE_NAME)
        # 设置新骨骼的头尾位置，如果不设置或者头尾位置一致则无法创建成功（回物体模式后骨骼被移除了）
        edit_bone.head = (0, 0, 0)
        edit_bone.tail = (0, 0, 1)
    bpy.ops.object.mode_set(mode='OBJECT')


def get_tmp_bone(armature):
    return next((edit_bone for edit_bone in armature.data.edit_bones if KAFEI_TMP_BONE_NAME in edit_bone.name), None)


def hide_ssb(armature, props):
    base_props = props.base
    controllable = base_props.enable_leg_d_controllable_checked
    curr_ssb_list = get_ssb_to_add(props)
    if armature.mode != 'OBJECT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='OBJECT')
    for pb in armature.pose.bones:
        if pb.name in bl_jp_map.keys():
            name_jp = bl_jp_map[pb.name]
            if name_jp in curr_ssb_list and name_jp in SSB_HIDE_LIST and ('D' not in name_jp or not controllable):
                pb.bone.hide = True


def remove_tmp_bone(armature):
    if armature.mode != 'EDIT':
        deselect_all_objects()
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    # SSB最多有41个
    for eb in armature.data.edit_bones:
        if KAFEI_TMP_BONE_NAME in eb.name:
            armature.data.edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode='OBJECT')


def remove_ssb(armature, props):
    if not props.force:
        return

    if armature.mode != 'EDIT':
        deselect_all_objects()
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')

    # 本次应当添加的次标准骨骼
    ssb_list = get_ssb_to_add(props)

    # 移除ssb
    edit_bones = armature.data.edit_bones
    eb_name_bl_list = [eb.name for eb in edit_bones]
    for name_bl in eb_name_bl_list:
        # 排除临时骨骼对流程的干扰
        if name_bl not in bl_jp_map.keys():
            continue
        name_jp = bl_jp_map[name_bl]
        if name_jp in ssb_list:
            edit_bones.remove(edit_bones[name_bl])
            dummy_name_bl = '_dummy_' + name_bl
            shadow_name_bl = '_shadow_' + name_bl
            if dummy_name_bl in bl_jp_map.keys():
                edit_bones.remove(edit_bones[dummy_name_bl])
            if shadow_name_bl in bl_jp_map.keys():
                edit_bones.remove(edit_bones[shadow_name_bl])

    # 移除map中的ssb 移除显示枠
    pmx_root = find_pmx_root_with_child(armature)
    mmd_root = pmx_root.mmd_root
    frames = mmd_root.display_item_frames
    for name_jp in ssb_list:
        if name_jp not in jp_bl_map.keys():
            continue
        # 移除map中的ssb
        name_bl = jp_bl_map[name_jp]
        del bl_jp_map[name_bl]
        del jp_bl_map[name_jp]
        # 移除显示枠
        found_frame, found_item = find_bone_item(pmx_root, name_bl)
        if found_frame is not None and found_item is not None:
            frames[found_frame].data.remove(found_item)
    bpy.ops.object.mode_set(mode='OBJECT')


class AddSsbOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.add_ssb"
    bl_label = "执行"
    bl_description = "追加次标准骨骼，效果同PE"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self, props):
        armature_data = props.model
        batch = props.batch
        batch_flag = batch.flag
        if not batch_flag:
            if not armature_data:
                self.report(type={'ERROR'}, message=f'请选择MMD模型骨架！')
                return False
            pmx_armature = next(
                (obj for obj in bpy.data.objects if obj.type == 'ARMATURE' and obj.data == armature_data), None)
            if not pmx_armature:
                self.report(type={'ERROR'}, message=f'请选择MMD模型骨架！')
                return False
            pmx_root = find_pmx_root_with_child(pmx_armature)
            if not pmx_root:
                self.report(type={'ERROR'}, message=f'请选择MMD模型骨架！')
                return False
            objs = find_pmx_objects(pmx_armature)
            if len(objs) == 0:
                self.report(type={'ERROR'}, message=f'模型网格对象不存在！')
                return False
        else:
            if not check_batch_props(self, batch):
                return False
        return True

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_add_ssb
        start_time = time.time()

        # 参数校验
        if not self.check_props(props):
            return

        batch = props.batch
        batch_flag = batch.flag
        armature_data = props.model
        pmx_armature = next(
            (obj for obj in bpy.data.objects if obj.type == 'ARMATURE' and obj.data == armature_data), None)
        pmx_root = find_pmx_root_with_child(pmx_armature)

        if batch_flag:
            batch_process(self.create_ssb, props)
        else:
            results = self.create_ssb(pmx_root, props)
            duration = time.time() - start_time
            self.show_msg(pmx_armature, props, results, duration)

    def create_ssb(self, pmx_root, props):
        # 接收返回结果的列表
        results = []
        # 获取模型数据
        armature = find_pmx_armature(pmx_root)
        # 显示根节点与骨架，避免引起上下文异常
        show_object(pmx_root)
        show_object(armature)
        deselect_all_objects()
        select_and_activate(armature)

        # 根据当前骨架生成骨骼名称映射
        gen_bone_name_map(armature)

        # 如果本次所有要添加的次标准骨骼（不含额外创建的ssb）均已存在，且未勾选强制重建，则直接返回
        if has_all_ssb_without_extra(armature, props) and not props.force:
            return results

        # 根据force选项移除ssb
        remove_ssb(armature, props)

        # 在mmd插件中，模型的PE骨骼面板顺序是根据blender顶点组来决定的
        # 但是在blender中，移动顶点组是一项非常耗时的操作
        # 顶点组所在的集合类型并不像其它集合那样，拥有移动到指定位置的函数。需要我们模拟界面点击的方式一个一个循环移动到指定位置
        # 这里通过新建一个Mesh，并为其预先添加顶点组，然后用这个Mesh和原模型合并的方式来达到设置骨骼面板的目的
        pre_set_panel_order(armature, props)
        # 在创建ssb的过程中需要获取mmd_bone，这是一个pose_bone的属性，需要创建完edit_bone之后切换模式才能获取
        # 但是切换模式会造成edit_bone的数据失效，需要重新获取，造成代码冗余
        # 这里通过预先创建的方式维护一组tmp bone，需要时直接从中获取，并进行相应属性的赋予即可，从而达到创建ssb过程中始终保持EDIT模式
        # 补充说明：如果对edit bone改名，如果不切换模式，bone的hide属性失效（虽然能够获取bone）；mmd插件的调用也应该移动到后面防止意料外问题发生
        create_tmp_bones(armature)

        # 进入编辑模式，并确保添加ssb期间不涉及模式切换
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')

        # 腕弯曲骨骼
        create_arm_twist_bone(armature, props, results)
        # 手弯曲骨骼
        create_wrist_twist_bone(armature, props, results)
        # 上半身2
        create_upper_body2_bone(armature, props, results)
        # 腰骨骼
        create_waist_bone(armature, props, results)
        # 足IK親
        create_ik_p_bone(armature, props, results)
        # 足先EX
        create_ex_bone(armature, props, results)
        # 手持骨
        create_dummy_bone(armature, props, results)
        # グルーブ骨
        create_groove_bone(armature, props, results)
        # 肩P
        create_shoulder_p_bone(armature, props, results)
        # 大拇指０骨骼
        create_thumb0_bone(armature, props, results)
        # 全ての親
        create_root_bone(armature, props, results)
        # 操作中心
        create_view_center_bone(armature, props, results)
        # 移除名称为ssb且骨架中不含该骨骼的顶点组
        post_set_panel_order(armature)
        # 移除多余的临时骨骼
        remove_tmp_bone(armature)
        # 隐藏指定ssb
        hide_ssb(armature, props)

        # 返回物体模式
        bpy.ops.object.mode_set(mode='OBJECT')
        deselect_all_objects()
        select_and_activate(armature)

        # 装配骨骼（付与相关属性需要装配一次生效）
        bpy.ops.mmd_tools.apply_additional_transform()
        # 应用骨骼局部轴
        bpy.ops.mmd_tools.bone_local_axes_setup(type='APPLY')
        return results

    def show_msg(self, armature, props, results, duration):
        success_results = [result for result in results if result.status == SsbStatus.SUCCESS]
        failed_results = [result for result in results if result.status == SsbStatus.FAILED]
        success_msg = ''
        if len(success_results) > 0:
            success_msg += "以下骨骼追加完毕了：\n"
        for success_result in success_results:
            names = success_result.result
            success_msg = success_msg + str(names) + "\n"

        failed_msg = ''
        for failed_result in failed_results:
            names = failed_result.result
            failed_msg = failed_result.message
            if failed_msg:
                failed_msg = failed_msg + failed_msg + '\n'
            else:
                failed_msg = failed_msg + f"{names[0]}所需的{names[1:]}不存在" + "\n"

        if success_msg or failed_msg:
            if success_msg:
                self.report({'INFO'}, success_msg.rstrip())
            if failed_msg:
                self.report({'WARNING'}, failed_msg.rstrip())
            if failed_msg:
                self.report({'WARNING'}, f'追加次标准骨骼结束，耗时{duration:.2f}秒，点击查看报告↑↑↑')
            else:
                self.report({'INFO'}, f'追加次标准骨骼结束，耗时{duration:.2f}秒，点击查看报告↑↑↑')
        else:
            missing_bones = []
            ssb_list = get_ssb_to_add(props)
            pb_names = {bl_jp_map[pb.name] for pb in armature.pose.bones}
            for ssb_name in ssb_list:
                if ssb_name not in pb_names:
                    missing_bones.append(ssb_name)
            if len(missing_bones) == 0:
                self.report({'INFO'}, "所有次标准骨骼追加完成")
            else:
                self.report({'WARNING'}, f"缺失骨骼：{missing_bones}")
                self.report({'WARNING'}, "没有能追加的骨骼，请尝试“强制重建”选项。点击查看缺失骨骼↑↑↑")


def get_ssb_to_add(props):
    """根据用户参数，获取本次应当添加的次标准骨骼"""
    base_props = props.base
    bones = []
    if base_props.root_checked:
        bones.append('全ての親')
    if base_props.arm_twist_checked:
        bones.extend(["右腕捩", "右腕捩1", "右腕捩2", "右腕捩3"])
        bones.extend(["左腕捩", "左腕捩1", "左腕捩2", "左腕捩3"])
    if base_props.wrist_twist_checked:
        bones.extend(["右手捩", "右手捩1", "右手捩2", "右手捩3"])
        bones.extend(["左手捩", "左手捩1", "左手捩2", "左手捩3"])
    if base_props.upper_body2_checked:
        bones.append('上半身2')
    if base_props.groove_checked:
        bones.append('グルーブ')
    if base_props.waist_checked:
        bones.extend(["腰", "腰キャンセル右", "腰キャンセル左"])
    if base_props.ik_p_checked:
        bones.extend(["右足IK親", "左足IK親"])
    if base_props.view_center_checked:
        bones.append("操作中心")
    if base_props.ex_checked:
        bones.extend(["右足D", "右ひざD", "右足首D", "右足先EX", "左足D", "左ひざD", "左足首D", "左足先EX"])
    if base_props.dummy_checked:
        bones.extend(["右ダミー", "左ダミー"])
    if base_props.shoulder_p_checked:
        bones.extend(["右肩P", "右肩C", "左肩P", "左肩C"])
    if base_props.thumb0_checked:
        bones.extend(["右親指０", "左親指０"])
    return bones


def create_ex_bone(armature, props, results):
    base_props = props.base
    if not base_props.ex_checked:
        return

    ex_infos = [
        ("右足先EX", "toe2_R", "右足", "右ひざ", "右足首", "右つま先ＩＫ"),
        ("左足先EX", "toe2_L", "左足", "左ひざ", "左足首", "左つま先ＩＫ")
    ]
    for info in ex_infos:
        # 基本名称信息
        ex_jp = info[0]
        ex_en = info[1]
        ex_bl = convertNameToLR(ex_jp)
        leg_jp = info[2]
        knee_jp = info[3]
        ankle_jp = info[4]
        toe_ik_jp = info[5]

        # 先决条件校验
        if ex_jp in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[ex_jp]))
            continue
        required_bones = [leg_jp, knee_jp, ankle_jp, toe_ik_jp]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = [ex_jp]
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
            continue

        # todo 源码中controllable初始为False且并未看见被修改为True的逻辑，但实际上应该是取决于传入的参数
        controllable = base_props.enable_leg_d_controllable_checked

        # 常用参数获取
        scale = props.scale
        edit_bones = armature.data.edit_bones
        pose_bones = armature.pose.bones
        objs = find_pmx_objects(armature)

        # 补充名称信息（blender）
        leg_bl = jp_bl_map[leg_jp]
        knee_bl = jp_bl_map[knee_jp]
        ankle_bl = jp_bl_map[ankle_jp]
        toe_ik_bl = jp_bl_map[toe_ik_jp]
        # 补充骨骼信息
        ankle_eb = edit_bones[ankle_bl]
        toe_ik_d_eb = edit_bones[toe_ik_bl]

        # 创建D骨
        leg_d_jp, leg_d_bl, leg_d_eb = create_d_bone(armature, scale, leg_jp, controllable)
        knee_d_jp, knee_d_bl, knee_d_eb = create_d_bone(armature, scale, knee_jp, controllable)
        ankle_d_jp, ankle_d_bl, ankle_d_eb = create_d_bone(armature, scale, ankle_jp, controllable)
        # 创建EX骨
        ex_eb = create_bone_with_mmd_info(armature, ex_bl, ex_jp, ex_en)
        # 设置是否 可移动 可旋转 可操作
        set_movable(armature, ex_bl, False)
        set_rotatable(armature, ex_bl, True)
        set_controllable(armature, ex_bl, True)
        # 设置 head tail
        ex_eb.head = (1 - 2.0 / 3.0) * ankle_d_eb.head + 2.0 / 3.0 * toe_ik_d_eb.head
        ex_eb.tail = ex_eb.head + Vector((0, -1 * scale, 0))
        # 设置 parent
        knee_d_eb.parent = leg_d_eb
        ankle_d_eb.parent = knee_d_eb
        ex_eb.parent = ankle_d_eb
        # 设置EX骨变形阶层
        pose_bones.get(ex_bl).mmd_bone.transform_order = pose_bones.get(ankle_d_bl).mmd_bone.transform_order

        # 权重分配
        for obj in objs:
            for vertex in obj.data.vertices:
                if is_vertex_dedicated_by_bone(obj, vertex, ankle_bl, threshold=0.97):
                    center = (vertex.co.y - ankle_eb.head.y) / (ex_eb.head.y - ankle_eb.head.y)
                    weight = np.clip((center - 0.75) * 2.0, 0.0, 1.0)
                    remove_vertex_weight(obj, vertex)
                    obj.vertex_groups[ex_bl].add([vertex.index], weight, 'ADD')
                    obj.vertex_groups[ankle_bl].add([vertex.index], 1 - weight, 'ADD')
        for obj in objs:
            for vertex in obj.data.vertices:
                for vg in vertex.groups:
                    group_name = obj.vertex_groups[vg.group].name
                    weight = vg.weight
                    if group_name == leg_bl:
                        obj.vertex_groups[leg_bl].remove([vertex.index])
                        obj.vertex_groups[leg_d_bl].add([vertex.index], weight, 'ADD')
                    if group_name == knee_bl:
                        obj.vertex_groups[knee_bl].remove([vertex.index])
                        obj.vertex_groups[knee_d_bl].add([vertex.index], weight, 'ADD')
                    if group_name == ankle_bl:
                        obj.vertex_groups[ankle_bl].remove([vertex.index])
                        obj.vertex_groups[ankle_d_bl].add([vertex.index], weight, 'ADD')

        # 足骨刚体移动到足D骨
        pmx_root = find_pmx_root_with_child(armature)
        rigid_group = find_rigid_group(pmx_root)
        if rigid_group:
            for rigid_body in rigid_group.children:
                if rigid_body.mmd_rigid.bone == leg_bl:
                    rigid_body.mmd_rigid.bone = leg_d_bl
                if rigid_body.mmd_rigid.bone == knee_bl:
                    rigid_body.mmd_rigid.bone = knee_d_bl
                if rigid_body.mmd_rigid.bone == ankle_bl:
                    rigid_body.mmd_rigid.bone = ankle_d_bl
        # 设置显示枠
        if base_props.enable_gen_frame_checked:
            add_item_after(armature, ex_bl, ankle_bl)
            if controllable:
                add_item_after(armature, ankle_d_bl, ankle_bl)
                add_item_after(armature, knee_d_bl, ankle_bl)
                add_item_after(armature, leg_d_bl, ankle_bl)
        results.append(
            SsbResult(status=SsbStatus.SUCCESS, result=[ex_jp, leg_d_jp, knee_d_jp, ankle_d_jp]))


def remove_vertex_weight(obj, vertex):
    """移除顶点权重（排除对'mmd_edge_scale', 'mmd_vertex_order'的影响）
    mmd_edge_scale 轮廓倍率，一般值均为1
    mmd_vertex_order 取值为i/vertex_count，记录了pmx模型顶点的顺序。
    """
    for group in vertex.groups:
        group_name = obj.vertex_groups[group.group].name
        if group_name not in ['mmd_edge_scale', 'mmd_vertex_order']:
            obj.vertex_groups[group.group].remove([vertex.index])


def create_d_bone(armature, scale, source_jp, controllable):
    edit_bones = armature.data.edit_bones
    pose_bones = armature.pose.bones

    # 源骨骼信息
    source_bl = jp_bl_map[source_jp]
    source_pb = pose_bones.get(source_bl)
    source_eb = edit_bones[source_bl]
    source_mmd_bone = source_pb.mmd_bone
    source_en = source_mmd_bone.name_e
    # 目标D骨骼信息
    target_jp = source_jp + "D"
    target_en = source_en + "D"
    target_bl = convertNameToLR(target_jp)

    # 创建目标D骨骼（通过新建骨骼并传递指定参数的方式来模拟拷贝）
    # 原逻辑足D骨是从足骨上面拷贝而来的，但是在blender中进行拷贝的话
    # 1：选中edit bone进行复制，但是复制后需要切换上下文才能获取pose_bone的bone属性
    # 2：mmd_bone中有一个叫ik_rotation_constraint的属性，如果一起拷贝过来，会很碍事
    target_eb = create_bone_with_mmd_info(armature, target_bl, target_jp, target_en)
    # 设置是否 可移动 可旋转 可操作
    movable = all(loc is False for loc in source_pb.lock_location)
    rotatable = all(loc is False for loc in source_pb.lock_rotation)
    set_movable(armature, target_bl, movable)
    set_rotatable(armature, target_bl, rotatable)
    set_controllable(armature, target_bl, controllable)
    # 设置 head tail parent
    target_eb.head = source_eb.head
    target_eb.tail = target_eb.head + Vector((0, 0, 1)) * scale
    target_eb.parent = source_eb.parent
    # 设置mmd名称
    target_pb = pose_bones.get(target_bl)
    target_mmd_bone = target_pb.mmd_bone
    target_mmd_bone.name_j = target_jp
    target_mmd_bone.name_e = target_en
    # 设置赋予信息
    target_mmd_bone.has_additional_rotation = True
    target_mmd_bone.additional_transform_influence = 1
    target_mmd_bone.additional_transform_bone = source_bl
    target_mmd_bone.is_tip = True
    # 设置变形阶层
    target_mmd_bone.transform_order = source_mmd_bone.transform_order + 1
    # 设置剩余内容
    target_mmd_bone.transform_after_dynamics = source_mmd_bone.transform_after_dynamics
    target_mmd_bone.enabled_fixed_axis = source_mmd_bone.enabled_fixed_axis
    target_mmd_bone.fixed_axis = source_mmd_bone.fixed_axis
    target_mmd_bone.enabled_local_axes = source_mmd_bone.enabled_local_axes
    target_mmd_bone.local_axis_x = source_mmd_bone.local_axis_x
    target_mmd_bone.local_axis_z = source_mmd_bone.local_axis_z
    return target_jp, target_bl, target_eb


def create_thumb0_bone(armature, props, results):
    base_props = props.base
    if not base_props.thumb0_checked:
        return

    def callback1(v):
        return Vector((-v.y, v.x, 0))

    def callback2(v):
        return Vector((v.y, -v.x, 0))

    thumb0_infos = [
        ("右親指０", "thumb0_R", "右手首", "右親指１", "右親指２", "右人指１", Vector((1, -1, 0)).normalized().xzy,
         callback1),
        ("左親指０", "thumb0_L", "左手首", "左親指１", "左親指２", "左人指１", Vector((-1, -1, 0)).normalized().xzy,
         callback2)
    ]
    for index, info in enumerate(thumb0_infos):
        # 基本名称信息
        thumb0_jp = info[0]
        thumb0_en = info[1]
        thumb0_bl = convertNameToLR(thumb0_jp)
        wrist_jp = info[2]
        thumb1_jp = info[3]
        thumb2_jp = info[4]
        fore1_jp = info[5]
        direction = info[6]

        # 先决条件校验
        if thumb0_jp in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[thumb0_jp]))
            continue
        required_bones = [wrist_jp, thumb1_jp]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = [thumb0_jp]
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
            continue

        # 常用参数获取
        scale = props.scale
        edit_bones = armature.data.edit_bones
        pose_bones = armature.pose.bones
        objs = find_pmx_objects(armature)

        # 补充名称信息（blender）
        wrist_bl = jp_bl_map[wrist_jp]
        thumb1_bl = jp_bl_map[thumb1_jp]
        thumb2_bl = jp_bl_map[thumb2_jp]
        fore1_bl = jp_bl_map[fore1_jp]
        # 补充骨骼信息
        wrist_eb = edit_bones.get(wrist_bl)
        thumb1_eb = edit_bones.get(thumb1_bl)
        thumb2_eb = edit_bones.get(thumb2_bl)
        fore1_eb = edit_bones.get(fore1_bl)

        # 创建亲指0
        thumb0_eb = create_bone_with_mmd_info(armature, thumb0_bl, thumb0_jp, thumb0_en)
        # 设置是否 可移动 可旋转 可操作
        set_movable(armature, thumb0_bl, False)
        set_rotatable(armature, thumb0_bl, True)
        set_controllable(armature, thumb0_bl, True)
        # 设置亲指0 head tail parent
        thumb0_eb.head = (1 - 2.0 / 3.0) * wrist_eb.head + (2.0 / 3.0) * thumb1_eb.head
        thumb0_eb.tail = thumb1_eb.head
        thumb0_eb.parent = wrist_eb
        thumb1_eb.parent = thumb0_eb

        # 权重分配
        length = Vector(thumb1_eb.head - thumb0_eb.head).length
        for obj in objs:
            for vertex in obj.data.vertices:
                if not contains_vg(obj, vertex, [wrist_bl, thumb1_bl]):
                    continue
                # 顶点 与 亲指0和亲指1中点 的距离（向量）
                distance = Vector(vertex.co) - Vector((thumb0_eb.head + thumb1_eb.head) * 0.5)
                # distance 在 direction 上面的投影长度（及方向）
                projection = distance.dot(direction) * direction
                # 计算权重
                weight = Vector(distance - projection).length
                weight /= length * 1.4
                if weight < 1.0:
                    # 将权重限定在0-1之间
                    weight = np.clip((1.0 - weight) * 1.3, 0.0, 1.0)
                    # 如果顶点受手首影响（阈值0.97）
                    if is_vertex_dedicated_by_bone(obj, vertex, wrist_bl, threshold=0.97):
                        remove_vertex_weight(obj, vertex)
                        obj.vertex_groups[thumb0_bl].add([vertex.index], weight, 'ADD')
                        obj.vertex_groups[wrist_bl].add([vertex.index], 1 - weight, 'ADD')
                    # 如果顶点受亲指1影响（阈值0.97）
                    elif is_vertex_dedicated_by_bone(obj, vertex, thumb1_bl, threshold=0.97):
                        remove_vertex_weight(obj, vertex)
                        obj.vertex_groups[thumb0_bl].add([vertex.index], weight, 'ADD')
                        obj.vertex_groups[thumb1_bl].add([vertex.index], 1 - weight, 'ADD')
                    # 其他情况分配权重
                    else:
                        vg_count = 0
                        vgs = [vg for vg in vertex.groups if
                               obj.vertex_groups[vg.group].name in bl_jp_map.keys() and
                               obj.vertex_groups[vg.group].name not in ('mmd_edge_scale', 'mmd_vertex_order')]
                        for vg in vgs:
                            vg_count += 1
                            if vg_count > 4:
                                break
                            group_name = obj.vertex_groups[vg.group].name
                            if group_name == wrist_bl:
                                bone_weight = vg.weight
                                # 将顶点在手首上的权重转移到亲指0上面
                                obj.vertex_groups[wrist_bl].remove([vertex.index])
                                obj.vertex_groups[thumb0_bl].add([vertex.index], bone_weight, 'ADD')
                                if bone_weight < weight:
                                    obj.vertex_groups[thumb0_bl].remove([vertex.index])
                                    obj.vertex_groups[thumb0_bl].add([vertex.index], weight, 'ADD')
                                    weight_sum = 0
                                    for other_vg in vgs:
                                        if vg.group == other_vg.group:
                                            continue
                                        weight_sum = other_vg.weight
                                    if weight_sum > 0:
                                        for other_vg in vgs:
                                            if vg.group == other_vg.group:
                                                continue
                                            other_vg_name = obj.vertex_groups[other_vg.group].name
                                            other_group_weight = other_vg.weight
                                            obj.vertex_groups[other_vg_name].remove([vertex.index])
                                            obj.vertex_groups[other_vg_name].add([vertex.index], other_group_weight * (
                                                    1 - weight) / weight_sum, 'ADD')
        # 设置显示枠
        if base_props.enable_gen_frame_checked:
            add_item_before(armature, thumb0_bl, thumb1_bl)
        results.append(SsbResult(status=SsbStatus.SUCCESS, result=[thumb0_jp]))
        # 设定親指Local轴
        if not base_props.enable_thumb_local_axes_checked:
            continue

        # 先决条件校验
        required_bones = [thumb0_jp, thumb1_jp, thumb2_jp, fore1_jp]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = []
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, message=f'设定親指Local轴所需的{not_found_list}不存在'))
            continue

        # todo 在设置本地轴z轴的时候，blender中显示的是一个值，PE中显示的是另一个值，在设置固定轴的时候，这个值能通过to_pmx_axis修正（未大量测试）
        # todo 但是这里却不能，虽然暂时无法修正为和PE中一模一样，但是使用上没问题
        set_local_axes(armature, thumb0_bl,
                       Vector(thumb1_eb.head - thumb0_eb.head).normalized().xzy,
                       to_pmx_axis(armature, scale, Vector(thumb0_eb.head - fore1_eb.head).normalized(),
                                   thumb0_bl))
        # mmd坐标系
        axis_z = info[7](Vector(thumb2_eb.head - thumb1_eb.head).xzy)
        axis_z.z = -axis_z.length * 0.2
        set_local_axes(armature, thumb1_bl,
                       Vector(thumb2_eb.head - thumb1_eb.head).normalized().xzy,
                       axis_z)
        # 获取親指先
        target_bone = get_target_bone(armature, thumb2_eb)
        if target_bone:
            thumb2_target_head = target_bone.head
        else:
            thumb2_target_head = thumb2_eb.tail
        set_local_axes(armature, thumb2_bl,
                       Vector(thumb2_target_head - thumb2_eb.head).normalized().xzy,
                       axis_z)


def set_local_axes(armature, bone_name, x, z):
    pose_bone = armature.pose.bones.get(bone_name)
    mmd_bone = pose_bone.mmd_bone
    mmd_bone.enabled_local_axes = True
    mmd_bone.local_axis_x = x
    mmd_bone.local_axis_z = z


def contains_vg(obj, vertex, names):
    for group in vertex.groups:
        group_name = obj.vertex_groups[group.group].name
        if group_name in names:
            return True
    return False


def create_arm_twist_bone(armature, props, results):
    base_props = props.base
    if not base_props.arm_twist_checked:
        return

    arm_twist_infos = [
        ("右腕捩", "arm twist_R", "右腕", "右ひじ"),
        ("左腕捩", "arm twist_L", "左腕", "左ひじ")
    ]
    for info in arm_twist_infos:
        result = create_twist_bone(armature, props, info, True)
        results.append(result)


def create_wrist_twist_bone(armature, props, results):
    base_props = props.base
    if not base_props.wrist_twist_checked:
        return

    arm_twist_infos = [
        ("右手捩", "wrist twist_R", "右ひじ", "右手首"),
        ("左手捩", "wrist twist_L", "左ひじ", "左手首")
    ]
    for info in arm_twist_infos:
        result = create_twist_bone(armature, props, info, False)
        results.append(result)


def create_twist_bone(armature, props, info, has_elbow_offset):
    # 基本名称信息
    twist_jp = info[0]
    twist_en = info[1]
    twist_bl = convertNameToLR(info[0])
    twist_parent_jp = info[2]
    twist_child_jp = info[3]

    # 先决条件校验
    if twist_jp in jp_bl_map.keys():
        return SsbResult(status=SsbStatus.SKIPPED, result=[twist_jp])
    required_bones = [twist_parent_jp, twist_child_jp]
    if any(name not in jp_bl_map for name in required_bones):
        not_found_list = [twist_jp]
        for bone_name in required_bones:
            if bone_name not in jp_bl_map:
                not_found_list.append(bone_name)
        return SsbResult(status=SsbStatus.FAILED, result=not_found_list)

    # 常用参数获取
    scale = props.scale
    base_props = props.base
    edit_bones = armature.data.edit_bones
    pose_bones = armature.pose.bones
    objs = find_pmx_objects(armature)

    # 补充名称信息（blender）
    twist_parent_bl = jp_bl_map[twist_parent_jp]
    twist_child_bl = jp_bl_map[twist_child_jp]

    twist_parent_eb = edit_bones.get(twist_parent_bl)
    twist_child_eb = edit_bones.get(twist_child_bl)
    # c++中，vec3本身不是引用类型，所以这里需要copy
    twist_child_eb_head = twist_child_eb.head.copy()
    # 自动补正旋转轴（修正腕捩所在位置）
    if has_elbow_offset and base_props.enable_elbow_offset_checked:
        v_count = 0.0
        loc_y_sum = 0.0
        for obj in objs:
            for vertex in obj.data.vertices:
                if is_vertex_dedicated_by_bone(obj, vertex, twist_parent_bl, threshold=0.6):
                    loc_y_sum += vertex.co.y / scale
                    v_count = v_count + 1.0
        if v_count > 0.0:
            offset = (loc_y_sum / v_count * scale - twist_child_eb_head.y) * 0.75
            twist_child_eb_head.y += offset

    # 创建捩骨
    twist_eb = create_bone_with_mmd_info(armature, twist_bl, twist_jp, twist_en)
    # 设置是否可移动 可旋转 可操作
    set_movable(armature, twist_bl, False)
    twist_pb = pose_bones.get(twist_bl)
    twist_pb.mmd_bone.is_tip = True
    twist_pb.lock_rotation = (True, False, True)  # 设置锁定旋转，如果是tip且未应用固定轴时需特殊处理
    set_controllable(armature, twist_bl, True)
    # 设置捩骨 head parent
    twist_eb.head = Vector(twist_parent_eb.head * 0.4 + twist_child_eb_head * 0.6)
    twist_eb.parent = twist_parent_eb
    # 设置捩骨轴限制相关参数（mmd坐标系），默认不会应用，暂不提供是否应用的参数给用户
    # 如果开启自动补正旋转轴，fixed_axis的值在小数点后第5位存在误差（用MEIKO时数值不一致，但是用Miku_Hatsune时数值一致）
    # fixed_axis计算长度时，需要考虑缩放
    # 计算点积时，仅考虑fixed_axis的方向，fixed_axis的大小应为1，以便在最大值和最小值之间插值（值取决于在方向上的延伸即后者，而非fixed_axis的长度）
    twist_pb.mmd_bone.enabled_fixed_axis = True
    tmp_axis = twist_child_eb_head - twist_parent_eb.head
    fixed_axis = to_pmx_axis(armature, scale, tmp_axis, twist_bl)
    twist_pb.mmd_bone.fixed_axis = fixed_axis
    # 设置捩骨 tail
    twist_eb.tail = twist_eb.head + fixed_axis.xzy.normalized() * scale
    # 更新（指定）骨骼旋转角度
    FnBone.update_auto_bone_roll(twist_eb)
    twist_child_eb.parent = twist_eb

    twist_parent_eb_dedicated_vertices = {}
    twist_parent_eb_dot = Vector(twist_parent_eb.head - twist_eb.head).dot(fixed_axis.xzy) * 0.8
    twist_child_eb_dot = Vector(twist_child_eb_head - twist_eb.head).dot(fixed_axis.xzy) * 0.8
    for obj in objs:
        for vertex in obj.data.vertices:
            v_twist_eb_dot = Vector(Vector(vertex.co) - twist_eb.head).dot(fixed_axis.xzy)
            if is_vertex_dedicated_by_bone(obj, vertex, twist_parent_bl, threshold=0.97):
                twist_parent_eb_dot = min(twist_parent_eb_dot, v_twist_eb_dot)
                twist_child_eb_dot = max(twist_child_eb_dot, v_twist_eb_dot)
                twist_parent_eb_dedicated_vertices[vertex] = obj
            elif v_twist_eb_dot > 0.0:
                for group in vertex.groups:
                    if obj.vertex_groups[group.group].name == twist_parent_bl:
                        index = obj.vertex_groups.find(twist_bl)
                        if index != -1:
                            obj.vertex_groups[index].add([vertex.index], group.weight, 'ADD')
                        # 移除操作放到最后
                        obj.vertex_groups[group.group].remove([vertex.index])
                        break
    part_twists = []
    part_twist_jp_list = []
    for i in range(3):
        coefficient = (i + 1) / 4.0
        # 基本名称信息
        part_twist_jp = twist_jp + str(i + 1)
        part_twist_jp_list.append(part_twist_jp)
        part_twist_bl = convertNameToLR(part_twist_jp)
        part_twists.append(part_twist_bl)

        # 先决条件校验
        if part_twist_jp in jp_bl_map:
            remove_bone(armature, objs, part_twist_bl)

        # 创建剩余捩骨
        part_twist_eb = create_bone_with_mmd_info(armature, part_twist_bl, part_twist_jp, "")
        # 设置是否可移动 可旋转 可操作
        set_movable(armature, part_twist_bl, False)
        set_rotatable(armature, part_twist_bl, True)
        set_controllable(armature, part_twist_bl, True)
        # 设置 head tail parent
        part_twist_eb.head = twist_eb.head + fixed_axis.xzy * (
                (1 - coefficient) * twist_parent_eb_dot + coefficient * twist_child_eb_dot)
        part_twist_eb.tail = part_twist_eb.head + Vector((0, 0, 1)) * scale
        part_twist_eb.parent = twist_parent_eb
        # 设置赋予相关信息
        part_twist_pb = pose_bones[part_twist_bl]
        mmd_bone = part_twist_pb.mmd_bone
        mmd_bone.has_additional_rotation = True
        mmd_bone.additional_transform_influence = coefficient
        mmd_bone.additional_transform_bone = twist_bl
        # 设置尖端骨骼
        pose_bones[part_twist_bl].mmd_bone.is_tip = True
    for vertex, obj in twist_parent_eb_dedicated_vertices.items():
        vertex_twist_bone_dot = Vector(Vector(vertex.co) - twist_eb.head).dot(fixed_axis.xzy)
        delta = ((vertex_twist_bone_dot - twist_parent_eb_dot) / (twist_child_eb_dot - twist_parent_eb_dot)) * 4.0
        weight = (int(100.0 * delta) % 100) / 100.0
        remove_vertex_weight(obj, vertex)
        if int(delta) == 0:
            obj.vertex_groups[part_twists[0]].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[twist_parent_bl].add([vertex.index], 1.0 - weight, 'ADD')
        elif int(delta) == 1:
            obj.vertex_groups[part_twists[1]].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[part_twists[0]].add([vertex.index], 1.0 - weight, 'ADD')
        elif int(delta) == 2:
            obj.vertex_groups[part_twists[2]].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[part_twists[1]].add([vertex.index], 1.0 - weight, 'ADD')
        elif int(delta) == 3:
            obj.vertex_groups[twist_bl].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[part_twists[2]].add([vertex.index], 1.0 - weight, 'ADD')
        elif int(delta) == 4:
            obj.vertex_groups[twist_child_bl].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[twist_bl].add([vertex.index], 1.0 - weight, 'ADD')
        else:
            pass
    if base_props.enable_gen_frame_checked:
        add_item_after(armature, twist_bl, twist_parent_bl)
    return SsbResult(status=SsbStatus.SUCCESS, result=[twist_jp] + part_twist_jp_list)


def create_waist_bone(armature, props, results):
    base_props = props.base
    if not base_props.waist_checked:
        return

    # 基本名称信息
    waist_jp = "腰"
    waist_en = "waist"
    waist_bl = convertNameToLR(waist_jp)
    under_body_jp = "下半身"
    right_leg_jp = "右足"
    left_leg_jp = "左足"

    # 先决条件校验
    if waist_jp in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[waist_jp]))
        return
    required_bones = [under_body_jp, right_leg_jp, left_leg_jp]  # PE中没有对左足进行校验，直接抛异常且创建失败
    under_body_parent = armature.pose.bones.get(jp_bl_map[under_body_jp]).parent
    if any(name not in jp_bl_map for name in required_bones) or under_body_parent is None:
        not_found_list = [waist_jp]
        for bone_name in required_bones:
            if bone_name not in jp_bl_map:
                not_found_list.append(bone_name)
        results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
        if under_body_parent is None:
            result = SsbResult(status=SsbStatus.FAILED,
                               message=f"{waist_jp}骨骼所需的{under_body_jp}的亲骨骼不存在")
            results.append(result)
        return

    # 常用参数获取
    scale = props.scale
    edit_bones = armature.data.edit_bones
    pose_bones = armature.pose.bones

    # 补充名称信息（blender）
    under_body_bl = jp_bl_map[under_body_jp]
    right_leg_bl = jp_bl_map[right_leg_jp]
    # 补充骨骼信息
    under_body_eb = edit_bones.get(under_body_bl)
    right_leg_eb = edit_bones.get(right_leg_bl)

    # 创建腰骨骼
    waist_eb = create_bone_with_mmd_info(armature, waist_bl, waist_jp, waist_en)
    # 设置是否 可移动 可旋转 可操作
    set_movable(armature, waist_bl, False)
    set_rotatable(armature, waist_bl, True)
    set_controllable(armature, waist_bl, True)
    # 设置腰骨骼 head tail parent
    waist_eb.head = Vector(
        (0, under_body_eb.head.z * 0.02, under_body_eb.head.z * 0.4 + right_leg_eb.head.z * 0.6))
    waist_eb.tail = waist_eb.head + Vector((under_body_eb.head - waist_eb.head) * 0.8)
    waist_eb.parent = under_body_eb.parent
    # 设置腰骨骼的变形阶层为下半身亲骨的变形阶层
    under_body_pb = pose_bones.get(under_body_bl)
    under_body_parent_pb = under_body_pb.parent
    waist_pb = pose_bones.get(waist_bl)
    waist_pb.mmd_bone.transform_order = under_body_parent_pb.mmd_bone.transform_order
    # 如果骨骼的父级是下半身的parent且名称不是センター先，则将其亲骨改为腰骨（还需要排除临时骨骼对流程的影响）
    center_saki_pattern = r'^センター先(\.\d{3})?$'  # PE中允许同名但是blender中会重命名为.001
    for eb in edit_bones:
        if eb.parent == under_body_eb.parent and not re.match(center_saki_pattern,
                                                              eb.name) and KAFEI_TMP_BONE_NAME not in eb.name:
            eb.parent = waist_eb
    # 设置显示枠
    if base_props.enable_gen_frame_checked:
        flag = add_item_after(armature, waist_bl, under_body_parent_pb.name)
        if not flag:
            pmx_root = find_pmx_root_with_child(armature)
            frame = create_center_frame(pmx_root)
            do_add_item(frame, 'BONE', waist_bl)
    waist_c_infos = [
        ("腰キャンセル右", "右足"),
        ("腰キャンセル左", "左足"),
    ]
    waist_c_jp_list = []
    for info in waist_c_infos:
        # 基本名称信息
        waist_c_jp = info[0]
        waist_c_jp_list.append(waist_c_jp)
        waist_c_bl = convertNameToLR(waist_c_jp)
        foot_jp = info[1]

        # 先决条件校验
        if waist_c_jp in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[waist_c_jp]))
            continue

        # 补充名称信息（blender）
        foot_bl = jp_bl_map[foot_jp]
        # 补充骨骼信息
        foot_eb = edit_bones.get(foot_bl)

        # 创建腰取消骨骼
        waist_c_eb = create_bone_with_mmd_info(armature, waist_c_bl, waist_c_jp, '')
        # 设置是否 可移动 可旋转 可操作
        set_movable(armature, waist_c_bl, False)
        set_rotatable(armature, waist_c_bl, True)
        set_controllable(armature, waist_c_bl, True)
        # 设置腰骨骼 head tail parent
        waist_c_eb.head = foot_eb.head
        waist_c_eb.tail = waist_c_eb.head + Vector((0, 0, 1)) * scale
        waist_c_eb.parent = foot_eb.parent
        foot_eb.parent = waist_c_eb
        # 设置赋予相关属性，然后重新装配骨骼（这部分属性一旦修改就dirty了，利用设置的tag调用mmd插件的骨骼装配）
        waist_c_pb = pose_bones[waist_c_bl]
        mmd_bone = waist_c_pb.mmd_bone
        mmd_bone.has_additional_rotation = True
        mmd_bone.additional_transform_influence = -1
        mmd_bone.additional_transform_bone = waist_bl
        # 设置尖端骨骼
        mmd_bone.is_tip = True
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[waist_jp] + waist_c_jp_list))


def remove_bone(armature, objs, bone_name):
    edit_bones = armature.data.edit_bones
    eb = edit_bones.get(bone_name)
    parent_eb = eb.parent
    pmx_root = find_pmx_root_with_child(armature)
    mmd_root = pmx_root.mmd_root
    frames = mmd_root.display_item_frames
    found_frame, found_item = find_bone_item(pmx_root, bone_name)
    # 移除显示枠
    if found_frame is not None and found_item is not None:
        frames[found_frame].data.remove(found_item)

    # 转移权重
    for obj in objs:
        vg = obj.vertex_groups.get(bone_name)
        parent_vg = None
        if parent_eb:
            parent_vg = obj.vertex_groups.get(parent_eb.name)
        if not vg:
            continue
        for vert in obj.data.vertices:
            for group in vert.groups:
                if group.group == vg.index:
                    if parent_vg is not None:
                        obj.vertex_groups[parent_vg.name].add([vert.index], group.weight, 'ADD')
                    obj.vertex_groups[vg.name].add([vert.index], 0, 'REPLACE')

    # 移除骨骼
    armature.data.edit_bones.remove(eb)


def create_ik_p_bone(armature, props, results):
    base_props = props.base
    if not base_props.ik_p_checked:
        return

    ik_p_infos = [
        ("右足IK親", "leg IKP_R", "右足ＩＫ"),
        ("左足IK親", "leg IKP_L", "左足ＩＫ")
    ]
    for info in ik_p_infos:
        # 基本名称信息
        ik_p_jp = info[0]
        ik_p_en = info[1]
        ik_p_bl = convertNameToLR(info[0])
        ik_jp = info[2]

        # 先决条件校验
        if ik_p_jp in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[ik_p_jp]))
            continue
        if ik_jp not in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.FAILED, result=[ik_p_jp, ik_jp]))
            continue

        # 常用参数获取
        edit_bones = armature.data.edit_bones

        # 补充名称信息（blender）
        ik_bl = jp_bl_map[ik_jp]
        # 补充骨骼信息
        ik_eb = edit_bones.get(ik_bl)

        # 创建ik亲骨
        ik_p_eb = create_bone_with_mmd_info(armature, ik_p_bl, ik_p_jp, ik_p_en)
        # 设置是否 可移动 可旋转 可操作
        set_movable(armature, ik_p_bl, True)
        set_rotatable(armature, ik_p_bl, True)
        set_controllable(armature, ik_p_bl, True)
        # 设置ik亲骨 head tail
        ik_p_eb.head = ik_eb.head * Vector((1, 1, 0))
        ik_p_eb.tail = ik_eb.head
        # 设置 parent
        ik_p_eb.parent = ik_eb.parent
        ik_eb.parent = ik_p_eb
        # 设置显示枠
        if base_props.enable_gen_frame_checked:
            add_item_before(armature, ik_p_bl, ik_bl)
        results.append(SsbResult(status=SsbStatus.SUCCESS, result=[ik_p_jp]))


def create_shoulder_p_bone(armature, props, results):
    base_props = props.base
    if not base_props.shoulder_p_checked:
        return

    shoulder_infos = [
        ("右肩P", "右肩C", "shoulderP_R", "右肩", "右腕"),
        ("左肩P", "左肩C", "shoulderP_L", "左肩", "左腕")
    ]
    for shoulder_info in shoulder_infos:
        # 基本名称信息
        shoulder_p_jp = shoulder_info[0]
        shoulder_c_jp = shoulder_info[1]
        shoulder_p_en = shoulder_info[2]
        shoulder_p_bl = convertNameToLR(shoulder_info[0])
        shoulder_c_bl = convertNameToLR(shoulder_info[1])
        shoulder_jp = shoulder_info[3]
        arm_jp = shoulder_info[4]

        # 先决条件校验
        if shoulder_p_jp in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[shoulder_p_jp]))
            continue
        required_bones = [shoulder_jp, arm_jp]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = [shoulder_p_jp]
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
            continue

        # 常用参数获取
        scale = props.scale
        edit_bones = armature.data.edit_bones
        pose_bones = armature.pose.bones

        # 补充名称信息（blender）
        shoulder_name_b = jp_bl_map[shoulder_jp]
        arm_name_b = jp_bl_map[arm_jp]
        # 补充骨骼信息
        shoulder_eb = edit_bones.get(shoulder_name_b)
        arm_eb = edit_bones.get(arm_name_b)

        # 创建肩P骨
        shoulder_p_bone = create_bone_with_mmd_info(armature, shoulder_p_bl, shoulder_p_jp, shoulder_p_en)
        # 设置是否 可移动 可旋转 可操作
        set_movable(armature, shoulder_p_bl, False)
        set_rotatable(armature, shoulder_p_bl, True)
        set_controllable(armature, shoulder_p_bl, True)
        # 创建肩c骨
        shoulder_c_bone = create_bone_with_mmd_info(armature, shoulder_c_bl, shoulder_c_jp, '')
        # 设置是否 可移动 可旋转 可操作
        set_movable(armature, shoulder_c_bl, False)
        set_rotatable(armature, shoulder_c_bl, True)
        set_controllable(armature, shoulder_c_bl, True)

        # 设置肩P骨 head tail parent 旋转轴 尖端骨骼
        shoulder_p_bone.head = shoulder_eb.head
        shoulder_p_bone.tail = shoulder_p_bone.head + Vector((0, 0, 1)) * scale
        shoulder_p_bone.parent = shoulder_eb.parent
        FnBone.update_auto_bone_roll(shoulder_p_bone)
        shoulder_p_pb = pose_bones[shoulder_p_bl]
        shoulder_p_pb.mmd_bone.is_tip = True
        # 设置肩C骨 head tail parent
        shoulder_c_bone.head = arm_eb.head
        shoulder_c_bone.tail = shoulder_c_bone.head + Vector((0, 0, 1)) * scale
        shoulder_c_bone.parent = shoulder_eb
        # 设置肩腕 parent
        shoulder_eb.parent = shoulder_p_bone
        arm_eb.parent = shoulder_c_bone
        # 设置赋予相关属性，然后重新装配骨骼（这部分属性一旦修改就dirty了，利用设置的tag调用mmd插件的骨骼装配）
        shoulder_c_pb = pose_bones[shoulder_c_bl]
        mmd_bone = shoulder_c_pb.mmd_bone
        mmd_bone.has_additional_rotation = True
        mmd_bone.additional_transform_influence = -1
        mmd_bone.additional_transform_bone = shoulder_p_bl
        # 设置尖端骨骼
        mmd_bone.is_tip = True
        # 设置显示枠
        if base_props.enable_gen_frame_checked:
            add_item_before(armature, shoulder_p_bl, shoulder_name_b)
        results.append(SsbResult(status=SsbStatus.SUCCESS, result=[shoulder_p_jp, shoulder_c_jp]))


def create_bone_with_mmd_info(armature, name_bl, name_jp, name_en):
    eb = get_tmp_bone(armature)
    eb.name = name_bl
    jp_bl_map[name_jp] = name_bl
    bl_jp_map[name_bl] = name_jp
    # 设置MMD骨骼名称
    mmd_bone = armature.pose.bones.get(name_bl).mmd_bone
    mmd_bone.name_j = name_jp
    mmd_bone.name_e = name_en
    return eb


def create_upper_body2_bone(armature, props, results):
    base_props = props.base
    if not base_props.upper_body2_checked:
        return

    # 基本名称信息
    upper_body2_jp = "上半身2"
    upper_body2_en = "upper body2"
    upper_body2_bl = convertNameToLR(upper_body2_jp)
    spine_jp = "上半身"
    neck_jp = "首"

    # 先决条件校验
    if upper_body2_jp in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[upper_body2_jp]))
        return
    required_bones = [spine_jp, neck_jp]
    if any(name not in jp_bl_map for name in required_bones):
        not_found_list = [upper_body2_jp]
        for bone_name in required_bones:
            if bone_name not in jp_bl_map:
                not_found_list.append(bone_name)
        results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
        return

    # 补充名称信息（blender）
    spine_bl = jp_bl_map[spine_jp]
    neck_bl = jp_bl_map[neck_jp]

    # 常用参数获取
    scale = props.scale
    edit_bones = armature.data.edit_bones
    pose_bones = armature.pose.bones
    objs = find_pmx_objects(armature)

    # 创建上半身2
    upper_body2_eb = create_bone_with_mmd_info(armature, upper_body2_bl, upper_body2_jp, upper_body2_en)
    # 设置是否 可移动 可旋转 可操作
    set_movable(armature, upper_body2_bl, False)
    set_rotatable(armature, upper_body2_bl, True)
    set_controllable(armature, upper_body2_bl, True)
    # 设置上半身2的 head tail parent
    spine_eb = edit_bones.get(spine_bl)
    neck_eb = edit_bones.get(neck_bl)
    upper_body2_eb.head = spine_eb.head * 0.65 + neck_eb.head * 0.35
    upper_body2_eb.tail = upper_body2_eb.head + (neck_eb.head - upper_body2_eb.head) * 0.8
    upper_body2_eb.parent = spine_eb
    # 设置变形阶层
    pose_bones.get(upper_body2_bl).mmd_bone.transform_order = pose_bones.get(spine_bl).mmd_bone.transform_order
    # 设置指向
    # mmd插件在导入时，用的是edit bone进行的比较
    # 当一个骨骼的target指向的是一个骨骼引用时，这个骨骼要被设置为use_connect需要：
    # 这两个骨骼是亲子关系 and 子骨骼不可移动 and 亲骨骼可移动 and 亲子距离<1e-4。
    # mmd插件在导出时，用的是pose_bone.bone https://docs.blender.org/api/current/bpy.types.Bone.html#bpy.types.Bone
    # 当一个亲骨骼的末端指向另一个子骨骼时，这个亲骨骼要设置target需要：
    # 子骨骼use_connect为True or 子骨骼拥有mmd_bone_use_connect属性
    #                       or (子骨骼不可移动 and math.isclose(0.0, (child.head - bone.tail).length))
    # bone.tail代表的意思是，骨骼尾端相对于其父骨骼的位置
    # 已确认无法设置指向是mmd插件的bug，这里逻辑不变
    spine_eb.tail = upper_body2_eb.head
    # 如果骨骼的父级指向上半身，则改为上半身2
    for eb in edit_bones:
        parent_eb = eb.parent
        if parent_eb and parent_eb.name == spine_bl and KAFEI_TMP_BONE_NAME not in eb.name:
            eb.parent = upper_body2_eb
    # 权重转移
    for obj in objs:
        upper_body2_vg_index = -1
        upper_body_vg_index = -1
        neck_vg_index = -1
        for vg in obj.vertex_groups:
            if vg.name == upper_body2_bl:
                upper_body2_vg_index = vg.index
            if vg.name == spine_bl:
                upper_body_vg_index = vg.index
            if vg.name == neck_bl:
                neck_vg_index = vg.index

        spine_vertices = []
        # 遍历顶点
        for vertex in obj.data.vertices:
            if is_vertex_dedicated_by_bone(obj, vertex, spine_jp, threshold=0.97):
                spine_vertices.append(vertex)
            elif vertex.co.z > upper_body2_eb.head.z:
                # 将不完全归上半身（含阈值）所有的顶点所对应的权重，转移到上半身2上面
                for group in vertex.groups:
                    if obj.vertex_groups[group.group].name == spine_jp:
                        index = obj.vertex_groups.find(upper_body2_bl)
                        if index != -1:
                            obj.vertex_groups[index].add([vertex.index], group.weight, 'ADD')
                        # 移除操作放到最后
                        obj.vertex_groups[group.group].remove([vertex.index])
                        break
        # 将完全归上半身（含阈值）的顶点所对应的权重，转移到上半身2上面
        for spine_vertex in spine_vertices:
            remove_vertex_weight(obj, spine_vertex)

            # 获取上半身顶点和上半身2的head的距离
            distance = spine_vertex.co - upper_body2_eb.head
            if distance.y > 0:
                distance.z += distance.y * 0.5
            # distance在上半身和首之间的比例
            per = distance.z / (neck_eb.head.z - upper_body2_eb.head.z)
            if per < -0.35:
                obj.vertex_groups[upper_body_vg_index].add([spine_vertex.index], 1, 'ADD')
            elif per > 0.35:
                obj.vertex_groups[upper_body2_vg_index].add([spine_vertex.index], 1, 'ADD')
            else:
                weight = int(((per + 0.35) / 0.7) * 100.0) * 0.01
                obj.vertex_groups[upper_body2_vg_index].add([spine_vertex.index], weight, 'ADD')
                obj.vertex_groups[upper_body_vg_index].add([spine_vertex.index], 1 - weight, 'ADD')
    # 如果刚体关联的是上半身，则改为上半身2
    pmx_root = find_pmx_root_with_child(armature)
    rigid_group = find_rigid_group(pmx_root)
    if rigid_group:
        for rigid_body in rigid_group.children:
            if rigid_body.mmd_rigid.bone == spine_bl:
                rigid_body.mmd_rigid.bone = upper_body2_bl
    # 设置显示枠
    if base_props.enable_gen_frame_checked:
        add_item_after(armature, upper_body2_bl, spine_bl)
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[upper_body2_jp]))


def is_vertex_dedicated_by_bone(obj, vertex, bone_name, threshold=1.0):
    summation = 0.0
    total = 0.0
    count = 1
    # 获取顶点权重
    for group in vertex.groups:
        # 在MMD中，一个顶点最多和4个骨骼相关联
        if count > 4:
            break
        weight = group.weight
        group_name = obj.vertex_groups[group.group].name
        if group_name in bl_jp_map.keys():
            count = count + 1
        if group_name == bone_name:
            summation += weight
        if group_name not in ['mmd_edge_scale', 'mmd_vertex_order']:
            total += weight
    if total != 0:
        return (summation / total) > threshold
    else:
        return 0


def add_frame(armature, assignee, base, after=True):
    pmx_root = find_pmx_root_with_child(armature)
    mmd_root = pmx_root.mmd_root
    found_frame, found_item = find_bone_item(pmx_root, base)

    if found_frame is not None and found_item is not None:
        frames = mmd_root.display_item_frames
        if after:
            do_add_item(frames[found_frame], 'BONE', assignee, order=found_item + 1)
        else:
            do_add_item(frames[found_frame], 'BONE', assignee, order=found_item)


def create_root_bone(armature, props, results):
    base_props = props.base
    if not base_props.root_checked:
        return

    # 基本名称信息
    root_jp = '全ての親'
    root_en = 'master'
    root_bl = convertNameToLR(root_jp)

    # 先决条件校验
    if root_jp in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[root_jp]))
        return

    # 常用参数获取
    scale = props.scale
    edit_bones = armature.data.edit_bones
    objs = find_pmx_objects(armature)

    # 创建全亲骨
    root_eb = create_bone_with_mmd_info(armature, root_bl, root_jp, root_en)
    # 设置是否可移动 可旋转 可操作
    set_movable(armature, root_bl, True)
    set_rotatable(armature, root_bl, True)
    set_controllable(armature, root_bl, True)
    # 设置tail
    # PE中的模型，至少会有一个center骨；从blender导出的骨骼，至少会有一个全亲骨
    # 通常来讲全亲骨的末端应该指向センター，但是参考代码及PE中的实际操作都表明，创建全亲骨无必要的骨骼，所以这里不做指向'センター'的优化。
    # 原逻辑是全亲骨指向骨骼面板中的首位，可是blender中是通过顶点组顺序来表示骨骼面板的
    # 获取排在首位的顶点组受到了骨架下有无物体以及物体顺序等方面的干扰
    # 应保证骨架下物体有且仅有1个才能最大程度上确保指向成功（PE中指向的结果是什么样这里就是什么样）
    # 但其它情况的话也无需拦截（按材质分开很普遍，这种情况通常也可以正常指向。后续可提供一个修复指向的功能）
    first_vg = get_first_vg(armature, objs, root_bl)
    first_eb = edit_bones[first_vg.name]
    if all(abs(coord) < 0.00001 for coord in first_eb.head):
        root_eb.tail = Vector((0, 0, 1)) * scale  # 确保全亲骨不会因为指向(0,0,0)而被移除
    else:
        root_eb.tail = first_eb.head

    # 设置剩余骨骼的parent和target
    edit_bones = armature.data.edit_bones
    for eb in edit_bones:
        parent_eb = eb.parent
        target_eb = get_target_bone(armature, eb)
        if not parent_eb and KAFEI_TMP_BONE_NAME not in eb.name:
            eb.parent = root_eb
        elif target_eb and target_eb == first_eb and KAFEI_TMP_BONE_NAME not in eb.name:
            # 如果骨骼的末端指向first_bone，则将其改为末端指向root_bone
            eb.tail = root_eb.head
    # 设置显示枠
    if base_props.enable_gen_frame_checked:
        set_root_frame(armature, root_bl, first_eb.name)
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[root_jp]))


def create_dummy_bone(armature, props, results):
    def callback1(vec):
        return Vector((-vec.z, 0, vec.x))

    def callback2(vec):
        return Vector((vec.z, 0, -vec.x))

    base_props = props.base
    if not base_props.dummy_checked:
        return

    dummy_infos = [
        ("右ダミー", "dummy_R", "右手首", "右中指１", callback1),
        ("左ダミー", "dummy_L", "左手首", "左中指１", callback2)
    ]
    for i, info in enumerate(dummy_infos):
        # 基本名称信息
        dummy_jp = info[0]
        dummy_en = info[1]
        dummy_bl = convertNameToLR(dummy_jp)
        wrist_jp = info[2]
        middle_finger_jp = info[3]

        # 先决条件校验
        if dummy_jp in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[dummy_jp]))
            continue
        required_bones = [wrist_jp, middle_finger_jp]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = [dummy_jp]
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
            continue

        # 常用参数获取
        scale = props.scale
        edit_bones = armature.data.edit_bones

        # 补充名称信息（blender）
        wrist_bl = jp_bl_map[wrist_jp]
        middle_finger_bl = jp_bl_map[middle_finger_jp]
        # 补充骨骼信息
        wrist_eb = edit_bones.get(wrist_bl)
        middle_finger_eb = edit_bones.get(middle_finger_bl)

        # 创建手持骨
        dummy_eb = create_bone_with_mmd_info(armature, dummy_bl, dummy_jp, dummy_en)
        # 设置是否可移动 可旋转 可操作
        set_movable(armature, dummy_bl, True)
        set_rotatable(armature, dummy_bl, True)
        set_controllable(armature, dummy_bl, True)
        # 计算基础数据
        wrist_head_vec = Vector(wrist_eb.head)
        middle_finger_eb_head_vec = Vector(
            (middle_finger_eb.head[0], wrist_eb.head[1], middle_finger_eb.head[2]))
        center_vec = (wrist_head_vec + middle_finger_eb_head_vec) * 0.5
        normalized_vec = Vector((middle_finger_eb_head_vec - wrist_head_vec) / scale).normalized() * scale
        res = info[4](normalized_vec)
        # 设置dummy骨骼head tail parent 旋转轴
        dummy_eb.head = center_vec + Vector((res.x * 0.25, 0, res.z * 0.25))
        dummy_eb.tail = dummy_eb.head + Vector((res.x * 1.2, 0, res.z * 1.2))
        dummy_eb.parent = wrist_eb
        FnBone.update_auto_bone_roll(dummy_eb)
        # 设置显示枠
        if base_props.enable_gen_frame_checked:
            add_item_after(armature, dummy_bl, jp_bl_map[wrist_jp])
        results.append(SsbResult(status=SsbStatus.SUCCESS, result=[dummy_jp]))


def create_groove_bone(armature, props, results):
    base_props = props.base
    if not base_props.groove_checked:
        return

    # 基本名称信息
    groove_jp = 'グルーブ'
    groove_en = 'groove'
    groove_bl = convertNameToLR(groove_jp)

    # 先决条件校验
    if groove_jp in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[groove_jp]))
        return
    if 'センター' not in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.FAILED, result=[groove_jp, 'センター']))
        return

    # 常用参数获取
    scale = props.scale
    edit_bones = armature.data.edit_bones

    # 创建グルーブ骨骼
    groove_eb = create_bone_with_mmd_info(armature, groove_bl, groove_jp, groove_en)
    # 设置是否可移动 可旋转 可操作
    set_movable(armature, groove_bl, True)
    set_rotatable(armature, groove_bl, True)
    set_controllable(armature, groove_bl, True)
    # 设置グルーブ骨骼 head tail parent
    center_eb = edit_bones.get("センター", None)
    groove_eb.head = center_eb.head + get_loc_by_xzy((0, 0.2, 0), scale)
    groove_eb.tail = groove_eb.head + get_loc_by_xzy((0, 1.4, 0), scale)
    groove_eb.parent = center_eb

    # 修改指向
    center_saki_pattern = r'^センター先(\.\d{3})?$'  # PE中允许同名但是blender中会重命名为.001
    for eb in edit_bones:
        if eb.parent == center_eb and not re.match(center_saki_pattern, eb.name) and KAFEI_TMP_BONE_NAME not in eb.name:
            eb.parent = groove_eb
    # 设置显示枠
    if base_props.enable_gen_frame_checked:
        flag = add_item_after(armature, groove_bl, "センター")
        if not flag:
            pmx_root = find_pmx_root_with_child(armature)
            frame = create_center_frame(pmx_root)
            do_add_item(frame, 'BONE', groove_bl, order=-1)

    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[groove_jp]))


def get_loc_by_xzy(loc, scale):
    """获取pmx模型在blender中的位置"""
    vector = Vector(loc).xzy if all(math.isfinite(n) for n in loc) else Vector((0, 0, 0))
    return vector * scale


def create_view_center_bone(armature, props, results):
    base_props = props.base
    if not base_props.view_center_checked:
        return

    # 基本名称信息
    view_center_jp = '操作中心'
    view_center_en = 'view cnt'
    view_center_bl = convertNameToLR(view_center_jp)

    # 先决条件校验
    if view_center_jp in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[view_center_jp]))
        return

    # 常用参数获取
    scale = props.scale
    edit_bones = armature.data.edit_bones
    pose_bones = armature.pose.bones
    objs = find_pmx_objects(armature)

    # 创建“操作中心”骨骼
    view_center_eb = create_bone_with_mmd_info(armature, view_center_bl, view_center_jp, view_center_en)
    # 设置是否可移动 可旋转 可操作
    set_movable(armature, view_center_bl, True)
    set_rotatable(armature, view_center_bl, True)
    set_controllable(armature, view_center_bl, True)
    # 设置tail 尖端骨骼
    view_center_eb.tail = Vector((0, 0, 1)) * scale
    view_center_pb = pose_bones[view_center_bl]
    view_center_pb.mmd_bone.is_tip = True
    # 设置剩余骨骼的parent和target
    first_vg = get_first_vg(armature, objs, view_center_bl)
    first_eb = edit_bones[first_vg.name]
    for eb in edit_bones:
        target_bone = get_target_bone(armature, eb)
        if target_bone == first_eb and KAFEI_TMP_BONE_NAME not in eb.name:
            # 如果骨骼的末端指向first_bone，则将其改为末端指向view_center_bone
            eb.tail = view_center_eb.head

    # 设置显示枠（流程同全亲骨）
    if base_props.enable_gen_frame_checked:
        set_root_frame(armature, view_center_bl, first_eb.name)
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[view_center_jp]))


def get_first_vg(armature, objs, exclude_name):
    """获取（排除自身后）排在首位的顶点组（对应的骨骼）"""

    # 如果对象拥有导入时的骨架修改器，可最大程度上确保顶点组的完整；如果没有骨架修改器，则会尽可能的寻找
    for obj in objs:
        if obj.modifiers.get('mmd_bone_order_override', None):
            for vg in obj.vertex_groups:
                if vg.name != exclude_name and armature.pose.bones.get(vg.name):
                    return vg
    for obj in objs:
        for vg in obj.vertex_groups:
            if vg.name != exclude_name and armature.pose.bones.get(vg.name):
                return vg
    raise RuntimeError(f"未在骨架为'{armature.name}'的物体中发现目标顶点组！")


def gen_bone_name_map(armature):
    """根据当前骨架生成骨骼名称映射"""
    # 显示声明以改变引用
    global jp_bl_map
    global bl_jp_map
    jp_bl_map = {}
    bl_jp_map = {}
    for pose_bone in armature.pose.bones:
        # 如果导入模型的时候jp_name为空串，则blender会创建名称为Bone.xxx的骨骼，插件也会设置该名称
        # 如果导入模型的时候jp_name相同，blender会创建名称为.xxx的骨骼，插件也会设置该名称
        # 所以除非刻意在blender中设置mmd_bone.name_j为空串，否则基本上不会出现jp_name重复的情况
        name_jp = pose_bone.mmd_bone.name_j
        name_bl = pose_bone.name
        jp_bl_map[name_jp] = name_bl
        bl_jp_map[name_bl] = name_jp


def set_movable(armature, bone_name, movable):
    """设置骨骼在blender和mmd中是否可移动"""
    pb = armature.pose.bones.get(bone_name)
    if not pb:
        return
    pb.lock_location = (not movable, not movable, not movable)


def set_rotatable(armature, bone_name, rotatable):
    """设置骨骼在blender和mmd中是否可旋转"""
    pb = armature.pose.bones.get(bone_name)
    if not pb:
        return
    pb.lock_rotation = (not rotatable, not rotatable, not rotatable)


def set_controllable(armature, bone_name, controllable):
    """
    设置骨骼在blender和mmd中是否可操作,
    不可操作在mmd中代表了无法移动旋转，但是在blender中仅仅是打了个tag，无其它额外操作
    """

    pb = armature.pose.bones.get(bone_name)
    if not pb:
        return
    pb.mmd_bone.is_controllable = controllable


def set_root_frame(armature, root_bl, first_bl):
    pmx_root = find_pmx_root_with_child(armature)
    found_frame, found_item = find_bone_item(pmx_root, first_bl)
    if not found_frame and not found_item:
        # 创建センター显示枠
        frame = create_center_frame(pmx_root)
        # 创建first_bone元素并将其移动到第0位
        do_add_item(frame, 'BONE', first_bl, order=0)
    mmd_root = pmx_root.mmd_root
    frames = mmd_root.display_item_frames
    if frames:
        # 获取首位显示枠（root）
        first_frame = frames[0]
        # 移除root里面的元素
        first_frame.data.clear()
        first_frame.active_item = 0
        # 创建root_bone元素并将其移动到第0位
        do_add_item(first_frame, 'BONE', root_bl, order=0)


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
