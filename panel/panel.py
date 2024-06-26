from ..operaters.change_tex_loc_operators import ChangeTexLocOperator
from ..operaters.gen_display_item_frame_operators import GenDisplayItemFrameOperator
from ..operaters.modify_colorspace_operators import ModifyColorspaceOperator
from ..operaters.modify_sss_operators import ModifySssOperator
from ..operaters.render_preview_operators import GenPreviewCameraOperator
from ..operaters.render_preview_operators import LoadRenderPresetOperator
from ..operaters.render_preview_operators import RenderPreviewOperator
from ..operaters.select_bone_operators import SelectBoneOperator
from ..operaters.transfer_preset_operators import TransferPresetOperator
from ..operaters.transfer_vg_weight_operators import TransferVgWeightOperator
from ..operaters.remove_specify_content_operators import RemoveSpecifyContentOperator
from ..utils import *


class TransferPresetPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_transfer_preset"
    bl_label = "通用材质传递"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_transfer_preset

        layout = self.layout
        direction_row = self.layout.row()
        direction_row.prop(props, "direction")
        common_param_row = self.layout.row()
        common_param_box = common_param_row.box()
        direction = props.direction
        if direction == 'PMX2PMX':
            source_row = common_param_box.row()
            source_row.prop(props, "source")
            target_row = common_param_box.row()
            target_row.prop(props, "target")

        material_flag_row = common_param_box.row()
        material_flag_row.prop(props, "material_flag")

        vgs_row = common_param_box.row()
        vgs_row.prop(props, "vgs_flag")

        modifiers_row = common_param_box.row()
        modifiers_row.prop(props, "modifiers_flag")
        if props.modifiers_flag:
            vgs_row.enabled = False
        else:
            vgs_row.enabled = True

        gen_skin_uv_flag_row = common_param_box.row()
        gen_skin_uv_flag_row.prop(props, "gen_skin_uv_flag")

        if props.gen_skin_uv_flag:
            skin_uv_name_row = common_param_box.row()
            skin_uv_name_box = skin_uv_name_row.box()
            skin_uv_name_box.prop(props, "skin_uv_name")

        if direction == 'PMX2ABC':
            toon_shading_flag_row = common_param_box.row()
            toon_shading_flag_row.prop(props, "toon_shading_flag")

        if props.toon_shading_flag:
            toon_shading_flag_row = common_param_box.row()
            box = toon_shading_flag_row.box()
            box.prop(props, "face_locator")
            face_row = box.row()

            face_row.prop(props, "auto_face_location")
            auto_face_location = props.auto_face_location
            if not auto_face_location:
                face_box = box.box()
                face_box.prop(props, "face_object")
                # 顶点组太多了，让用户手动输入名称
                face_box.prop(props, "face_vg", icon='GROUP_VERTEX')

            material_flag_row.enabled = False
            vgs_row.enabled = False
            modifiers_row.enabled = False
        else:
            material_flag_row.enabled = True
            if props.modifiers_flag:
                vgs_row.enabled = False
            else:
                vgs_row.enabled = True
            modifiers_row.enabled = True

        row = layout.row()
        row.operator(TransferPresetOperator.bl_idname, text=TransferPresetOperator.bl_label)


class ToolsPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_tools"
    bl_label = "工具"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 1

    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout


class ModifyColorspacePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_modify_colorspace"
    bl_label = "修改贴图色彩空间"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_colorspace
        layout = self.layout
        box = layout.box()

        colorspace_row = box.row()
        colorspace_row.prop(props, "colorspace")
        keywords_row = box.row()
        keywords_row.prop(props, "keywords")
        selected_only_row = box.row()
        selected_only_row.prop(props, "selected_only")
        operator_row = box.row()
        operator_row.operator(ModifyColorspaceOperator.bl_idname, text=ModifyColorspaceOperator.bl_label)


class ModifySssPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_modify_sss"
    bl_label = "修复次表面发青问题"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        box = layout.box()
        modify_sss_row = box.row()
        modify_sss_row.operator(ModifySssOperator.bl_idname, text=ModifySssOperator.bl_label)


class TransferVgWeightPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_transfer_vg_weight"
    bl_label = "权重转移"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_transfer_vg_weight
        layout = self.layout
        box = layout.box()
        source_vg_row = box.row()
        source_vg_row.prop(props, "source_vg", icon='GROUP_VERTEX')
        target_vg_row = box.row()
        target_vg_row.prop(props, "target_vg", icon='GROUP_VERTEX')
        operator_row = box.row()
        operator_row.operator(TransferVgWeightOperator.bl_idname, text=TransferVgWeightOperator.bl_label)


class SelectBonePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_select_bone"
    bl_label = "选择指定用途骨骼"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        props = scene.mmd_kafei_tools_select_bone
        box = layout.box()

        category_row = box.row()
        category_row.prop(props, "category")
        operators_row = box.row()
        operators_row.operator(SelectBoneOperator.bl_idname, text=SelectBoneOperator.bl_label)


class PrePostProcessingPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_pre_post_processing"
    bl_label = "预处理 / 后处理"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 2

    def draw(self, context):
        layout = self.layout


class ChangeTexLocPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_change_tex_loc"
    bl_label = "修改贴图路径"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_change_tex_loc
        batch = props.batch

        layout = self.layout
        box = layout.box()
        new_folder_row = box.row()
        new_folder_row.prop(props, "new_folder")

        directory_row = box.row()
        directory_row.prop(batch, "directory")
        threshold_row = box.row()
        threshold_row.prop(batch, "threshold")
        suffix_row = box.row()
        suffix_row.prop(batch, "suffix")
        remove_empty_row = box.row()
        remove_empty_row.prop(props, "remove_empty")
        change_tex_loc_row = box.row()
        change_tex_loc_row.operator(ChangeTexLocOperator.bl_idname, text=ChangeTexLocOperator.bl_label)


class GenDisplayItemFramePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_gen_display_item_frame"
    bl_label = "生成显示枠"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_gen_display_item_frame
        batch = props.batch

        layout = self.layout
        box = layout.box()
        show_batch_props(box, batch)
        gen_display_item_row = box.row()
        gen_display_item_row.operator(GenDisplayItemFrameOperator.bl_idname, text=GenDisplayItemFrameOperator.bl_label)


class RemoveSpecifyContentPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_remove_specify_content"
    bl_label = "移除指定内容"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        props = scene.mmd_kafei_tools_remove_specify_content
        batch = props.batch
        box = layout.box()

        content_type_row = box.row()
        content_type_row.prop(props, "content_type")
        content_type = props.content_type
        if content_type == 'MATERIAL':
            create_default_row = box.row()
            create_default_row.prop(props, "create_default")
        elif content_type == 'MODIFIER':
            keep_first_row = box.row()
            keep_first_row.prop(props, "keep_first")
        elif content_type == 'VERTEX_GROUP':
            # 无额外参数
            pass
        elif content_type == 'SHAPE_KEY':
            keep_current_row = box.row()
            keep_current_row.prop(props, "keep_current")
        elif content_type == 'UV_MAP':
            keep_first_row = box.row()
            keep_first_row.prop(props, "keep_first")
            show_batch_props(box, batch)

        operator_row = box.row()
        operator_row.operator(RemoveSpecifyContentOperator.bl_idname, text=RemoveSpecifyContentOperator.bl_label)


class RenderPreviewPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_render_preview"
    bl_label = "渲染预览图"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_render_preview
        align = props.align
        batch = props.batch
        layout = self.layout
        box = layout.box()

        type_row = box.row(align=True)
        type_row.prop(props, "type")
        rotation_row = box.row(align=True)
        rotation_row.prop(props, "rotation_euler_x")
        rotation_row_y = rotation_row.row(align=True)
        rotation_row_y.prop(props, "rotation_euler_y")
        rotation_row_y.enabled = not align  # Disable if align is True
        rotation_row.prop(props, "rotation_euler_z")

        auto_follow_row = rotation_row.row()
        auto_follow_row.alignment = 'CENTER'
        auto_follow_row.prop(props, "auto_follow")

        scale_row = box.row()
        scale_row.prop(props, "scale")

        align_row = box.row()
        align_row.prop(props, "align")

        batch_box = show_batch_props(box, batch)
        if batch_box:
            force_center_row = batch_box.row()
            force_center_row.prop(props, "force_center")

        load_render_preset_row = box.row()
        load_render_preset_row.operator(LoadRenderPresetOperator.bl_idname, text=LoadRenderPresetOperator.bl_label)
        render_row = box.row()
        render_row.operator(GenPreviewCameraOperator.bl_idname, text=GenPreviewCameraOperator.bl_label)
        render_row.operator(RenderPreviewOperator.bl_idname, text=RenderPreviewOperator.bl_label)


if __name__ == "__main__":
    bpy.utils.register_class(TransferPresetPanel)
