import bpy

from ..batch_utils import BatchProcessOperatorMixin
from ..constants import BATCH_TASK_PRE_POST_PROCESSING, INVALID_CHARS
from ..utils import check_batch_props, translate
from .change_tex_loc_operators import do_change_tex_loc
from .organize_panel_operators import organize_panel
from .remove_uv_map_operators import do_remove_uv_maps


class PrePostProcessingOperator(BatchProcessOperatorMixin, bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.pre_post_processing"
    bl_label = "执行"
    bl_description = "执行勾选的预处理/后处理流程。"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能
    batch_task = BATCH_TASK_PRE_POST_PROCESSING
    batch_f_flag = True

    def execute(self, context):
        props = context.scene.mmd_kafei_tools_pre_post_processing
        if not self.check_props(props):
            return {'CANCELLED'}
        return self.start_batch_process(context, props, do_pre_post_processing)

    def check_props(self, props):
        if not (props.change_tex_loc or props.remove_uv_map or props.organize_panel):
            self.report(type={'ERROR'}, message=translate("请至少勾选一项处理！"))
            return False
        if props.organize_panel:
            compatibility_effective = props.compatibility_flag and any((
                props.fix_bone_name_flag,
                props.fix_morph_name_flag,
                props.fix_all_materials_flag,
                props.fix_rigid_body_size_flag,
            ))
            organize_effective = any((
                props.bone_panel_flag,
                props.morph_panel_flag,
                props.rigid_body_panel_flag,
                props.display_panel_flag,
                props.translation_flag,
                compatibility_effective,
            ))
            if not organize_effective:
                self.report(type={'ERROR'}, message=translate("请至少勾选一项面板整理选项！"))
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
            # 拒绝路径段、Windows 保留设备名与结尾的点
            reserved_names = {
                "CON", "PRN", "AUX", "NUL",
                "CONIN$", "CONOUT$",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            }
            if (
                    new_folder in (".", "..")
                    or new_folder.endswith(".")
                    or new_folder.split(".", 1)[0].upper() in reserved_names
            ):
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
