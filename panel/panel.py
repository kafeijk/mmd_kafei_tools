from ..operaters.modify_specify_content_operators import ModifySpecifyContentOperator
from ..operaters.change_tex_loc_operators import ChangeTexLocOperator
from ..operaters.modify_colorspace_operators import ModifyColorspaceOperator
from ..operaters.modify_sss_operators import ModifySssOperator
from ..operaters.organize_panel_operators import OrganizePanelOperator
from ..operaters.remove_uv_map_operators import RemoveUvMapOperator
from ..operaters.render_preview_operators import GenPreviewCameraOperator
from ..operaters.render_preview_operators import LoadRenderPresetOperator
from ..operaters.render_preview_operators import RenderPreviewOperator
from ..operaters.small_feature_operators import SmallFeatureOperator
from ..operaters.ssb_operators import AddSsbOperator, SelectAllSsbOperator
from ..operaters.transfer_preset_operators import TransferPresetOperator
from ..operaters.transfer_vg_weight_operators import TransferVgWeightOperator
from ..utils import *


class TransferPresetPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_transfer_preset"
    bl_label = "通用预设处理"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_transfer_preset

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        direction_col = col.column()
        direction_col.prop(props, "direction")
        common_param_col = col.column()
        common_param_box = common_param_col.box()
        direction = props.direction

        if direction in ['PMX2ABC', 'PMX2PMX']:
            if direction == 'PMX2ABC':
                source_pmx2abc_col = common_param_box.column()
                source_pmx2abc_col.prop(props, "source_pmx2abc")
            if direction == 'PMX2PMX':
                source_col = common_param_box.column()
                source_col.prop(props, "source")
                target_col = common_param_box.column()
                target_col.prop(props, "target")

            material_flag_col = common_param_box.column()
            material_flag_col.prop(props, "material_flag")

            uv_flag_col = common_param_box.column()
            uv_flag_col.prop(props, "uv_flag")
            vgs_col = common_param_box.column()
            vgs_col.prop(props, "vgs_flag")

            modifiers_col = common_param_box.column()
            modifiers_col.prop(props, "modifiers_flag")

            if direction == 'PMX2PMX':
                tolerance_col = common_param_box.column()
                tolerance_col.prop(props, "tolerance")

            if direction == 'PMX2ABC':
                normal_flag_col = common_param_box.column()
                normal_flag_col.prop(props, "normal_flag")

                toon_shading_flag_col = common_param_box.column()
                toon_shading_flag_col.prop(props, "toon_shading_flag")

                if props.toon_shading_flag:
                    toon_shading_flag_col = common_param_box.column()
                    box = toon_shading_flag_col.box()
                    box.prop(props, "face_locator")
                    face_col = box.column()

                    face_col.prop(props, "auto_face_location")
                    auto_face_location = props.auto_face_location
                    if not auto_face_location:
                        face_box = box.box()
                        face_box.prop(props, "face_object")
                        # 顶点组太多了，让用户手动输入名称
                        face_box.prop(props, "face_vg", icon='GROUP_VERTEX')

                    material_flag_col.enabled = False
                    uv_flag_col.enabled = False
                    vgs_col.enabled = False
                    modifiers_col.enabled = False
                    normal_flag_col.enabled = False
                else:
                    material_flag_col.enabled = True
                    uv_flag_col.enabled = True
                    vgs_col.enabled = True
                    modifiers_col.enabled = True
                    normal_flag_col.enabled = True

        if direction == 'ABC2ABC':
            abc_filepath_col = common_param_box.column()
            abc_filepath_col.prop(props, "abc_filepath")
            selected_only_col = common_param_box.column()
            selected_only_col.prop(props, "selected_only")
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
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        colorspace_col = col.column()
        colorspace_col.prop(props, "colorspace")
        keywords_col = col.column()
        keywords_col.prop(props, "keywords")
        selected_only_col = col.column()
        selected_only_col.prop(props, "selected_only")

        operator_col = col.column()
        operator_col.operator(ModifyColorspaceOperator.bl_idname, text=ModifyColorspaceOperator.bl_label)


class ModifySssPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_modify_sss"
    bl_label = "次表面简易修复"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_sss

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        strategy_col = col.column()
        strategy_col.prop(props, "strategy")
        modify_sss_col = col.column()
        modify_sss_col.operator(ModifySssOperator.bl_idname, text=ModifySssOperator.bl_label)


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
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        source_vg_name_col = col.column()
        source_vg_name_col.prop(props, "source_vg_name", icon='GROUP_VERTEX')
        target_vg_name_col = col.column()
        target_vg_name_col.prop(props, "target_vg_name", icon='GROUP_VERTEX')
        selected_v_only_col = col.column()
        selected_v_only_col.prop(props, "selected_v_only")

        operator_col = col.column()
        operator_col.operator(TransferVgWeightOperator.bl_idname, text=TransferVgWeightOperator.bl_label)


class RemoveSpecifyContentPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_remove_specify_content"
    bl_label = "物体操作"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_specify_content
        batch = props.batch

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        content_type_col = col.column()
        content_type_col.prop(props, "content_type")
        content_type = props.content_type
        if content_type == 'ADD_UV_MAP':
            uv_name_col = col.column()
            uv_name_col.prop(props, "uv_name")
            average_islands_flag_col = col.column()
            average_islands_flag_col.prop(props, "average_islands_flag")
        elif content_type == 'ADD_COLOR_ATTRIBUTE':
            color_attribute_name_col = col.column()
            color_attribute_name_col.prop(props, "color_attribute_name")
            color_col = col.column()
            color_col.prop(props, "color")
        elif content_type == 'REMOVE_UV_MAP':
            keep_first_col = col.column()
            keep_first_col.prop(props, "keep_first")
        elif content_type == 'REMOVE_COLOR_ATTRIBUTE':
            keep_first_col = col.column()
            keep_first_col.prop(props, "keep_first")
        elif content_type == 'REMOVE_MATERIAL':
            create_default_col = col.column()
            create_default_col.prop(props, "create_default")
        elif content_type == 'REMOVE_MODIFIER':
            keep_first_col = col.column()
            keep_first_col.prop(props, "keep_first")
        elif content_type == 'REMOVE_VERTEX_GROUP':
            keep_locked_col = col.column()
            keep_locked_col.prop(props, "keep_locked")
        elif content_type == 'REMOVE_SHAPE_KEY':
            keep_current_col = col.column()
            keep_current_col.prop(props, "keep_current")

        operator_col = col.column()
        operator_col.operator(ModifySpecifyContentOperator.bl_idname, text=ModifySpecifyContentOperator.bl_label)


class SmallFeaturePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_sf"
    bl_label = "小功能"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_sf

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        option_col = col.column()
        option_col.prop(props, "option")

        operators_col = col.column()
        operators_col.operator(SmallFeatureOperator.bl_idname, text=SmallFeatureOperator.bl_label)


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
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        new_folder_col = col.column()
        new_folder_col.prop(props, "new_folder")

        show_batch_props(col, False, False, batch)
        remove_empty_col = col.column()
        remove_empty_col.prop(props, "remove_empty")

        change_tex_loc_col = col.column()
        change_tex_loc_col.operator(ChangeTexLocOperator.bl_idname, text=ChangeTexLocOperator.bl_label)


# class AddSsbPanel:
class AddSsbPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_add_ssb"
    bl_label = "追加次标准骨骼"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_add_ssb
        base_props = props.base
        batch = props.batch
        force = props.force
        batch_flag = batch.flag

        layout = self.layout
        box = layout.box()
        model_row = box.row()
        model_row.prop(props, "model")
        model_row.enabled = not batch_flag
        scale_row = box.row()
        scale_row.prop(props, "scale")
        scale_row.enabled = not batch_flag
        row = box.row()
        show_batch_props(box, True, True, batch)
        box = layout.box()
        row = box.row()
        row.prop(base_props, "root_checked")
        row = box.row()
        row.prop(base_props, "arm_twist_checked")
        row = box.row()
        row.separator()
        row.prop(base_props, "enable_elbow_offset_checked")
        arm_twist_checked = base_props.arm_twist_checked
        row.enabled = arm_twist_checked
        row = box.row()
        row.prop(base_props, "wrist_twist_checked")
        row = box.row()
        row.prop(base_props, "upper_body2_checked")
        row = box.row()
        row.prop(base_props, "groove_checked")
        row = box.row()
        row.prop(base_props, "waist_checked")
        row = box.row()
        row.prop(base_props, "ik_p_checked")
        row = box.row()
        row.prop(base_props, "view_center_checked")
        row = box.row()
        row.prop(base_props, "ex_checked")
        row = box.row()
        row.separator()
        row.prop(base_props, "enable_leg_d_controllable_checked")
        ex_checked = base_props.ex_checked
        row.enabled = ex_checked
        row = box.row()
        row.prop(base_props, "dummy_checked")
        row = box.row()
        row.prop(base_props, "shoulder_p_checked")
        row = box.row()
        row.prop(base_props, "thumb0_checked")
        row.enabled = not force
        row = box.row()
        row.separator()
        row.prop(base_props, "enable_thumb_local_axes_checked")
        thumb0_checked = base_props.thumb0_checked
        row.enabled = thumb0_checked
        row = box.row()
        row.prop(base_props, "enable_gen_frame_checked")

        if not props.enable_hidden_option:
            icon = 'HIDE_ON' if not props.enable_hidden_option else 'ERROR'
            row.prop(props, "enable_hidden_option", icon=icon, text="", emboss=False)

        if props.enable_hidden_option:
            row = box.row()
            row.prop(props, "force")
            icon = 'HIDE_ON' if not props.enable_hidden_option else 'ERROR'
            row.prop(props, "enable_hidden_option", icon=icon, text="", emboss=False)
        row = box.row()
        row.operator(SelectAllSsbOperator.bl_idname, text=SelectAllSsbOperator.bl_label)
        row.enabled = not force
        box = layout.box()
        row = box.row()
        row.operator(AddSsbOperator.bl_idname, text=AddSsbOperator.bl_label)


class RemoveUvMapPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_remove_uv_map"
    bl_label = "移除冗余UV"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_remove_uv_map
        batch = props.batch

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        show_batch_props(col, False, False, batch)

        operator_col = col.column()
        operator_col.operator(RemoveUvMapOperator.bl_idname, text=RemoveUvMapOperator.bl_label)


class OrganizePanelPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_organize_panel"
    bl_label = "面板整理"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_organize_panel
        batch = props.batch

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        bone_panel_flag_col = col.column()
        bone_panel_flag_col.prop(props, "bone_panel_flag")
        morph_panel_flag_col = col.column()
        morph_panel_flag_col.prop(props, "morph_panel_flag")
        rigid_body_panel_flag_col = col.column()
        rigid_body_panel_flag_col.prop(props, "rigid_body_panel_flag")
        display_panel_flag_col = col.column()
        display_panel_flag_col.prop(props, "display_panel_flag")

        bone_flag_row = col.row()
        bone_flag_row.separator()
        bone_flag_row.separator()
        bone_flag_row.prop(props, "bone_flag")
        if props.display_panel_flag is False:
            bone_flag_row.enabled = False

        exp_flag_row = col.row()
        exp_flag_row.separator()
        exp_flag_row.separator()
        exp_flag_row.prop(props, "exp_flag")
        if props.display_panel_flag is False:
            exp_flag_row.enabled = False

        show_batch_props(col, True, True, batch)

        organize_panel_col = col.column()
        organize_panel_col.operator(OrganizePanelOperator.bl_idname, text=OrganizePanelOperator.bl_label)


class RenderPreviewPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_render_preview"
    bl_label = "渲染预览图"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_render_preview
        align = props.align
        batch = props.batch

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        type_col = col.column()
        type_col.prop(props, "type")
        scale_col = col.column()
        scale_col.prop(props, "scale")
        rotation_col = col.column(align=True)
        rotation_col.prop(props, "rotation_euler_x")
        rotation_col_y = rotation_col.column(align=True)
        rotation_col_y.prop(props, "rotation_euler_y")
        rotation_col_y.enabled = not align  # Disable if align is True
        rotation_col.prop(props, "rotation_euler_z")
        auto_follow_col = rotation_col.column()
        auto_follow_col.prop(props, "auto_follow")
        align_col = col.column()
        align_col.prop(props, "align")

        batch_box = show_batch_props(col, True, True, batch)
        if batch_box:
            force_center_col = batch_box.column()
            force_center_col.prop(props, "force_center")

        load_render_preset_row = col.row()
        load_render_preset_row.operator(LoadRenderPresetOperator.bl_idname, text=LoadRenderPresetOperator.bl_label)
        render_row = col.row()
        render_row.operator(GenPreviewCameraOperator.bl_idname, text=GenPreviewCameraOperator.bl_label)
        render_row.operator(RenderPreviewOperator.bl_idname, text=RenderPreviewOperator.bl_label)


if __name__ == "__main__":
    bpy.utils.register_class(TransferPresetPanel)
