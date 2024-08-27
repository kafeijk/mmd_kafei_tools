from ..utils import *


class SelectBoneOperator(bpy.types.Operator):
    # TODO 暂时想不到还有其它什么用途骨骼，可能不限于mmd骨骼
    bl_idname = "mmd_kafei_tools.select_bone"
    bl_label = "选择"
    bl_description = "骨骼选择"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_select_bone
        if self.check_props(props) is False:
            return

        # 获取激活的物体
        obj = bpy.context.active_object
        pmx_root = find_pmx_root_with_child(obj)
        armature = find_pmx_armature(pmx_root)

        # 选中骨架并进入姿态模式
        deselect_all_objects()
        show_object(armature)
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='POSE')

        category = props.category
        if category == 'BAKE':
            for bone in armature.pose.bones:
                if bone.mmd_bone.name_j in PMX_BAKE_BONES:
                    bone.bone.select = True
                    armature.data.bones.active = bone.bone

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
