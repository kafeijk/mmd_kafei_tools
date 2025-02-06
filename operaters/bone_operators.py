from mathutils import Quaternion, Euler

from ..utils import *


class FlipBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.flip_bone"
    bl_label = "翻转姿态"
    bl_description = "翻转姿态"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "FLIP_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        mirror_pose()
        return {'FINISHED'}


class DeleteInvalidRigidbodyJointOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.delete_invalid_rigidbody_joint"
    bl_label = "清理无效刚体Joint"
    bl_description = "清理无效的刚体和关节。如果刚体所关联的骨骼不存在，则删除该刚体及与之关联的关节；如果刚体没有关联的骨骼，则不处理"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "INVALID_RIGIDBODY_JOINT"
        if check_props(self, option) is False:
            return {'FINISHED'}
        remove_invalid_rigidbody_joint()
        return {'FINISHED'}


class SelectPhysicalBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_physical_bone"
    bl_label = "物理骨骼"
    bl_description = "选择受物理影响的MMD骨骼"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "PHYSICAL_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_physical_bone()
        return {'FINISHED'}


class SelectBakeBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_bake_bone"
    bl_label = "K帧骨骼"
    bl_description = "选择用于K帧的MMD骨骼"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "BAKE_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bake_bone()
        return {'FINISHED'}


class SelectLinkedBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_linked_bone"
    bl_label = "关联骨骼"
    bl_description = "选择以父/子关系关联到当前选中项的所有骨骼"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "LINKED_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bone_by_input(option)
        return {'FINISHED'}


class SelectRingBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_ring_bone"
    bl_label = "并排骨骼"
    bl_description = "选择当前选中项的环绕骨骼，例如选择裙子骨骼的一周"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "RING_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bone_by_input(option)
        return {'FINISHED'}


class SelecExtendParentBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_extend_parent_bone"
    bl_label = "父 +"
    bl_description = "拓展选择当前选中项的父骨骼"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "EXTEND_PARENT_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bone_by_input(option)
        return {'FINISHED'}


class SelectExtendChildrenBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_extend_children_bone"
    bl_label = "子 +"
    bl_description = "拓展选择当前选中项的子骨骼"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "EXTEND_CHILDREN_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bone_by_input(option)
        return {'FINISHED'}


class SelectLessParentBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_less_parent_bone"
    bl_label = "父 -"
    bl_description = "从当前选中项的父级开始缩减选择"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "LESS_PARENT_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bone_by_input(option)
        return {'FINISHED'}


class SelectLessChildrenBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_less_children_bone"
    bl_label = "子 -"
    bl_description = "从当前选中项的子级开始缩减选择"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "LESS_CHILDREN_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bone_by_input(option)
        return {'FINISHED'}


class SelectMoreBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_more_bone"
    bl_label = "拓展选区"
    bl_description = "拓展选择当前选中项的父子骨骼"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "MORE_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bone_by_input(option)
        return {'FINISHED'}


class SelectLessBoneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.select_less_bone"
    bl_label = "缩减选区"
    bl_description = "缩减选择当前选中项的父子骨骼"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        option = "LESS_BONE"
        if check_props(self, option) is False:
            return {'FINISHED'}
        select_bone_by_input(option)
        return {'FINISHED'}


def check_props(operator, option):
    if option in ("FLIP_BONE", "PHYSICAL_BONE", "BAKE_BONE", "LINKED_BONE", "RING_BONE", "INVALID_RIGIDBODY_JOINT",
                  "MORE_BONE", "EXTEND_CHILDREN_BONE", "EXTEND_PARENT_BONE",
                  "LESS_BONE", "LESS_PARENT_BONE", "LESS_CHILDREN_BONE"):
        active_object = bpy.context.active_object
        if not active_object:
            operator.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        pmx_root = find_pmx_root_with_child(active_object)
        if not pmx_root:
            operator.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        armature = find_pmx_armature(pmx_root)
        if not armature:
            operator.report(type={'ERROR'}, message=f'模型缺少骨架！')
            return False

        if option in ("FLIP_BONE"):
            selected_pbs = []
            pbs = armature.pose.bones
            for pb in pbs:
                if pb.bone.select:
                    selected_pbs.append(pb)
            if not selected_pbs:
                operator.report(type={'ERROR'}, message=f'请至少选择一根骨骼！')
                return False

            lr = ""
            for pb in selected_pbs:
                # 去除.xxx后缀
                basename = re.sub(r'\.\d+$', '', pb.name)
                # 去除LR
                if basename.endswith(('.L', '.R', '.l', '.r', '_L', '_R', '_l', '_r')):
                    curr_lr = basename[-1].lower()
                    if not lr:
                        lr = curr_lr
                    else:
                        if curr_lr != lr:
                            operator.report(type={'ERROR'}, message=f'请选择单侧骨骼！')
                            return False
        return True


def is_valid_bone(bone_info, pb):
    eb_hide_map = bone_info[0]
    original_mode = bone_info[1]
    armature_layers = bone_info[2]
    if not pb:
        return False
    # 骨骼被隐藏
    bone = pb.bone
    if original_mode == 'POSE':
        if bone.hide:
            return False
    if original_mode == 'EDIT':
        hide_flag = eb_hide_map.get(pb.name)
        if hide_flag:
            return False

    # 骨骼不在显示层
    if bpy.app.version < (4, 0, 0):
        layers = bone.layers
        active_layers = [i for i, layer in enumerate(layers) if layer]
        if all(not armature_layers[i] for i in active_layers):
            return False
    else:
        visible = False
        for armature_layer in armature_layers:
            for b in armature_layer.bones:
                if b.name == pb.name:
                    visible = True
                    break
            if visible:
                break
        if not visible:
            return False
    return True


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
    # 如果子骨骼只有一个子骨骼，将其添加到列表
    child = pb.children[0]
    if is_valid_bone(bone_info, pb) and len(child.children) == 1:
        pb_set.add(child)
        if once:
            return
        traverse_children(bone_info, child, pb_set, once)  # 继续递归子骨骼
    else:
        pb_set.add(child)
        return


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


matmul = (lambda a, b: a * b) if bpy.app.version < (2, 80, 0) else (lambda a, b: a.__matmul__(b))


class BoneConverter:
    def __init__(self, pose_bone, scale, invert=False):
        mat = pose_bone.bone.matrix_local.to_3x3()
        mat[1], mat[2] = mat[2].copy(), mat[1].copy()
        self.__mat = mat.transposed()
        self.__scale = scale
        if invert:
            self.__mat.invert()
        self.convert_interpolation = _InterpolationHelper(self.__mat).convert

    def convert_location(self, location):
        return matmul(self.__mat, Vector(location)) * self.__scale

    def convert_rotation(self, rotation_xyzw):
        rot = Quaternion()
        rot.x, rot.y, rot.z, rot.w = rotation_xyzw
        return Quaternion(matmul(self.__mat, rot.axis) * -1, rot.angle).normalized()


class _InterpolationHelper:
    def __init__(self, mat):
        self.__indices = indices = [0, 1, 2]
        l = sorted((-abs(mat[i][j]), i, j) for i in range(3) for j in range(3))
        _, i, j = l[0]
        if i != j:
            indices[i], indices[j] = indices[j], indices[i]
        _, i, j = next(k for k in l if k[1] != i and k[2] != j)
        if indices[i] != j:
            idx = indices.index(j)
            indices[i], indices[idx] = indices[idx], indices[i]

    def convert(self, interpolation_xyz):
        return (interpolation_xyz[i] for i in self.__indices)


def xyzw_from_rotation_mode(mode):
    # 如果旋转模式是四元数，直接返回
    if mode == 'QUATERNION':
        return lambda xyzw: xyzw

    # 如果旋转模式是坐标轴角度，将其转为四元数
    if mode == 'AXIS_ANGLE':
        def __xyzw_from_axis_angle(xyzw):
            q = Quaternion(xyzw[:3], xyzw[3])
            return [q.x, q.y, q.z, q.w]

        return __xyzw_from_axis_angle

    # 如果旋转模式是轴角（绕xyzw[:3]旋转了xyzw[3]度），将其转为四元数
    def __xyzw_from_euler(xyzw):
        q = Euler(xyzw[:3], xyzw[3]).to_quaternion()
        return [q.x, q.y, q.z, q.w]

    return __xyzw_from_euler


class _MirrorMapper:
    def __init__(self, data_map=None):
        self.__data_map = data_map

    @staticmethod
    def get_location(location):
        return (-location[0], location[1], location[2])

    @staticmethod
    def get_rotation(rotation_xyzw):
        return (rotation_xyzw[0], -rotation_xyzw[1], -rotation_xyzw[2], rotation_xyzw[3])

    @staticmethod
    def get_rotation3(rotation_xyz):
        return (rotation_xyz[0], -rotation_xyz[1], -rotation_xyz[2])


def minRotationDiff(prev_q, curr_q):
    t1 = (prev_q.w - curr_q.w) ** 2 + (prev_q.x - curr_q.x) ** 2 + (prev_q.y - curr_q.y) ** 2 + (
            prev_q.z - curr_q.z) ** 2
    t2 = (prev_q.w + curr_q.w) ** 2 + (prev_q.x + curr_q.x) ** 2 + (prev_q.y + curr_q.y) ** 2 + (
            prev_q.z + curr_q.z) ** 2
    # t1 = prev_q.rotation_difference(curr_q).angle
    # t2 = prev_q.rotation_difference(-curr_q).angle
    return -curr_q if t2 < t1 else curr_q


def getBoneConverter(bone):
    converter = BoneConverter(bone, 0.08)
    mode = bone.rotation_mode
    compatible_quaternion = minRotationDiff

    class _ConverterWrap:
        convert_location = converter.convert_location
        convert_interpolation = converter.convert_interpolation
        if mode == 'QUATERNION':
            convert_rotation = converter.convert_rotation
            compatible_rotation = compatible_quaternion
        elif mode == 'AXIS_ANGLE':
            @staticmethod
            def convert_rotation(rot):
                (x, y, z), angle = converter.convert_rotation(rot).to_axis_angle()
                return (angle, x, y, z)

            @staticmethod
            def compatible_rotation(prev, curr):
                angle, x, y, z = curr
                if prev[1] * x + prev[2] * y + prev[3] * z < 0:
                    angle, x, y, z = -angle, -x, -y, -z
                angle_diff = prev[0] - angle
                if abs(angle_diff) > math.pi:
                    pi_2 = math.pi * 2
                    bias = -0.5 if angle_diff < 0 else 0.5
                    angle += int(bias + angle_diff / pi_2) * pi_2
                return (angle, x, y, z)
        else:
            convert_rotation = lambda rot: converter.convert_rotation(rot).to_euler(mode)
            compatible_rotation = lambda prev, curr: curr.make_compatible(prev) or curr

    return _ConverterWrap


def do_mirror_pose(bone_a, bone_b):
    x, y, z = bone_a.location
    rw, rx, ry, rz = bone_a.rotation_quaternion

    converter = BoneConverter(bone_a, 12.5, invert=True)
    # 将blender位置值转为vmd位置值
    location = converter.convert_location([x, y, z])
    # 将blender旋转值转为vmd旋转值
    get_xyzw = xyzw_from_rotation_mode(bone_a.rotation_mode)
    curr_rot = converter.convert_rotation(get_xyzw([rx, ry, rz, rw]))
    rotation_xyzw = curr_rot[1:] + curr_rot[0:1]
    rotation_xyzw = Quaternion(rotation_xyzw)

    _loc, _rot = _MirrorMapper.get_location, _MirrorMapper.get_rotation
    converter = getBoneConverter(bone_b)
    # 将vmd位置值转为blender位置值
    loc = converter.convert_location(_loc(location))
    # 将vmd旋转值转为blender旋转值
    curr_rot = converter.convert_rotation(_rot(rotation_xyzw))
    bone_b.location = loc
    bone_b.rotation_quaternion = curr_rot

    bone_b.scale = bone_a.scale


def get_mirror_name(bl_name):
    # 获取去除数字拓展后的basename
    basename = re.sub(r'\.\d+$', '', bl_name)
    # 提取数字扩展部分（如果有）
    res = re.search(r'(\.\d+)$', bl_name)
    suffix = res.group(0) if res else ''

    mirror_basename = ''
    if basename[-2:] == ".L":
        mirror_basename = basename[:-2] + ".R"
    elif basename[-2:] == ".l":
        mirror_basename = basename[:-2] + ".r"
    elif basename[-2:] == ".R":
        mirror_basename = basename[:-2] + ".L"
    elif basename[-2:] == ".r":
        mirror_basename = basename[:-2] + ".l"

    mirror_bl_name = mirror_basename + suffix
    return mirror_bl_name


def mirror_pose():
    """翻转骨骼姿态，该部分从mmd_tools提取，原理不清楚，但流程相当于导出动作再镜像导入。"""
    obj = bpy.context.active_object
    pmx_root = find_pmx_root_with_child(obj)
    armature = find_pmx_armature(pmx_root)

    pbs = armature.pose.bones
    selected_pbs = []
    for pb in pbs:
        if pb.bone.select:
            selected_pbs.append(pb)

    # 没有骨骼被选择则直接返回
    if not selected_pbs:
        return

    for pb in selected_pbs:
        mirror_pb_name = get_mirror_name(pb.name)
        mirror_bone = pbs.get(mirror_pb_name)
        if mirror_bone:
            do_mirror_pose(pb, mirror_bone)


def remove_invalid_rigidbody_joint():
    """清理无效刚体Joint"""
    original_mode = bpy.context.active_object.mode
    obj = bpy.context.active_object
    root = find_pmx_root_with_child(obj)
    armature = find_pmx_armature(root)
    deselect_all_objects()
    show_object(armature)
    select_and_activate(armature)
    bpy.ops.object.mode_set(mode='POSE')  # 如果不进入POSE模式，armature.pose.bones无法获取到EDIT模式下对骨骼的修改
    rigidbody_parent = find_rigid_body_parent(root)
    joint_parent = find_joint_parent(root)

    # （预先）删除无效关节
    for joint in reversed(joint_parent.children):
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

    for joint in reversed(joint_parent.children):
        rigidbody1 = joint.rigid_body_constraint.object1
        rigidbody2 = joint.rigid_body_constraint.object2
        if not rigidbody1 or not rigidbody2:
            bpy.data.objects.remove(joint, do_unlink=True)

    bpy.ops.object.mode_set(mode=original_mode)


def select_physical_bone():
    """选择物理骨骼"""
    original_mode = bpy.context.active_object.mode
    obj = bpy.context.active_object
    root = find_pmx_root_with_child(obj)
    armature = find_pmx_armature(root)
    bl_names = get_physical_bone(root)
    # 选中骨架并进入姿态模式
    deselect_all_objects()
    show_object(armature)
    select_and_activate(armature)
    bpy.ops.object.mode_set(mode='POSE')
    for bone in armature.pose.bones:
        if bone.name in bl_names:
            bone.bone.select = True
        else:
            bone.bone.select = False

    if original_mode == "EDIT":
        bpy.ops.object.mode_set(mode='EDIT')


def select_bake_bone():
    """选择用于烘焙VMD的骨骼"""
    original_mode = bpy.context.active_object.mode
    obj = bpy.context.active_object
    pmx_root = find_pmx_root_with_child(obj)
    armature = find_pmx_armature(pmx_root)
    # 选中骨架并进入姿态模式
    deselect_all_objects()
    show_object(armature)
    select_and_activate(armature)
    bpy.ops.object.mode_set(mode='POSE')
    for bone in armature.pose.bones:
        if bone.mmd_bone.name_j in PMX_BAKE_BONES:
            bone.bone.select = True
        else:
            bone.bone.select = False

    if original_mode == "EDIT":
        bpy.ops.object.mode_set(mode='EDIT')


def get_end_bones(selected_pbs, pb_set):
    """获取末端子骨，即子骨数量为0或子骨均未被选中"""
    for pb in selected_pbs:
        if len(pb.children) == 0:
            pb_set.add(pb)
        else:
            selected_child_flag = False
            for child in pb.children:
                if child.bone.select:
                    selected_child_flag = True
                    break
            if not selected_child_flag:
                pb_set.add(pb)


def get_bone_info(armature, original_mode):
    """获取骨骼信息：编辑模式下骨骼的隐藏状态 初始模式 骨骼所在层"""
    eb_hide_map = {}
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in armature.data.edit_bones:
        eb_hide_map[eb.name] = eb.hide
    if bpy.app.version < (4, 0, 0):
        return eb_hide_map, original_mode, armature.data.layers
    else:
        bpy.ops.object.mode_set(mode='POSE')    # Warning: `Collection.bones` is not available in armature edit mode
        layers = [c for c in armature.data.collections_all if c.is_visible]
        return eb_hide_map, original_mode, layers


def select_bone_by_input(option):
    """根据用户所选择的骨骼，来选择option相关骨骼

    关联骨骼：
        Blender原逻辑：向上寻找父级，向下寻找子级，遇到非关联项则结束寻找
        现逻辑：向上寻找父级，向下寻找子级，如果父级/子级存在分叉（多个子级）则结束查找
    并排骨骼：
        选择环绕骨骼，有点类似选择并排边，PE插件创建物理骨骼时名称存在“_纵向id_横向id”格式的后缀，以此来判别
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
    original_mode = bpy.context.active_object.mode
    obj = bpy.context.active_object
    pmx_root = find_pmx_root_with_child(obj)
    armature = find_pmx_armature(pmx_root)

    deselect_all_objects()
    show_object(armature)
    select_and_activate(armature)

    # 获取骨骼信息：编辑模式下骨骼的隐藏状态 初始模式 骨骼所在层
    bone_info = get_bone_info(armature, original_mode)

    pbs = armature.pose.bones
    selected_pbs = []
    invalid_bone_set = set()
    for pb in pbs:
        # Blender逻辑中，关联查找不考虑被选中的隐藏骨骼，而查找父级子级时考虑，这里统一考虑
        if pb.bone.select and is_valid_bone(bone_info, pb):
            selected_pbs.append(pb)
        else:
            invalid_bone_set.add(pb)

    # 没有骨骼被选择则直接返回
    if not selected_pbs:
        bpy.ops.object.mode_set(mode=original_mode)
        return

    # 拓展选择时，需维持当前激活骨骼的激活状态，缩减选择时，若激活骨骼为将被缩减选择的骨骼，则无需保持激活状态。
    active_pb = None
    if armature.data.bones.active:
        active_pb = pbs.get(armature.data.bones.active.name)

    # 缩减选择时，查找范围排除无效骨骼
    if option in ["LESS_PARENT_BONE", "LESS_CHILDREN_BONE", "LESS_BONE"]:
        unselect_bone(armature, invalid_bone_set)
    if active_pb and active_pb not in selected_pbs:
        unselect_bone(armature, {active_pb})

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
        get_end_bones(selected_pbs, unselected_set)
    elif option == "LESS_BONE":
        for pb in selected_pbs:
            ancestor = get_deselected_ancestor(bone_info, pb, selected_pbs)
            unselected_set.add(ancestor)
        get_end_bones(selected_pbs, unselected_set)

    # 选择/取消选择
    if option in ["LESS_PARENT_BONE", "LESS_CHILDREN_BONE", "LESS_BONE"]:
        unselect_bone(armature, unselected_set)
    else:
        for pb in selected_set:
            pb.bone.select = True
        if active_pb in selected_pbs:
            active_pb.bone.select = True

    # 返回初始模式
    bpy.ops.object.mode_set(mode=original_mode)


def unselect_bone(armature, pb_set):
    """取消选择骨骼"""
    bpy.ops.object.mode_set(mode="POSE")
    for pb in pb_set:
        pb.bone.select = False
    bpy.ops.object.mode_set(mode="EDIT")
    for pb in pb_set:
        eb = armature.data.edit_bones.get(pb.name)
        eb.select = False
        eb.select_head = False
        eb.select_tail = False
