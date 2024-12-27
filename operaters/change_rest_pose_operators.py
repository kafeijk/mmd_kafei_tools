from ..tools.ApplyModifierForObjectWithShapeKeys import applyModifierForObjectWithShapeKeys
from ..utils import *

bpy.types.Object.original_location = bpy.props.FloatVectorProperty(
    get=lambda obj: obj.get('original_location', None)
)
bpy.types.Object.original_rotation = bpy.props.FloatVectorProperty(
    subtype="EULER",
    get=lambda obj: obj.get('original_rotation', None)
)
bpy.types.Object.original_location_lock = bpy.props.BoolVectorProperty(
    get=lambda obj: obj.get('original_location_lock', None)
)


class ChangeRestPoseStartOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.change_rest_pose_start"
    bl_label = "绑定"
    bl_description = "开始调整初始姿态"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.start(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def start(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_change_rest_pose

        # 校验是否选中MMD模型
        if self.check_props(props) is False:
            return

        # 获取模型信息
        active_object = bpy.context.active_object
        root = find_pmx_root_with_child(active_object)
        armature = find_pmx_armature(root)
        rigidbody_parent = find_rigid_body_parent(root)
        joint_parent = find_joint_parent(root)

        # 对骨架祖先上锁，防止编辑
        modify_root_trans_lock(armature, True)
        # 对骨骼解锁，允许编辑
        modify_pb_trans_lock(armature, False)

        # 开启骨架可见性并进入姿态模式
        show_object(armature)
        deselect_all_objects()
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='POSE')
        # 姿态变换归零
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.loc_clear()
        bpy.ops.pose.rot_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.select_all(action='DESELECT')

        # 设置刚体约束
        set_rigidbody_cons(rigidbody_parent, armature)
        # 设置Joint控制器（约束、驱动）
        self.set_joint_controller(props, joint_parent, rigidbody_parent)

    def set_joint_controller(self, props, joint_parent, rigidbody_parent):
        h_joint_keyword = props.h_joint_keyword
        h_joint_strategy = props.h_joint_strategy

        v_joints = []  # 纵Joints
        h_joints = []  # 横Joints
        for joint in joint_parent.children:
            if h_joint_keyword in joint.name:
                h_joints.append(joint)
            else:
                v_joints.append(joint)

        # 纵Joint约束为刚体A
        for joint in v_joints:
            self.set_joint_cons(joint, rigidbody_parent)

        for joint in h_joints:
            if h_joint_strategy == "RIGIDBODY_A":
                self.set_joint_cons(joint, rigidbody_parent)
            elif h_joint_strategy == "CENTROID":
                self.do_set_joint_driver(joint, rigidbody_parent)
            else:
                pass

    def do_set_joint_driver(self, joint, rigidbody_parent):
        rigidbody1 = joint.rigid_body_constraint.object1
        rigidbody2 = joint.rigid_body_constraint.object2
        if not all(r in rigidbody_parent.children for r in [rigidbody1, rigidbody2]):
            return

        # 记录初始位置
        if "original_location" not in joint:
            joint["original_location"] = joint.location.copy()
        if "original_rotation" not in joint:
            joint["original_rotation"] = joint.rotation_euler.copy()

        # 移除已有驱动
        if joint.animation_data and joint.animation_data.drivers:
            # 移除位置驱动器
            for fcurve in joint.animation_data.drivers:
                if fcurve.data_path.startswith("location") or fcurve.data_path.startswith("rotation_euler"):
                    joint.animation_data.drivers.remove(fcurve)

        # 创建xyz驱动器
        for i, axis in enumerate('xyz'):
            # 添加位置驱动器
            fcurve = joint.driver_add("location", i)
            driver = fcurve.driver
            driver.type = 'SCRIPTED'

            # 添加变量 rigidbody1
            var1 = driver.variables.new()
            var1.name = f"rigidbody1_{axis}"
            var1.type = 'TRANSFORMS'
            var1.targets[0].id = rigidbody1
            var1.targets[0].transform_type = f"LOC_{axis.upper()}"

            # 添加变量 rigidbody2
            var2 = driver.variables.new()
            var2.name = f"rigidbody2_{axis}"
            var2.type = 'TRANSFORMS'
            var2.targets[0].id = rigidbody2
            var2.targets[0].transform_type = f"LOC_{axis.upper()}"

            # 设置驱动器表达式为两个刚体位置的平均值
            driver.expression = f"({var1.name} + {var2.name}) / 2"

        for i, axis in enumerate('xyz'):
            # 添加旋转驱动器
            fcurve = joint.driver_add("rotation_euler", i)
            driver = fcurve.driver
            driver.type = 'SCRIPTED'

            # 添加变量 rigidbody1
            var1 = driver.variables.new()
            var1.name = f"rigidbody1_rot_{axis}"
            var1.type = 'TRANSFORMS'
            var1.targets[0].id = rigidbody1
            var1.targets[0].transform_type = f"ROT_{axis.upper()}"
            var1.targets[0].rotation_mode = "YXZ"

            # 添加变量 rigidbody2
            var2 = driver.variables.new()
            var2.name = f"rigidbody2_rot_{axis}"
            var2.type = 'TRANSFORMS'
            var2.targets[0].id = rigidbody2
            var2.targets[0].transform_type = f"ROT_{axis.upper()}"
            var2.targets[0].rotation_mode = "YXZ"

            # 计算角度平均值，考虑角度修正（如179°和-179°的平均值应该是180°而不是0°）
            driver.expression = (
                f"{var1.name} + (({var2.name}-{var1.name} +pi)%(2*pi)-pi)/2"
            )

    def set_joint_cons(self, joint, rigidbody_parent):
        joint.constraints.clear()
        constraint = joint.constraints.new("CHILD_OF")
        constraint.name = "mmd_kafei_tools_joint_parent"
        rigidbody1 = joint.rigid_body_constraint.object1
        if rigidbody1 in rigidbody_parent.children:
            constraint.target = rigidbody1

    def check_props(self, props):
        active_object = bpy.context.active_object
        if not active_object:
            self.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        pmx_root = find_pmx_root_with_child(active_object)
        if not pmx_root:
            self.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        armature = find_pmx_armature(pmx_root)
        if not armature:
            self.report(type={'ERROR'}, message=f'模型缺少骨架！')
            return False
        return True


class ChangeRestPoseEndOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.change_rest_pose_end"
    bl_label = "应用绑定"
    bl_description = "应用刚体Joint"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.end(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def end(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_sf

        # 校验是否选中MMD模型
        if self.check_props(props) is False:
            return

        # 获取模型信息
        active_object = bpy.context.active_object
        root = find_pmx_root_with_child(active_object)
        armature = find_pmx_armature(root)
        objs = find_pmx_objects(armature)
        rigidbody_parent = find_rigid_body_parent(root)
        joint_parent = find_joint_parent(root)

        # 解锁
        modify_root_trans_lock(armature, False)
        # 恢复骨骼锁定状态
        modify_pb_trans_lock(armature, True)

        # 回到物体模式
        deselect_all_objects()
        if objs[0]:
            show_object(objs[0])
            select_and_activate(objs[0])

        # 应用纵Joint约束
        apply_cons(joint_parent)

        # 应用刚体约束
        apply_cons(rigidbody_parent)
        # 重设刚体约束
        set_rigidbody_cons(rigidbody_parent, armature, enabled=False)

        # 应用（移除）横Joint驱动器
        apply_driver(joint_parent)

        # 创建骨架修改器以方便后续

    def check_props(self, props):
        active_object = bpy.context.active_object
        if not active_object:
            self.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        pmx_root = find_pmx_root_with_child(active_object)
        if not pmx_root:
            self.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        armature = find_pmx_armature(pmx_root)
        if not armature:
            self.report(type={'ERROR'}, message=f'模型缺少骨架！')
            return False
        return True


class ChangeRestPoseEnd2Operator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.change_rest_pose_end2"
    bl_label = "应用姿态"
    bl_description = "应用当前姿态对网格和骨架的影响，需要手动选择受影响的MMD网格对象"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.end(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def end(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_change_rest_pose

        # 校验是否选中MMD模型
        if self.check_props(props) is False:
            return

        # 获取模型信息
        selected_objects = bpy.context.selected_objects
        roots = set()
        for obj in selected_objects:
            root = find_pmx_root_with_child(obj)
            if not root:
                continue
            roots.add(root)
        root = roots.pop()
        armature = find_pmx_armature(root)
        objs = find_pmx_objects(armature)
        force_apply = props.force_apply

        for obj in objs:
            deselect_all_objects()
            show_object(obj)
            select_and_activate(obj)

            if force_apply:
                # 创建骨架修改器
                armature_mod = self.create_armature_mod(obj, armature)
                # 移动骨架修改器到首位
                bpy.ops.object.modifier_move_to_index(modifier=armature_mod.name, index=0)
                # 强制应用修改器
                applyModifierForObjectWithShapeKeys(context, [armature_mod.name], False)
            else:
                if obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 1:
                    continue
                # 创建骨架修改器
                armature_mod = self.create_armature_mod(obj, armature)
                # 移动骨架修改器到首位
                bpy.ops.object.modifier_move_to_index(modifier=armature_mod.name, index=0)
                # 应用修改器
                bpy.ops.object.modifier_apply(modifier=armature_mod.name)

        deselect_all_objects()
        show_object(armature)
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        bpy.ops.pose.armature_apply(selected=False)
        bpy.ops.object.mode_set(mode='OBJECT')

        # 清理数据块，释放文件体积
        if force_apply:
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    def create_armature_mod(self, obj, armature):
        armature_mod = obj.modifiers.new(name="mmd_bone_order_override", type='ARMATURE')
        armature_mod.show_viewport = True
        armature_mod.show_render = True
        armature_mod.object = armature
        return armature_mod

    def check_props(self, props):
        selected_objects = bpy.context.selected_objects
        if not selected_objects:
            self.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False

        roots = set()
        for obj in selected_objects:
            root = find_pmx_root_with_child(obj)
            if not root:
                continue
            roots.add(root)
        if not roots:
            self.report(type={'ERROR'}, message=f'请选择MMD模型！')
            return False
        if len(roots) > 1:
            self.report(type={'ERROR'}, message=f'MMD模型数量大于1！')
            return False

        root = roots.pop()
        armature = find_pmx_armature(root)
        if not armature:
            self.report(type={'ERROR'}, message=f'模型缺少骨架！')
            return False

        return True


def modify_root_trans_lock(obj, lock):
    # 上锁 防止编辑root
    ancestor = obj.parent
    while ancestor is not None:
        ancestor.location = (0, 0, 0)
        ancestor.rotation_mode = 'QUATERNION'
        ancestor.rotation_quaternion = (1, 0, 0, 0)
        ancestor.rotation_mode = 'XYZ'
        ancestor.rotation_euler = (math.radians(0), math.radians(0), math.radians(0))
        ancestor.scale = (1, 1, 1)

        ancestor.lock_location = (lock, lock, lock)
        ancestor.lock_rotation_w = lock
        ancestor.lock_rotation = (lock, lock, lock)
        ancestor.lock_scale = (lock, lock, lock)

        ancestor = ancestor.parent


def modify_pb_trans_lock(armature, lock):
    for pb in armature.pose.bones:
        if not lock:
            # 记录当前lock状态
            if "original_location_lock" not in pb:
                pb["original_location_lock"] = pb.lock_location
            # 修改lock状态
            pb.lock_location = (lock, lock, lock)
        else:
            if "original_location_lock" in pb:
                pb.lock_location = pb["original_location_lock"]
                del pb["original_location_lock"]


def apply_cons(parent):
    for index, child in enumerate(parent.children):
        global_matrix = child.matrix_world

        if child.parent:
            child.matrix_local = child.parent.matrix_world.inverted() @ global_matrix
        else:
            child.matrix_local = global_matrix

        # 清除约束
        child.constraints.clear()


def set_rigidbody_cons(rigidbody_parent, armature, enabled=True):
    for rigidbody in rigidbody_parent.children:
        # 清除已有约束
        for constraint in reversed(rigidbody.constraints):
            rigidbody.constraints.remove(constraint)

        constraint = rigidbody.constraints.new("CHILD_OF")
        constraint.name = "mmd_tools_rigid_parent"
        constraint.enabled = enabled
        constraint.target = armature
        bl_name = rigidbody.mmd_rigid.bone
        if bl_name and bl_name in armature.data.bones:
            constraint.subtarget = bl_name


def apply_driver(parent):
    for child in parent.children:
        # 移除自定义属性
        if "original_location" in child:
            del child["original_location"]
        if "original_rotation" in child:
            del child["original_rotation"]

        # 移除 joint 的位置和旋转驱动器
        if child.animation_data and child.animation_data.drivers:
            for fcurve in child.animation_data.drivers:
                if fcurve.data_path.startswith("location") or fcurve.data_path.startswith("rotation_euler"):
                    child.animation_data.drivers.remove(fcurve)
