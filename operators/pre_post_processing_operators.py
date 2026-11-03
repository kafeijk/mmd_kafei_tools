import bpy

from ..constants import INVALID_CHARS
from ..utils import batch_process, check_batch_props, translate
from .change_tex_loc_operators import do_change_tex_loc
from .organize_panel_operators import organize_panel
from .remove_uv_map_operators import do_remove_uv_maps


class PrePostProcessingOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.pre_post_processing"
    bl_label = "执行"
    bl_description = "执行预处理/后处理流程。"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_pre_post_processing
        if not self.check_props(props):
            return
        batch_process(do_pre_post_processing, props, f_flag=True)

    def check_props(self, props):
        if not (props.change_tex_loc or props.remove_uv_map or props.organize_panel):
            self.report(type={'ERROR'}, message=translate("请至少勾选一项处理！"))
            return False
        if not check_batch_props(self, props.batch):
            return False
        if props.change_tex_loc:
            new_folder = props.new_folder.strip()
            if not new_folder:
                self.report(type={'ERROR'}, message=translate("请填写贴图文件夹名称！"))
                return False
            if any(char in new_folder for char in INVALID_CHARS):
                self.report(type={'ERROR'}, message=translate("贴图文件夹名称无效！"))
                return False
        return True


def do_pre_post_processing(pmx_root, props, filepath):
    """按勾选项依次执行，文件只在流程开始前导入、全部完成后导出"""
    if props.change_tex_loc:
        do_change_tex_loc(pmx_root, props, filepath)
    if props.remove_uv_map:
        do_remove_uv_maps(pmx_root)
    if props.organize_panel:
        organize_panel(pmx_root, props)
