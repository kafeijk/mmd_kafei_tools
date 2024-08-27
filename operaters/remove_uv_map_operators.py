from ..utils import *


class RemoveUvMapOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.remove_uv_map"
    bl_label = "执行"
    bl_description = "移除冗余UV贴图"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_remove_uv_map
        if not self.check_props(props):
            return

        batch_process(self.do_remove, props, f_flag=False)

    def check_props(self, props):
        batch = props.batch
        if not check_batch_props(self, batch):
            return False
        return True

    def do_remove(self, pmx_root, props):
        armature = find_pmx_armature(pmx_root)
        objs = find_pmx_objects(armature)
        for obj in objs:
            deselect_all_objects()
            select_and_activate(obj)
            self.process_uvs(obj, True)

    def process_uvs(self, obj, keep_first):
        uv_maps = obj.data.uv_layers
        if keep_first:
            uv_maps_to_remove = uv_maps[1:]
        else:
            uv_maps_to_remove = uv_maps
        for uv_map in reversed(uv_maps_to_remove):
            obj.data.uv_layers.remove(uv_map)
        # https://blender.stackexchange.com/questions/163300/how-to-update-an-object-after-changing-its-uv-coordinates
        obj.data.update()
