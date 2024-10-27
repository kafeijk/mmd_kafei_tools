from ..utils import *


class SmallFeatureOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.sf"
    bl_label = "执行"
    bl_description = "执行"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_sf
        if self.check_props(props) is False:
            return

        option = props.option
        if option == 'BAKE':
            self.select_bake_bone()
        elif option == 'SCENE_ROOT':
            self.gen_scene_root()

    def select_bake_bone(self):
        """选择用于烘焙VMD的骨骼"""
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

    def gen_scene_root(self):
        """创建一个空物体，以实现对整个场景的统一控制"""
        if len(bpy.data.objects) == 0:
            return

        has_root = True
        root = find_ancestor(bpy.data.objects[0])
        for obj in bpy.data.objects:
            if root == find_ancestor(obj):
                continue
            has_root = False
            break

        if has_root:
            deselect_all_objects()
            select_and_activate(root)
            return

        root = bpy.data.objects.new("root", None)
        bpy.context.collection.objects.link(root)
        # 遍历场景中的物体
        for obj in bpy.data.objects:
            # 检查物体是否没有parent
            if obj.parent is None and obj != root:
                # 将其parent设置为root（保持变换）
                obj.parent = root
                obj.matrix_parent_inverse = root.matrix_world.inverted()
        # 选中root空物体
        deselect_all_objects()
        select_and_activate(root)

    def check_props(self, props):
        option = props.option
        if option == 'BAKE':
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
