from enum import auto

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

        # 获取base_props对象的所有属性名
        all_props = dir(base_props)

        # 如果所有值都为True，则将所有值都设置为False；只要有一个值不为True，则将所有值设置为True；不含enable属性
        set_to_true = False
        for prop_name in all_props:
            if "enable" not in prop_name and isinstance(getattr(base_props, prop_name), bool):
                # 如果有任何一个属性不为True，则将所有符合条件的属性都设置为True
                if not getattr(base_props, prop_name):
                    set_to_true = True
                    break
                # 否则将所有符合条件的属性设置为False
                else:
                    set_to_true = False
        for prop_name in all_props:
            if "enable" not in prop_name and isinstance(getattr(base_props, prop_name), bool):
                setattr(base_props, prop_name, set_to_true)


def pre_set_panel_order(armature):
    """通过与临时物体合并的方式预先创建顶点组（对应PE中的骨骼面板）"""
    objs = find_pmx_objects(armature)
    if has_all_ssb(armature):
        return

    # pmx模型的首个Mesh对象
    pmx_obj = objs[0]
    # 创建临时物体
    collection = pmx_obj.users_collection[0]
    tmp_obj = create_tmp_obj(armature, collection)

    # 设置面板中位于前面的顶点组
    for name_j in SSB_ORDER_TOP_LIST:
        if convertNameToLR(name_j) not in tmp_obj.vertex_groups:
            tmp_obj.vertex_groups.new(name=convertNameToLR(name_j))
    # 设置面板中位于中间的顶点组
    for vg in pmx_obj.vertex_groups:
        vg_name_b = vg.name
        # 顶点组如果不在当前骨架中则跳过
        if vg_name_b not in bl_jp_map.keys():
            continue
        vg_name_j = bl_jp_map[vg.name]
        if vg_name_j in SSB_ORDER_MAP.keys():
            items = SSB_ORDER_MAP[vg_name_j]
            for item_name_j in items:
                item_name_b = convertNameToLR(item_name_j)
                if item_name_b not in tmp_obj.vertex_groups:
                    tmp_obj.vertex_groups.new(name=item_name_b)
        else:
            if vg_name_b not in tmp_obj.vertex_groups:
                tmp_obj.vertex_groups.new(name=vg_name_b)
    # 设置面板中位于底部的顶点组
    for name_j in SSB_ORDER_BOTTOM_LIST:
        if convertNameToLR(name_j) not in tmp_obj.vertex_groups:
            tmp_obj.vertex_groups.new(name=convertNameToLR(name_j))

    # 为物体添加顶点组
    # 通常情况下，只需要为第一个物体预先设置顶点组即可
    # 但是如果后续逻辑涉及到权重转换，或者是使用者修改了物体的顺序时，都可能会产生问题
    # 稳妥起见，为所有物体都设置上相应的顶点组
    for obj in objs:
        deselect_all_objects()
        obj_name = obj.name
        current_tmp_obj = copy_obj(tmp_obj)
        select_and_activate(obj)
        select_and_activate(current_tmp_obj)
        bpy.ops.object.join()
        current_obj = bpy.context.active_object
        current_obj.name = obj_name

    # 从集合中移除对象
    collection.objects.unlink(tmp_obj)
    # 从场景中删除对象
    bpy.data.objects.remove(tmp_obj, do_unlink=True)


def has_all_ssb(armature):
    count = 0
    for pb in armature.pose.bones:
        if bl_jp_map[pb.name] in SSB_NAMES:
            count += 1
    if count == len(SSB_NAMES):
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
        batch = props.batch
        batch_flag = batch.flag
        if not batch_flag:
            if not model:
                self.report(type={'ERROR'}, message=f'请选择MMD模型！')
                return False
            pmx_root = find_pmx_root_with_child(model)
            if not pmx_root:
                self.report(type={'ERROR'}, message=f'请选择MMD模型！')
                return False
            pmx_armature = find_pmx_armature(pmx_root)
            if not pmx_armature:
                self.report(type={'ERROR'}, message=f'模型骨架不存在！')
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
        model = props.model
        pmx_root = find_pmx_root_with_child(model)

        if batch_flag:
            batch_process(self.create_ssb, props)
        else:
            results = self.create_ssb(pmx_root, props)
            armature = find_pmx_armature(pmx_root)
            duration = time.time() - start_time
            self.show_msg(armature, props, results, duration)

    def create_ssb(self, pmx_root, props):
        # 获取模型数据
        armature = find_pmx_armature(pmx_root)
        # 显示根节点与骨架，避免引起上下文异常
        show_object(pmx_root)
        show_object(armature)
        deselect_all_objects()
        select_and_activate(armature)
        # 根据当前骨架生成骨骼名称映射
        gen_bone_name_map(armature)
        # 在mmd插件中，模型的PE骨骼面板顺序是根据blender顶点组来决定的
        # 但是在blender中，移动顶点组是一项非常耗时的操作
        # 顶点组所在的集合类型并不像其它集合那样，拥有移动到指定位置的函数。需要我们模拟界面点击的方式一个一个循环移动到指定位置
        # 这里通过新建一个Mesh，并为其预先添加顶点组，然后用这个Mesh和原模型合并的方式来达到设置骨骼面板的目的
        pre_set_panel_order(armature)
        # 根据勾选的选项追加次标准骨骼
        # todo 增加用户提供的参数
        # todo 先对参数进行校验，得出需要对哪些内容进行添加（但是不管怎样流程都是能走通的）
        # todo 给出反馈，已经存在的不需要给出反馈，如果全部正常添加则给出正常反馈，一旦有一些内容添加不成功用警告（没有能追加的骨骼 改为 哪些骨骼因某种原因添加不成功）
        # todo 需要有添加是否成功的 result
        # 进入编辑模式，并确保添加ssb期间不涉及模式切换
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        # 接收返回结果的列表
        results = []
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
        # 返回物体模式
        bpy.ops.object.mode_set(mode='OBJECT')
        deselect_all_objects()
        select_and_activate(armature)
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
                self.report({'WARNING'}, "没有能追加的骨骼，请尝试“强制”选项。点击查看缺失骨骼↑↑↑")


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
    if base_props.waist_checked:
        bones.extend(["右足IK親", "左足IK親"])
    if base_props.view_center_checked:
        bones.append("操作中心")
    if base_props.ex_checked:
        bones.extend(["右足D", "右ひざD", "右足首D", "右足先EX", "左足D", "左ひざD", "左足首D", "左足先EX"])
    if base_props.groove_checked:
        bones.extend(["右ダミー", "左ダミー"])
    if base_props.shoulder_p_checked:
        bones.extend(["右肩P", "右肩C", "左肩P", "左肩C"])
    if base_props.thumb0_checked:
        bones.extend(["右親指０", "右親指１"])
    return bones


def create_ex_bone(armature, props, results):
    base_props = props.base
    if not base_props.ex_checked:
        return

    scale = props.scale
    ex_infos = [
        ("左足先EX", "toe2_L", "左足", "左ひざ", "左足首", "左つま先ＩＫ"),
        ("右足先EX", "toe2_R", "右足", "右ひざ", "右足首", "右つま先ＩＫ")
    ]
    for info in ex_infos:
        # 基本名称信息
        ex_name_j = info[0]
        ex_name_e = info[1]
        ex_name_b = convertNameToLR(ex_name_j)
        leg_name_j = info[2]
        knee_name_j = info[3]
        ankle_name_j = info[4]
        toe_ik_name_j = info[5]
        # todo 源码中controllable初始为False且并未看见被修改为True的逻辑，但实际上应该是取决于传入的参数
        controllable = base_props.enable_leg_d_controllable_checked

        # 先决条件校验
        if ex_name_j in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[ex_name_j]))
            continue
        required_bones = [leg_name_j, knee_name_j, ankle_name_j, toe_ik_name_j]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = [ex_name_j]
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
            continue

        # 基本名称信息（blender）
        leg_name_b = jp_bl_map[leg_name_j]
        knee_name_b = jp_bl_map[knee_name_j]
        ankle_name_b = jp_bl_map[ankle_name_j]
        toe_ik_name_b = jp_bl_map[toe_ik_name_j]

        # 创建D骨以及EX骨
        leg_d_name_j, leg_d_name_b = create_d_bone(armature, scale, leg_name_j, controllable)
        knee_d_name_j, knee_d_name_b = create_d_bone(armature, scale, knee_name_j, controllable)
        ankle_d_name_j, ankle_d_name_b = create_d_bone(armature, scale, ankle_name_j, controllable)
        create_bone_with_mmd_info(armature, ex_name_b, ex_name_j, ex_name_e)
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.armature.select_all(action='DESELECT')
        edit_bones = armature.data.edit_bones
        leg_d_bone = edit_bones[leg_d_name_b]
        knee_d_bone = edit_bones[knee_d_name_b]
        ankle_d_bone = edit_bones[ankle_d_name_b]
        ankle_bone = edit_bones[ankle_name_b]
        toe_ik_d_bone = edit_bones[toe_ik_name_b]
        ex_bone = edit_bones[ex_name_b]
        set_visible(armature, ex_name_b, True)
        set_movable(armature, ex_name_b, False)
        set_rotatable(armature, ex_name_b, True)
        set_controllable(armature, ex_name_b, True)
        ex_bone.head = (1 - 2.0 / 3.0) * ankle_d_bone.head + 2.0 / 3.0 * toe_ik_d_bone.head
        ex_bone.tail = ex_bone.head + Vector((0, -1 * scale, 0))
        pose_bones = armature.pose.bones
        # 设置EX骨变形阶层
        pose_bones.get(ex_name_b).mmd_bone.transform_order = pose_bones.get(ankle_d_name_b).mmd_bone.transform_order
        # 设置父级关系
        knee_d_bone.parent = leg_d_bone
        ankle_d_bone.parent = knee_d_bone
        ex_bone.parent = ankle_d_bone
        bpy.ops.mmd_tools.apply_additional_transform()
        objs = find_pmx_objects(armature)
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = armature.data.edit_bones
        ankle_bone = edit_bones[ankle_name_b]
        ex_bone = edit_bones[ex_name_b]
        for obj in objs:
            for vertex in obj.data.vertices:
                if is_vertex_dedicated_by_bone(obj, vertex, ankle_name_b, threshold=0.97):
                    ankle_y = ankle_bone.head.y
                    ex_y = ex_bone.head.y
                    center = (vertex.co.y - ankle_y) / (ex_y - ankle_y)
                    weight = np.clip((center - 0.75) * 2.0, 0.0, 1.0)
                    for group in vertex.groups:
                        obj.vertex_groups[group.group].remove([vertex.index])
                    obj.vertex_groups[ex_name_b].add([vertex.index], weight, 'ADD')
                    obj.vertex_groups[ankle_name_b].add([vertex.index], 1 - weight, 'ADD')
        for obj in objs:
            for vertex in obj.data.vertices:
                for vg in vertex.groups:
                    group_name = obj.vertex_groups[vg.group].name
                    weight = vg.weight
                    if group_name == leg_name_b:
                        obj.vertex_groups[leg_name_b].remove([vertex.index])
                        obj.vertex_groups[leg_d_name_b].add([vertex.index], weight, 'ADD')
                    if group_name == knee_name_b:
                        obj.vertex_groups[knee_name_b].remove([vertex.index])
                        obj.vertex_groups[knee_d_name_b].add([vertex.index], weight, 'ADD')
                    if group_name == ankle_name_b:
                        obj.vertex_groups[ankle_name_b].remove([vertex.index])
                        obj.vertex_groups[ankle_d_name_b].add([vertex.index], weight, 'ADD')
        # 足骨刚体移动到足D骨
        pmx_root = find_pmx_root_with_child(armature)
        rigid_group = find_rigid_group(pmx_root)
        if rigid_group:
            for rigid_body in rigid_group.children:
                if rigid_body.mmd_rigid.bone == leg_name_b:
                    rigid_body.mmd_rigid.bone = leg_d_name_b
                if rigid_body.mmd_rigid.bone == knee_name_b:
                    rigid_body.mmd_rigid.bone = knee_d_name_b
                if rigid_body.mmd_rigid.bone == ankle_name_b:
                    rigid_body.mmd_rigid.bone = ankle_d_name_b
        if base_props.enable_gen_frame_checked:
            add_item_after(armature, ex_name_b, ankle_name_b)
            if controllable:
                add_item_after(armature, ankle_d_name_b, ankle_name_b)
                add_item_after(armature, knee_d_name_b, knee_name_b)
                add_item_after(armature, leg_d_name_b, leg_name_b)
        results.append(
            SsbResult(status=SsbStatus.SUCCESS, result=[ex_name_j, leg_d_name_j, knee_d_name_j, ankle_d_name_j]))


def create_d_bone(armature, scale, bone_name_j, controllable):
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.armature.select_all(action='DESELECT')
    edit_bones = armature.data.edit_bones
    bone_name_b = convertNameToLR(bone_name_j)
    source_bone = edit_bones[bone_name_b]
    source_mmd_bone = armature.pose.bones.get(bone_name_b).mmd_bone
    source_name_j = source_mmd_bone.name_j
    source_name_e = source_mmd_bone.name_e
    new_name_j = source_name_j + "D"
    new_name_e = source_name_e + "D"
    new_name_b = convertNameToLR(new_name_j)
    create_bone_with_mmd_info(armature, new_name_b, new_name_j, new_name_e)
    jp_bl_map[new_name_j] = new_name_b
    bl_jp_map[new_name_b] = new_name_j
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.armature.select_all(action='DESELECT')
    edit_bones = armature.data.edit_bones
    source_bone = edit_bones[bone_name_b]
    new_bone = edit_bones[new_name_b]
    new_mmd_bone = armature.pose.bones.get(new_name_b).mmd_bone
    new_mmd_bone.name_j = new_name_j
    new_mmd_bone.name_e = new_name_e
    new_bone.head = source_bone.head
    new_bone.tail = new_bone.head + Vector((0, 0, 1)) * scale
    new_bone.parent = source_bone.parent
    movable = all(loc is False for loc in armature.pose.bones.get(bone_name_b).lock_location)
    rotatable = all(loc is False for loc in armature.pose.bones.get(bone_name_b).lock_rotation)
    set_movable(armature, new_name_b, movable)
    set_rotatable(armature, new_name_b, rotatable)
    set_visible(armature, new_name_b, controllable)
    set_controllable(armature, new_name_b, controllable)
    # 设置赋予信息
    new_mmd_bone.has_additional_rotation = True
    new_mmd_bone.additional_transform_influence = 1
    new_mmd_bone.additional_transform_bone = bone_name_b
    new_mmd_bone.is_tip = True
    # 设置变形阶层
    source_mmd_bone = armature.pose.bones.get(bone_name_b).mmd_bone
    new_mmd_bone.transform_order = source_mmd_bone.transform_order + 1
    # 设置剩余内容 原逻辑足D骨是从足骨上面拷贝而来的，但是在blender中进行拷贝的话
    # 1：选中edit bone进行复制，但是复制后需要切换上下文才能获取pose_bone的bone属性
    # 2：mmd属性中有一个叫ik_rotation_constraint，如果一起拷贝过来，会很碍事
    # 所以这里通过新建骨骼并传递指定参数的方式来模拟拷贝（但后面这几项参数几乎用不上，仅做拷贝）
    new_mmd_bone.transform_after_dynamics = source_mmd_bone.transform_after_dynamics
    # 默认不会应用固定轴
    new_mmd_bone.enabled_fixed_axis = source_mmd_bone.enabled_fixed_axis
    new_mmd_bone.fixed_axis = source_mmd_bone.fixed_axis
    new_mmd_bone.enabled_local_axes = source_mmd_bone.enabled_local_axes
    new_mmd_bone.local_axis_x = source_mmd_bone.local_axis_x
    new_mmd_bone.local_axis_z = source_mmd_bone.local_axis_z
    if new_mmd_bone.enabled_local_axes:
        bpy.context.view_layer.objects.active = armature
        bpy.ops.mmd_tools.bone_local_axes_setup(type='APPLY')
    return new_name_j, new_name_b


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
    scale = props.scale
    for index, info in enumerate(thumb0_infos):
        # 基本名称信息
        thumb0_name_j = info[0]
        thumb0_name_e = info[1]
        thumb0_name_b = convertNameToLR(thumb0_name_j)
        wrist_name_j = info[2]
        thumb1_name_j = info[3]
        thumb2_name_j = info[4]
        fore1_name_j = info[5]
        direction = info[6]

        # 先决条件校验
        if thumb0_name_j in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[thumb0_name_j]))
            continue
        required_bones = [wrist_name_j, thumb1_name_j]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = [thumb0_name_j]
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
            continue

        # 基本名称信息（blender）
        wrist_name_b = jp_bl_map[wrist_name_j]
        thumb1_name_b = jp_bl_map[thumb1_name_j]
        thumb2_name_b = jp_bl_map[thumb2_name_j]
        fore1_name_b = jp_bl_map[fore1_name_j]

        # 创建亲指0
        create_bone_with_mmd_info(armature, thumb0_name_b, thumb0_name_j, thumb0_name_e)
        set_visible(armature, thumb0_name_b, True)
        set_movable(armature, thumb0_name_b, False)
        set_rotatable(armature, thumb0_name_b, True)
        set_controllable(armature, thumb0_name_b, True)
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = armature.data.edit_bones
        thumb0_bone = edit_bones.get(thumb0_name_b)
        thumb1_bone = edit_bones.get(thumb1_name_b)
        thumb2_bone = edit_bones.get(thumb2_name_b)
        fore1_bone = edit_bones.get(fore1_name_b)
        wrist_bone = edit_bones.get(wrist_name_b)
        thumb0_bone.head = (1 - 2.0 / 3.0) * wrist_bone.head + (2.0 / 3.0) * thumb1_bone.head
        thumb0_bone.parent = wrist_bone
        thumb1_bone.parent = thumb0_bone
        thumb0_bone.tail = thumb1_bone.head
        # 亲指1和亲指0之间的距离
        length = Vector(thumb1_bone.head - thumb0_bone.head).length
        objs = find_pmx_objects(armature)
        for obj in objs:
            for vertex in obj.data.vertices:
                if not contains_bone(obj, vertex, [wrist_name_b, thumb1_name_b]):
                    continue
                # 顶点 与 亲指0和亲指1中点 的距离（向量）
                distance = Vector(vertex.co) - Vector((thumb0_bone.head + thumb1_bone.head) * 0.5)
                # distance 在 direction 上面的投影长度（及方向）
                projection = distance.dot(direction) * direction
                # 计算权重
                weight = Vector(distance - projection).length
                weight /= length * 1.4
                if weight < 1.0:
                    # 将权重限定在0-1之间
                    weight = np.clip((1.0 - weight) * 1.3, 0.0, 1.0)
                    # 如果顶点受手首影响（阈值0.97）
                    if is_vertex_dedicated_by_bone(obj, vertex, wrist_name_b, threshold=0.97):
                        for group in vertex.groups:
                            obj.vertex_groups[group.group].remove([vertex.index])
                        obj.vertex_groups[thumb0_name_b].add([vertex.index], weight, 'ADD')
                        obj.vertex_groups[wrist_name_b].add([vertex.index], 1 - weight, 'ADD')
                    # 如果顶点受亲指1影响（阈值0.97）
                    elif is_vertex_dedicated_by_bone(obj, vertex, thumb1_name_b, threshold=0.97):
                        for group in vertex.groups:
                            obj.vertex_groups[group.group].remove([vertex.index])
                        obj.vertex_groups[thumb0_name_b].add([vertex.index], weight, 'ADD')
                        obj.vertex_groups[thumb1_name_b].add([vertex.index], 1 - weight, 'ADD')
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
                            if group_name == wrist_name_b:
                                bone_weight = vg.weight
                                # 将顶点在手首上的权重转移到亲指0上面
                                obj.vertex_groups[wrist_name_b].remove([vertex.index])
                                obj.vertex_groups[thumb0_name_b].add([vertex.index], bone_weight, 'ADD')
                                if bone_weight < weight:
                                    obj.vertex_groups[thumb0_name_b].remove([vertex.index])
                                    obj.vertex_groups[thumb0_name_b].add([vertex.index], weight, 'ADD')
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
            add_item_before(armature, thumb0_name_b, thumb1_name_b)
        results.append(SsbResult(status=SsbStatus.SUCCESS, result=[thumb0_name_j]))
        # 设定親指Local轴
        if not base_props.enable_thumb_local_axes_checked:
            continue
        required_bones = [thumb0_name_j, thumb1_name_j, thumb2_name_j, fore1_name_j]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = []
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, message=f'设定親指Local轴所需的{not_found_list}不存在'))
            continue

        # todo 在设置本地轴z轴的时候，blender中显示的是一个值，PE中显示的是另一个值，在设置固定轴的时候，这个值能通过to_pmx_axis修正（未大量测试）
        # todo 但是这里却不能，虽然暂时无法修正为和PE中一模一样，但是使用上没问题
        set_local_axes(armature, thumb0_name_b,
                       Vector(thumb1_bone.head - thumb0_bone.head).normalized().xzy,
                       to_pmx_axis(armature, scale, Vector(thumb0_bone.head - fore1_bone.head).normalized(),
                                   thumb0_name_b))
        # mmd坐标系
        axis_z = info[7](Vector(thumb2_bone.head - thumb1_bone.head).xzy)
        axis_z.z = -axis_z.length * 0.2
        set_local_axes(armature, thumb1_name_b,
                       Vector(thumb2_bone.head - thumb1_bone.head).normalized().xzy,
                       axis_z)
        # 获取親指先
        target_bone = get_target_bone(armature, thumb2_bone)
        if target_bone:
            thumb2_target_head = target_bone.head
        else:
            thumb2_target_head = thumb2_bone.tail
        set_local_axes(armature, thumb2_name_b,
                       Vector(thumb2_target_head - thumb2_bone.head).normalized().xzy,
                       axis_z)

    bpy.context.view_layer.objects.active = armature
    bpy.ops.mmd_tools.bone_local_axes_setup(type='APPLY')


def set_local_axes(armature, bone_name, x, z):
    pose_bone = armature.pose.bones.get(bone_name)
    mmd_bone = pose_bone.mmd_bone
    mmd_bone.enabled_local_axes = True
    mmd_bone.local_axis_x = x
    mmd_bone.local_axis_z = z


def contains_bone(obj, vertex, names):
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
    base_props = props.base
    scale = props.scale

    # 基本名称信息
    twist_name_j = info[0]
    twist_name_e = info[1]
    twist_name_b = convertNameToLR(info[0])
    twist_parent_name_j = info[2]
    twist_child_name_j = info[3]

    # 先决条件校验
    if twist_name_j in jp_bl_map.keys():
        return SsbResult(status=SsbStatus.SKIPPED, result=[twist_name_j])
    required_bones = [twist_parent_name_j, twist_child_name_j]
    if any(name not in jp_bl_map for name in required_bones):
        not_found_list = [twist_name_j]
        for bone_name in required_bones:
            if bone_name not in jp_bl_map:
                not_found_list.append(bone_name)
        return SsbResult(status=SsbStatus.FAILED, result=not_found_list)

    # 基本名称信息（blender）
    twist_parent_name_b = jp_bl_map[twist_parent_name_j]
    twist_child_name_b = jp_bl_map[twist_child_name_j]

    edit_bones = armature.data.edit_bones
    twist_child_bone = edit_bones.get(twist_child_name_b)
    twist_child_bone_head_vector = twist_child_bone.head.copy()
    objs = find_pmx_objects(armature)

    # 自动补正旋转轴（修正腕捩所在位置）
    if has_elbow_offset and base_props.enable_elbow_offset_checked:
        v_count = 0.0
        loc_y_sum = 0.0
        for obj in objs:
            for vertex in obj.data.vertices:
                if is_vertex_dedicated_by_bone(obj, vertex, twist_parent_name_b, threshold=0.6):
                    loc_y_sum += vertex.co.y / scale
                    v_count = v_count + 1.0
        if v_count > 0.0:
            offset = (loc_y_sum / v_count * scale - twist_child_bone.head.y) * 0.75
            twist_child_bone_head_vector.y += offset

    # 创建捩骨
    create_bone_with_mmd_info(armature, twist_name_b, twist_name_j, twist_name_e)
    set_visible(armature, twist_name_b, True)
    set_movable(armature, twist_name_b, False)
    twist_pb = armature.pose.bones.get(twist_name_b, None)
    twist_pb.mmd_bone.is_tip = True
    # 设置锁定旋转，如果是tip且未应用固定轴时需特殊处理
    twist_pb.lock_rotation = (True, False, True)
    set_controllable(armature, twist_name_b, True)
    # 获取捩骨
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    twist_bone = edit_bones.get(twist_name_b)
    twist_parent_bone = edit_bones.get(twist_parent_name_b)
    twist_parent_bone_head = twist_parent_bone.head.copy()
    twist_child_bone = edit_bones.get(twist_child_name_b)
    twist_child_bone_head = twist_child_bone.head.copy()
    twist_bone.parent = twist_parent_bone
    twist_bone_head = Vector(twist_parent_bone_head * 0.4 + twist_child_bone_head_vector * 0.6).copy()
    twist_bone.head = twist_bone_head
    # 设置轴限制相关参数（mmd坐标系）,默认不会应用
    armature.pose.bones.get(twist_name_b).mmd_bone.enabled_fixed_axis = True
    tmp_axis = twist_child_bone_head_vector - twist_parent_bone_head
    # todo 如果开启自动补正旋转轴，fixed_axis的值在小数点后第5位存在误差，需后续多测试看下
    # 由于用MEIKO时数值不一致，但是用Miku_Hatsune时数值一致，暂定为误差
    # todo 默认不会装配只设置，后续看要不要提供用户参数
    # fixed_axis计算长度时，需要考虑缩放
    # 计算点积时，仅考虑fixed_axis的方向，fixed_axis的大小应为1，以便在最大值和最小值之间插值（值取决于在方向上的延伸即后者，而非fixed_axis的长度）
    fixed_axis = to_pmx_axis(armature, scale, tmp_axis, twist_name_b)
    armature.pose.bones.get(twist_name_b).mmd_bone.fixed_axis = fixed_axis
    twist_bone.tail = twist_bone.head + fixed_axis.xzy.normalized() * scale
    FnBone.update_auto_bone_roll(twist_bone)
    twist_child_bone.parent = twist_bone
    twist_parent_bone_dedicated_vertices = {}

    twist_parent_bone_dot = Vector(twist_parent_bone_head - twist_bone_head).dot(fixed_axis.xzy) * 0.8
    twist_child_bone_dot = Vector(twist_child_bone_head - twist_bone_head).dot(fixed_axis.xzy) * 0.8
    for obj in objs:
        for vertex in obj.data.vertices:
            v_twist_bone_dot = Vector(Vector(vertex.co) - twist_bone.head).dot(fixed_axis.xzy)
            if is_vertex_dedicated_by_bone(obj, vertex, twist_parent_name_b, threshold=0.97):
                twist_parent_bone_dot = min(twist_parent_bone_dot, v_twist_bone_dot)
                twist_child_bone_dot = max(twist_child_bone_dot, v_twist_bone_dot)
                twist_parent_bone_dedicated_vertices[vertex] = obj
            elif v_twist_bone_dot > 0.0:
                for group in vertex.groups:
                    if obj.vertex_groups[group.group].name == twist_parent_name_b:
                        name_b_group_index = obj.vertex_groups.find(twist_name_b)
                        if name_b_group_index != -1:
                            obj.vertex_groups[name_b_group_index].add([vertex.index], group.weight, 'ADD')
                        # 移除操作放到最后
                        obj.vertex_groups[group.group].remove([vertex.index])
                        break
    part_twists = []
    part_twist_name_j_list = []
    for i in range(3):
        coefficient = (i + 1) / 4.0
        # 基本名称信息
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        part_twist_name_j = twist_name_j + str(i + 1)
        part_twist_name_j_list.append(part_twist_name_j)
        part_twist_name_b = convertNameToLR(part_twist_name_j)
        part_twists.append(part_twist_name_b)
        # 查找part捩骨是否存在，存在则移除
        if part_twist_name_j in jp_bl_map:
            remove_bone(armature, objs, part_twist_name_b)
        # 创建剩余捩骨
        create_bone_with_mmd_info(armature, part_twist_name_b, part_twist_name_j, "")
        # 设置可见性暂时为True
        set_visible(armature, part_twist_name_b, True)
        set_movable(armature, part_twist_name_b, False)
        set_rotatable(armature, part_twist_name_b, True)
        set_controllable(armature, part_twist_name_b, True)
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = armature.data.edit_bones
        part_twist_bone = edit_bones[part_twist_name_b]
        part_twist_bone.head = twist_bone_head + fixed_axis.xzy * (
                (1 - coefficient) * twist_parent_bone_dot + coefficient * twist_child_bone_dot)
        part_twist_bone.tail = part_twist_bone.head + Vector((0, 0, 1)) * scale
        twist_parent_bone = edit_bones.get(twist_parent_name_b)
        part_twist_bone.parent = twist_parent_bone
        # 设置赋予相关信息
        pose_bones = armature.pose.bones
        mmd_bone = pose_bones[part_twist_name_b].mmd_bone
        mmd_bone.has_additional_rotation = True
        mmd_bone.additional_transform_influence = coefficient
        mmd_bone.additional_transform_bone = twist_name_b
        # 设置尖端骨骼
        pose_bones[part_twist_name_b].mmd_bone.is_tip = True
        # 装配骨骼
        pose_bones[part_twist_name_b].bone.select = True
        bpy.context.view_layer.objects.active = armature
        bpy.ops.mmd_tools.apply_additional_transform()
        pose_bones[part_twist_name_b].bone.select = False
        # 恢复可见性为False
        set_visible(armature, part_twist_name_b, False)
    for vertex, obj in twist_parent_bone_dedicated_vertices.items():
        vertex_twist_bone_dot = Vector(Vector(vertex.co) - twist_bone_head).dot(fixed_axis.xzy)
        delta = ((vertex_twist_bone_dot - twist_parent_bone_dot) / (twist_child_bone_dot - twist_parent_bone_dot)) * 4.0
        weight = (int(100.0 * delta) % 100) / 100.0
        for group in vertex.groups:
            obj.vertex_groups[group.group].remove([vertex.index])
        if int(delta) == 0:
            obj.vertex_groups[part_twists[0]].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[twist_parent_name_b].add([vertex.index], 1.0 - weight, 'ADD')
        elif int(delta) == 1:
            obj.vertex_groups[part_twists[1]].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[part_twists[0]].add([vertex.index], 1.0 - weight, 'ADD')
        elif int(delta) == 2:
            obj.vertex_groups[part_twists[2]].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[part_twists[1]].add([vertex.index], 1.0 - weight, 'ADD')
        elif int(delta) == 3:
            obj.vertex_groups[twist_name_b].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[part_twists[2]].add([vertex.index], 1.0 - weight, 'ADD')
        elif int(delta) == 4:
            obj.vertex_groups[twist_child_name_b].add([vertex.index], weight, 'ADD')
            obj.vertex_groups[twist_name_b].add([vertex.index], 1.0 - weight, 'ADD')
        else:
            pass
    if base_props.enable_gen_frame_checked:
        add_item_after(armature, twist_name_b, twist_parent_name_b)
    return SsbResult(status=SsbStatus.SUCCESS, result=[twist_name_j] + part_twist_name_j_list)


def create_waist_bone(armature, props, results):
    base_props = props.base
    if not base_props.waist_checked:
        return

    # 基本名称信息
    scale = props.scale
    waist_name_j = "腰"
    waist_name_e = "Waist Bone"
    waist_name_b = convertNameToLR(waist_name_j)
    under_body_name_j = "下半身"
    right_leg_name_j = "右足"
    left_leg_name_j = "左足"

    # 先决条件校验
    if waist_name_j in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[waist_name_j]))
        return
    required_bones = [under_body_name_j, right_leg_name_j, left_leg_name_j]  # PE中没有对左足进行校验，直接抛异常且创建失败
    under_body_parent = armature.pose.bones.get(jp_bl_map[under_body_name_j]).parent
    if any(name not in jp_bl_map for name in required_bones) or under_body_parent is None:
        not_found_list = [waist_name_j]
        for bone_name in required_bones:
            if bone_name not in jp_bl_map:
                not_found_list.append(bone_name)
        results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
        if under_body_parent is None:
            result = SsbResult(status=SsbStatus.FAILED,
                               message=f"{waist_name_j}骨骼所需的{under_body_name_j}的亲骨骼不存在")
            results.append(result)
        return

    # 创建腰骨骼
    create_bone_with_mmd_info(armature, waist_name_b, waist_name_j, waist_name_e)
    set_visible(armature, waist_name_b, True)
    set_movable(armature, waist_name_b, False)
    set_rotatable(armature, waist_name_b, True)
    set_controllable(armature, waist_name_b, True)
    # 设置腰骨骼父级 head tail
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    waist_bone = edit_bones.get(waist_name_b)
    under_body_bone = edit_bones.get(jp_bl_map[under_body_name_j])
    right_leg_bone = edit_bones.get(jp_bl_map[right_leg_name_j])
    waist_bone.parent = under_body_bone.parent
    waist_bone_parent_name_b = waist_bone.parent.name
    waist_bone.head = Vector(
        (0, under_body_bone.head.z * 0.02, under_body_bone.head.z * 0.4 + right_leg_bone.head.z * 0.6))
    waist_bone.tail = waist_bone.head + Vector((under_body_bone.head - waist_bone.head) * 0.8)
    # 设置腰骨骼的变形阶层为下半身亲骨的变形阶层
    under_body_parent_pose_bone = armature.pose.bones.get(jp_bl_map[under_body_name_j]).parent
    armature.pose.bones.get(
        waist_name_b).mmd_bone.transform_order = under_body_parent_pose_bone.mmd_bone.transform_order
    # 如果骨骼的父级是下半身的parent且名称不是センター先，则将其亲骨改为腰骨
    center_saki = "センター先"
    for edit_bone in edit_bones:
        if edit_bone.parent == under_body_bone.parent and edit_bone.name != center_saki:
            edit_bone.parent = waist_bone
    # 设置显示枠
    if base_props.enable_gen_frame_checked:
        flag = add_item_after(armature, waist_name_b, under_body_parent_pose_bone.name)
        if not flag:
            pmx_root = find_pmx_root_with_child(armature)
            frame = create_center_frame(pmx_root)
            do_add_item(frame, 'BONE', waist_name_b)
    waist_c_infos = [
        ("腰キャンセル右", "右足"),
        ("腰キャンセル左", "左足"),
    ]
    waist_c_name_j_list = []
    for info in waist_c_infos:
        waist_c_name_j = info[0]
        waist_c_name_j_list.append(waist_c_name_j)
        waist_c_name_b = convertNameToLR(waist_c_name_j)
        foot_name_j = info[1]
        foot_name_b = convertNameToLR(foot_name_j)
        if waist_c_name_j in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[waist_c_name_j]))
            continue
        # 创建腰取消骨骼
        create_bone_with_mmd_info(armature, waist_c_name_b, waist_c_name_j, '')
        # 暂时设置可见
        set_visible(armature, waist_c_name_b, True)
        set_movable(armature, waist_c_name_b, False)
        set_rotatable(armature, waist_c_name_b, True)
        set_controllable(armature, waist_c_name_b, True)
        # 设置腰骨骼父级 head tail
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = armature.data.edit_bones
        waist_c_bone = edit_bones.get(waist_c_name_b)
        foot_bone = edit_bones.get(foot_name_b)
        waist_c_bone.head = foot_bone.head
        waist_c_bone.tail = waist_c_bone.head + Vector((0, 0, 1)) * scale
        waist_c_bone.parent = foot_bone.parent
        foot_bone.parent = waist_c_bone
        # 设置赋予相关属性，然后重新装配骨骼（这部分属性一旦修改就dirty了，利用设置的tag调用mmd插件的骨骼装配）
        if armature.mode != 'POSE':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='POSE')
        pose_bones = armature.pose.bones
        # 设置赋予相关信息
        mmd_bone = pose_bones[waist_c_name_b].mmd_bone
        mmd_bone.has_additional_rotation = True
        mmd_bone.additional_transform_influence = -1
        mmd_bone.additional_transform_bone = waist_name_b
        # 设置尖端骨骼
        pose_bones[waist_c_name_b].mmd_bone.is_tip = True
        pose_bones[waist_c_name_b].mmd_bone.is_tip = True
        # 装配骨骼
        pose_bones[waist_c_name_b].bone.select = True
        bpy.ops.mmd_tools.apply_additional_transform()
        pose_bones[waist_c_name_b].bone.select = False
        # 恢腰c骨可见性为False
        set_visible(armature, waist_c_name_b, False)
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[waist_name_j] + waist_c_name_j_list))


def remove_bone(armature, objs, bone_name):
    bone = armature.data.edit_bones.get(bone_name)
    parent_bone = bone.parent
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
        if parent_bone:
            parent_vg = obj.vertex_groups.get(parent_bone.name)
        if not vg:
            continue
        for vert in obj.data.vertices:
            for group in vert.groups:
                if group.group == vg.index:
                    if parent_vg is not None:
                        obj.vertex_groups[parent_vg.name].add([vert.index], group.weight, 'ADD')
                    obj.vertex_groups[vg].add([vert.index], 0, 'REPLACE')

    # 移除骨骼
    edit_bone = armature.data.edit_bones.get(bone_name)
    armature.data.edit_bones.remove(edit_bone)


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
        ik_p_name_j = info[0]
        ik_p_name_e = info[1]
        ik_p_name_b = convertNameToLR(info[0])
        ik_name_j = info[2]

        # 先决条件校验
        if ik_p_name_j in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[ik_p_name_j]))
            continue
        if ik_name_j not in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.FAILED, result=[ik_p_name_j, ik_name_j]))
            continue

        # 基本名称信息（blender）
        ik_name_b = jp_bl_map[ik_name_j]

        create_bone_with_mmd_info(armature, ik_p_name_b, ik_p_name_j, ik_p_name_e)
        set_visible(armature, ik_p_name_b, True)
        set_movable(armature, ik_p_name_b, True)
        set_rotatable(armature, ik_p_name_b, True)
        set_controllable(armature, ik_p_name_b, True)
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = armature.data.edit_bones
        ik_p_bone = edit_bones.get(ik_p_name_b)
        ik_bone = edit_bones.get(ik_name_b)
        # 设置ik亲骨 head tail
        ik_p_bone.head = ik_bone.head * Vector((1, 1, 0))
        ik_p_bone.tail = ik_bone.head
        # 设置父级
        ik_p_bone.parent = ik_bone.parent
        ik_bone.parent = ik_p_bone
        # 设置显示枠
        if base_props.enable_gen_frame_checked:
            add_item_before(armature, ik_p_name_b, ik_name_b)
        results.append(SsbResult(status=SsbStatus.SUCCESS, result=[ik_p_name_j]))


def create_shoulder_p_bone(armature, props, results):
    base_props = props.base
    if not base_props.shoulder_p_checked:
        return

    scale = props.scale
    shoulder_infos = [
        ("左肩P", "左肩C", "shoulderP_L", "左肩", "左腕"),
        ("右肩P", "右肩C", "shoulderP_R", "右肩", "右腕")
    ]
    for shoulder_info in shoulder_infos:
        # 基本名称信息
        shoulder_p_name_j = shoulder_info[0]
        shoulder_c_name_j = shoulder_info[1]
        shoulder_p_name_e = shoulder_info[2]
        shoulder_p_name_b = convertNameToLR(shoulder_info[0])
        shoulder_c_name_b = convertNameToLR(shoulder_info[1])
        shoulder_name_j = shoulder_info[3]
        arm_name_j = shoulder_info[4]

        # 先决条件校验
        if shoulder_p_name_j in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[shoulder_p_name_j]))
            continue
        required_bones = [shoulder_name_j, arm_name_j]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = [shoulder_p_name_j]
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
            continue

        # 基本名称信息（blender）
        shoulder_name_b = jp_bl_map[shoulder_name_j]
        arm_name_b = jp_bl_map[arm_name_j]

        # 创建肩P骨
        create_bone_with_mmd_info(armature, shoulder_p_name_b, shoulder_p_name_j, shoulder_p_name_e)
        set_visible(armature, shoulder_p_name_b, True)
        set_movable(armature, shoulder_p_name_b, False)
        set_rotatable(armature, shoulder_p_name_b, True)
        set_controllable(armature, shoulder_p_name_b, True)
        # 创建肩c骨
        create_bone_with_mmd_info(armature, shoulder_c_name_b, shoulder_c_name_j, '')
        # 肩c骨可见性暂时设置为True
        set_visible(armature, shoulder_c_name_b, True)
        set_movable(armature, shoulder_c_name_b, False)
        set_rotatable(armature, shoulder_c_name_b, True)
        set_controllable(armature, shoulder_c_name_b, True)
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = armature.data.edit_bones
        shoulder_p_bone = edit_bones.get(shoulder_p_name_b)
        shoulder_c_bone = edit_bones.get(shoulder_c_name_b)
        shoulder_bone = edit_bones.get(shoulder_name_b)
        arm_bone = edit_bones.get(arm_name_b)
        # 设置肩P骨head tail parent 旋转轴
        shoulder_p_bone.head = shoulder_bone.head
        shoulder_p_bone.tail = shoulder_p_bone.head + Vector((0, 0, 1)) * scale
        shoulder_p_bone.parent = shoulder_bone.parent
        FnBone.update_auto_bone_roll(shoulder_p_bone)
        # 设置肩C骨head tail parent
        shoulder_c_bone.head = arm_bone.head
        shoulder_c_bone.tail = shoulder_c_bone.head + Vector((0, 0, 1)) * scale
        shoulder_c_bone.parent = shoulder_bone
        # 设置肩 腕 parent
        shoulder_bone.parent = shoulder_p_bone
        arm_bone.parent = shoulder_c_bone
        # 设置赋予相关属性，然后重新装配骨骼（这部分属性一旦修改就dirty了，利用设置的tag调用mmd插件的骨骼装配）
        if armature.mode != 'POSE':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='POSE')
        pose_bones = armature.pose.bones
        # 设置赋予相关信息
        mmd_bone = pose_bones[shoulder_c_name_b].mmd_bone
        mmd_bone.has_additional_rotation = True
        mmd_bone.additional_transform_influence = -1
        mmd_bone.additional_transform_bone = shoulder_p_name_b
        # 设置尖端骨骼
        pose_bones[shoulder_p_name_b].mmd_bone.is_tip = True
        pose_bones[shoulder_c_name_b].mmd_bone.is_tip = True
        # 装配骨骼
        pose_bones[shoulder_c_name_b].bone.select = True
        bpy.ops.mmd_tools.apply_additional_transform()
        pose_bones[shoulder_c_name_b].bone.select = False
        # 恢复肩c骨可见性为False
        set_visible(armature, shoulder_c_name_b, False)
        # 设置显示枠
        if base_props.enable_gen_frame_checked:
            add_item_before(armature, shoulder_p_name_b, shoulder_name_b)
        results.append(SsbResult(status=SsbStatus.SUCCESS, result=[shoulder_p_name_j, shoulder_c_name_j]))


def create_bone_with_mmd_info(armature, shoulder_p_name_b, shoulder_p_name_j, shoulder_p_name_e):
    create_bone(armature, shoulder_p_name_b)
    jp_bl_map[shoulder_p_name_j] = shoulder_p_name_b
    bl_jp_map[shoulder_p_name_b] = shoulder_p_name_j
    # 设置MMD骨骼名称
    bpy.ops.object.mode_set(mode='POSE')
    mmd_bone = armature.pose.bones.get(shoulder_p_name_b).mmd_bone
    mmd_bone.name_j = shoulder_p_name_j
    mmd_bone.name_e = shoulder_p_name_e
    bpy.ops.object.mode_set(mode='EDIT')



def create_upper_body2_bone(armature, props, results):
    base_props = props.base
    if not base_props.upper_body2_checked:
        return

    # 基本名称信息
    name_j = "上半身2"
    name_e = "upper body2"
    name_b = convertNameToLR(name_j)
    spine = "上半身"
    neck = "首"

    # 先决条件校验
    if name_j in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[name_j]))
        return
    required_bones = [spine, neck]
    if any(name not in jp_bl_map for name in required_bones):
        not_found_list = [name_j]
        for bone_name in required_bones:
            if bone_name not in jp_bl_map:
                not_found_list.append(bone_name)
        results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
        return

    # 创建上半身2
    create_bone(armature, name_b)
    jp_bl_map[name_j] = name_b
    bl_jp_map[name_b] = name_j
    # 设置MMD骨骼名称
    mmd_bone = armature.pose.bones.get(name_b).mmd_bone
    mmd_bone.name_j = name_j
    mmd_bone.name_e = name_e
    # 设置是否可见
    set_visible(armature, name_b, True)
    # 设置是否可移动
    set_movable(armature, name_b, False)
    # 设置是否可旋转
    set_rotatable(armature, name_b, True)
    # 设置是否可操作
    set_controllable(armature, name_b, True)
    # 设置上半身2的head
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    spine_bone = armature.data.edit_bones.get(jp_bl_map[spine])
    neck_bone = armature.data.edit_bones.get(jp_bl_map[neck])
    neck_bone_head = neck_bone.head.copy()
    upper_body2_bone = armature.data.edit_bones.get(name_b)
    upper_body2_bone.head = spine_bone.head * 0.65 + neck_bone.head * 0.35
    upper_body2_bone_head = upper_body2_bone.head.copy()
    # 设置上半身2的tail
    upper_body2_bone.tail = upper_body2_bone.head + (neck_bone.head - upper_body2_bone.head) * 0.8
    # 设置父级
    upper_body2_bone.parent = spine_bone
    # 设置变形阶层
    armature.pose.bones.get(name_b).mmd_bone.transform_order = armature.pose.bones.get(spine).mmd_bone.transform_order
    # 设置指向
    # mmd插件在导入时，用的是edit bone进行的比较
    # 当一个骨骼的target指向的是一个骨骼引用时，这个骨骼要被设置为use_connect需要：
    # 这两个骨骼是亲子关系 and 子骨骼不可移动 and 亲骨骼可移动 and 亲子距离<1e-4。
    # mmd插件在导出时，用的是pose_bone.bone https://docs.blender.org/api/current/bpy.types.Bone.html#bpy.types.Bone
    # 当一个亲骨骼的末端指向另一个子骨骼时，这个亲骨骼要设置target需要：
    # 子骨骼use_connect为True or 子骨骼拥有mmd_bone_use_connect属性 or (子骨骼不可移动 and math.isclose(0.0, (child.head - bone.tail).length))
    # bone.tail代表的意思是，亲骨骼的末端距离亲骨骼的亲骨骼的距离
    spine_bone.tail = upper_body2_bone.head
    edit_bones = armature.data.edit_bones
    # 如果骨骼的父级指向上半身，则改为上半身2
    for edit_bone in edit_bones:
        parent_bone = edit_bone.parent
        if parent_bone and parent_bone.name == spine:
            edit_bone.parent = edit_bones[name_b]
    # 对每个物体均进行处理
    objs = find_pmx_objects(armature)
    for obj in objs:
        upper_body2_vg_index = -1
        upper_body_vg_index = -1
        neck_vg_index = -1
        for vertex_group in obj.vertex_groups:
            if vertex_group.name == name_b:
                upper_body2_vg_index = vertex_group.index
            if vertex_group.name == jp_bl_map[spine]:
                upper_body_vg_index = vertex_group.index
            if vertex_group.name == jp_bl_map[neck]:
                neck_vg_index = vertex_group.index

        spine_vertices = []
        # 遍历顶点
        for vertex in obj.data.vertices:
            if is_vertex_dedicated_by_bone(obj, vertex, spine, threshold=0.97):
                spine_vertices.append(vertex)
            elif vertex.co.z > upper_body2_bone_head.z:
                # 将不完全归上半身（含阈值）所有的顶点所对应的权重，转移到上半身2上面
                for group in vertex.groups:
                    if obj.vertex_groups[group.group].name == spine:
                        name_b_group_index = obj.vertex_groups.find(name_b)
                        if name_b_group_index != -1:
                            obj.vertex_groups[name_b_group_index].add([vertex.index], group.weight, 'ADD')
                        # 移除操作放到最后
                        obj.vertex_groups[group.group].remove([vertex.index])
                        break
        # 将完全归上半身（含阈值）的顶点所对应的权重，转移到上半身2上面
        for spine_vertex in spine_vertices:
            # todo NANOEM_MODEL_VERTEX_TYPE_BDEF2 指代的是顶点被两个骨骼控制且权重合计为1吧？ 后续再验证下
            for group in spine_vertex.groups:
                obj.vertex_groups[group.group].remove([spine_vertex.index])

            # 获取上半身顶点和上半身2的head的距离
            distance = spine_vertex.co - upper_body2_bone_head
            if distance.y > 0:
                distance.z += distance.y * 0.5
            # distance在上半身和首之间的比例
            per = distance.z / (neck_bone_head.z - upper_body2_bone_head.z)
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
            if rigid_body.mmd_rigid.bone == spine:
                rigid_body.mmd_rigid.bone = name_b
    # 设置显示枠
    if base_props.enable_gen_frame_checked:
        add_item_after(armature, name_b, jp_bl_map[spine])
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[name_j]))


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
    return (summation / total) > threshold


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
    name_j = '全ての親'
    name_e = 'root'
    name_b = convertNameToLR(name_j)

    # 先决条件校验
    if name_j in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[name_j]))
        return

    # 创建全亲骨
    create_bone(armature, name_b)
    jp_bl_map[name_j] = name_b
    bl_jp_map[name_b] = name_j
    # 设置MMD骨骼名称
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
    first_bone = get_first_bone(armature, name_b, objs)
    set_tail(armature, name_b, first_bone.name)
    # 设置亲骨骼及末端指向
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    for edit_bone in edit_bones:
        parent_bone = edit_bone.parent
        target_bone = get_target_bone(armature, edit_bone)
        if not parent_bone:
            edit_bone.parent = edit_bones[name_b]
        elif target_bone and target_bone == first_bone:
            # 如果骨骼的末端指向first_bone，则将其改为末端指向root_bone
            set_target_bone(edit_bone, edit_bones[name_b])
    # 设置显示枠
    if base_props.enable_gen_frame_checked:
        set_root_frame(armature, name_b, first_bone)
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[name_j]))


def create_dummy_bone(armature, props, results):
    base_props = props.base
    if not base_props.dummy_checked:
        return

    dummy_l = ("左ダミー", "dummy_L", "左手首", "左中指１")
    dummy_r = ("右ダミー", "dummy_R", "右手首", "右中指１")
    dummy_infos = [dummy_l, dummy_r]
    scale = props.scale
    for i, info in enumerate(dummy_infos):
        # 基本名称信息
        name_j = info[0]
        name_e = info[1]
        name_b = convertNameToLR(name_j)
        wrist_bone_name = info[2]
        middle_finger_bone_name = info[3]

        # 先决条件校验
        if name_j in jp_bl_map.keys():
            results.append(SsbResult(status=SsbStatus.SKIPPED, result=[name_j]))
            continue
        required_bones = [wrist_bone_name, middle_finger_bone_name]
        if any(name not in jp_bl_map for name in required_bones):
            not_found_list = [name_j]
            for bone_name in required_bones:
                if bone_name not in jp_bl_map:
                    not_found_list.append(bone_name)
            results.append(SsbResult(status=SsbStatus.FAILED, result=not_found_list))
            continue

        # 创建手持骨
        create_bone(armature, name_b)
        jp_bl_map[name_j] = name_b
        bl_jp_map[name_b] = name_j
        # 设置MMD骨骼名称
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
        if armature.mode != 'EDIT':
            select_and_activate(armature)
            bpy.ops.object.mode_set(mode='EDIT')
        # 计算基础数据
        wrist_bone = armature.data.edit_bones.get(jp_bl_map[wrist_bone_name])
        middle_finger_bone = armature.data.edit_bones.get(jp_bl_map[middle_finger_bone_name])
        wrist_head_vec = Vector(wrist_bone.head)
        middle_finger_bone_head_vec = Vector(
            (middle_finger_bone.head[0], wrist_bone.head[1], middle_finger_bone.head[2]))
        center_vec = (wrist_head_vec + middle_finger_bone_head_vec) * 0.5
        normalized_vec = Vector((middle_finger_bone_head_vec - wrist_head_vec) / scale).normalized() * scale
        if i == 0:
            result = Vector((normalized_vec.z, 0, -normalized_vec.x))
        else:
            result = Vector((-normalized_vec.z, 0, normalized_vec.x))
        # 设置dummy骨骼head
        dummy_bone = armature.data.edit_bones.get(name_b)
        head = center_vec + Vector((result.x * 0.25, 0, result.z * 0.25))
        dummy_bone.head = head
        dummy_bone.tail = head + Vector((result.x * 1.2, 0, result.z * 1.2))
        # 设置父级
        dummy_bone.parent = wrist_bone
        # 设置旋转轴
        FnBone.update_auto_bone_roll(dummy_bone)
        # 设置显示枠
        if base_props.enable_gen_frame_checked:
            add_item_after(armature, name_b, jp_bl_map[wrist_bone_name])
        results.append(SsbResult(status=SsbStatus.SUCCESS, result=[name_j]))


def create_groove_bone(armature, props, results):
    base_props = props.base
    if not base_props.groove_checked:
        return

    # 基本名称信息
    name_j = 'グルーブ'
    name_e = 'groove'
    name_b = convertNameToLR(name_j)

    # 先决条件校验
    if name_j in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[name_j]))
        return
    if 'センター' not in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.FAILED, result=[name_j, 'センター']))
        return

    # 创建グルーブ骨骼
    create_bone(armature, name_b)
    jp_bl_map[name_j] = name_b
    bl_jp_map[name_b] = name_j
    # 设置MMD骨骼名称
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
    # 设置グルーブ骨骼head位置
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    canter_bone = armature.data.edit_bones.get("センター", None)
    scale = props.scale
    groove_edit_bone = armature.data.edit_bones.get(name_b)
    groove_edit_bone.head = canter_bone.head + get_loc_by_xzy((0, 0.2, 0), scale)
    # 设置グルーブ骨骼父级
    groove_edit_bone.parent = canter_bone
    # 设置グルーブ骨骼tail位置
    groove_edit_bone.tail = groove_edit_bone.head + get_loc_by_xzy((0, 1.4, 0), scale)
    # 修改指向
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    canter_bone = armature.data.edit_bones.get("センター", None)
    edit_bones = armature.data.edit_bones
    center_saki = "センター先"
    # todo 模式的更换貌似会使edit_bone失效，然后就闪退了....之后应该调整顺序避免频繁修改上下文
    groove_edit_bone = armature.data.edit_bones.get(name_b)
    for edit_bone in edit_bones:
        if edit_bone.parent == canter_bone and edit_bone.name != center_saki:
            edit_bone.parent = groove_edit_bone
    # 设置显示枠
    if base_props.enable_gen_frame_checked:
        set_groove_frame(armature, name_b)
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[name_j]))


def get_loc_by_xzy(loc, scale):
    """获取pmx模型在blender中的位置"""
    vector = Vector(loc).xzy if all(math.isfinite(n) for n in loc) else Vector((0, 0, 0))
    return vector * scale


def set_groove_frame(armature, groove_name):
    pmx_root = find_pmx_root_with_child(armature)
    mmd_root = pmx_root.mmd_root
    found_frame, found_item = find_bone_item(pmx_root, groove_name)
    if found_frame and found_item:
        frames = mmd_root.display_item_frames
        do_add_item(frames[found_frame], 'BONE', groove_name, order=found_item + 1)
    else:
        frame = create_center_frame(pmx_root)
        do_add_item(frame, 'BONE', groove_name, order=0)


def create_view_center_bone(armature, props, results):
    base_props = props.base
    if not base_props.view_center_checked:
        return
    scale = props.scale

    # 基本名称信息
    name_j = '操作中心'
    name_e = 'view cnt'
    name_b = convertNameToLR(name_j)

    # 先决条件校验
    if name_j in jp_bl_map.keys():
        results.append(SsbResult(status=SsbStatus.SKIPPED, result=[name_j]))
        return

    # 创建操作中心骨骼
    create_bone(armature, name_b)
    jp_bl_map[name_j] = name_b
    bl_jp_map[name_b] = name_j
    # 设置MMD骨骼名称
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
    objs = find_pmx_objects(armature)
    first_bone = get_first_bone(armature, name_b, objs)
    if armature.mode != 'EDIT':
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    for edit_bone in edit_bones:
        target_bone = get_target_bone(armature, edit_bone)
        if target_bone == first_bone:
            # 如果骨骼的末端指向first_bone，则将其改为末端指向view_center_bone
            set_target_bone(edit_bone, edit_bones[name_b])
    # 设置操作中心 tail
    edit_bones[name_b].tail = edit_bones[name_b].tail * scale
    # 设置显示枠（流程同全亲骨）
    if base_props.enable_gen_frame_checked:
        set_root_frame(armature, name_b, first_bone)
    results.append(SsbResult(status=SsbStatus.SUCCESS, result=[name_j]))


def get_first_bone(armature, name, objs):
    """获取（排除自身后）排在首位的顶点组对应的骨骼"""
    first_vg = ''
    for obj in objs:
        for vg in obj.vertex_groups:
            if vg and vg.name and name != vg.name and armature.pose.bones.get(vg.name, None):
                first_vg = vg.name
                break
        if first_vg:
            break
    first_bone = armature.pose.bones.get(first_vg)
    return first_bone


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
        name_j = pose_bone.mmd_bone.name_j
        name_b = pose_bone.name
        jp_bl_map[name_j] = name_b
        bl_jp_map[name_b] = name_j


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


def set_root_frame(armature, root_bone_name, first_bone):
    pmx_root = find_pmx_root_with_child(armature)
    found_frame, found_item = find_bone_item(pmx_root, first_bone.name)
    if first_bone and not found_frame and not found_item:
        # 创建センター显示枠
        frame = create_center_frame(pmx_root)
        # 创建first_bone元素并将其移动到第0位
        do_add_item(frame, 'BONE', first_bone.name, order=0)
    mmd_root = pmx_root.mmd_root
    frames = mmd_root.display_item_frames
    if frames:
        # 获取首位显示枠（root）
        first_frame = frames[0]
        # 移除root里面的元素
        first_frame.data.clear()
        first_frame.active_item = 0
        # 创建root_bone元素并将其移动到第0位
        do_add_item(first_frame, 'BONE',root_bone_name, order=0)


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
