from ..operaters.modify_specify_content_operators import ModifySpecifyContentOperator
from ..operaters.modify_specify_content_operators import ArrangeObjectOperator
from ..operaters.change_tex_loc_operators import ChangeTexLocOperator
from ..operaters.modify_colorspace_operators import ModifyColorspaceOperator
from ..operaters.organize_panel_operators import OrganizePanelOperator
from ..operaters.remove_uv_map_operators import RemoveUvMapOperator
from ..operaters.render_preview_operators import GenPreviewCameraOperator
from ..operaters.render_preview_operators import LoadRenderPresetOperator
from ..operaters.render_preview_operators import RenderPreviewOperator
from ..operaters.small_feature_operators import SmallFeatureOperator
from ..operaters.ssb_operators import AddSsbOperator, SelectAllSsbOperator
from ..operaters.transfer_preset_operators import TransferPresetOperator
from ..operaters.transfer_vg_weight_operators import TransferVgWeightOperator
from ..operaters.change_rest_pose_operators import ChangeRestPoseStartOperator
from ..operaters.change_rest_pose_operators import ChangeRestPoseEndOperator
from ..operaters.change_rest_pose_operators import ChangeRestPoseEnd2Operator
from ..operaters.bone_operators import FlipBoneOperator
from ..operaters.bone_operators import DeleteInvalidRigidbodyJointOperator
from ..operaters.bone_operators import SelectPhysicalBoneOperator
from ..operaters.bone_operators import SelectBakeBoneOperator
from ..operaters.bone_operators import SelectLinkedBoneOperator
from ..operaters.bone_operators import SelectRingBoneOperator
from ..operaters.bone_operators import SelectExtendChildrenBoneOperator
from ..operaters.bone_operators import SelecExtendParentBoneOperator
from ..operaters.bone_operators import SelectLessParentBoneOperator
from ..operaters.bone_operators import SelectLessChildrenBoneOperator
from ..operaters.bone_operators import SelectMoreBoneOperator
from ..operaters.bone_operators import SelectLessBoneOperator
from ..operaters.fill_suffix_operators import FillSuffixChangeTexlocOperator
from ..operaters.fill_suffix_operators import FillSuffixSsbOperator
from ..operaters.fill_suffix_operators import FillSuffixRemoveUvMapOperator
from ..operaters.fill_suffix_operators import FillSuffixOrganizePanelOperator
from ..operaters.fill_suffix_operators import FillSuffixRenderPreviewOperator
from ..operaters.render_settings_operators import RenderSettingsOperator
from ..operaters.render_settings_operators import WorldSettingsOperator
from ..operaters.render_settings_operators import ResolutionSettingsOperator
from ..operaters.render_settings_operators import SwapResolutionOperator
from ..operaters.render_settings_operators import LightSettingsOperator
from ..operaters.quick_operation_operators import MergeVerticesOperator
from ..operaters.quick_operation_operators import DummyOperator
from ..operaters.quick_operation_operators import SetMatNameByObjNameOperator
from ..operaters.quick_operation_operators import SetObjNameByMatNameOperator
from ..operaters.quick_operation_operators import DetectOverlappingFacesOperator
from ..operaters.quick_operation_operators import CleanSceneOperator
from ..utils import *
import addon_utils


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


class SceneSettingsPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_scene_settings"
    bl_label = "场景设置"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 1

    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout


class RenderSettingsPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_render_settings"
    bl_label = "渲染设置"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_scene_settings"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_render_settings

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        engine_col = col.column()
        engine_row = engine_col.row()
        engine_row.prop(props, "engine")
        engine_row.operator(RenderSettingsOperator.bl_idname, text="", icon="TRIA_RIGHT")

        props2 = scene.mmd_kafei_tools_world_settings
        world_col = col.column()
        world_row = world_col.row()
        world_row.prop(props2, "world_name")
        world_row.operator(WorldSettingsOperator.bl_idname, text="", icon="TRIA_RIGHT")

        rd = scene.render
        transparent_col = col.column()
        transparent_col.prop(rd, "film_transparent", text="Transparent")


class OutputSettingsPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_output_settings"
    bl_label = "输出设置"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_scene_settings"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        row = layout.row(align=True)
        col1 = row.column(align=True)
        col2 = row.column(align=True)
        col2.scale_x = 0.3

        props = scene.mmd_kafei_tools_output_settings
        rd = context.scene.render

        # 分辨率
        col1.prop(props, "resolution", text="Resolution")
        col1.prop(rd, "resolution_x", text="X")
        col1.prop(rd, "resolution_y", text="Y")
        col2.operator(ResolutionSettingsOperator.bl_idname, text="", icon="TRIA_RIGHT")
        col2.operator(SwapResolutionOperator.bl_idname, text="⇅", emboss=True)

        # 帧率
        col1.separator()
        col11 = col1.column(heading="Frame Rate")
        if bpy.types.RENDER_PT_format._preset_class is None:
            bpy.types.RENDER_PT_format._preset_class = bpy.types.RENDER_MT_framerate_presets
        args = rd.fps, rd.fps_base, bpy.types.RENDER_PT_format._preset_class.bl_label
        fps_label_text, show_framerate = bpy.types.RENDER_PT_format._draw_framerate_label(*args)
        col11.menu("RENDER_MT_framerate_presets", text=fps_label_text)
        if show_framerate:
            col111 = col11.column(align=True)
            col111.prop(rd, "fps")
            col111.prop(rd, "fps_base", text="Base")

        # 输出文件格式
        col1.separator()
        image_settings = rd.image_settings
        col1.template_image_settings(image_settings, color_management=False)


class LightSettingsPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_light_settings"
    bl_label = "灯光设置"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_scene_settings"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_light_settings

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        target_type_col = col.column()
        target_type_col.prop(props, "target_type")

        target_type = props.target_type
        if target_type == "ARMATURE":
            bone_name_col = col.column()
            bone_name_col.prop(props, "bone_name")
        elif target_type == "MESH":
            vg_name_col = col.column()
            vg_name_col.prop(props, "vg_name")

        col.separator()
        col = col.column()
        col.prop(props, "main_distance")
        col.prop(props, "fill_distance")
        col.prop(props, "main_position")
        col.separator()
        col.prop(props, "back_distance")
        col.prop(props, "back_angle")

        operators_col = col.column()
        operators_col.operator(LightSettingsOperator.bl_idname, text=LightSettingsOperator.bl_label)


class ModifyColorspacePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_modify_colorspace"
    bl_label = "色彩空间调整"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_scene_settings"
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_colorspace

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        keywords = props.keywords

        source_colorspace_col = col.column()
        source_colorspace_col.prop(props, "source_colorspace")
        if keywords:
            source_colorspace_col.enabled = False
        else:
            source_colorspace_col.enabled = True

        target_colorspace_col = col.column()
        target_colorspace_col.prop(props, "target_colorspace")

        keywords_col = col.column()
        keywords_col.prop(props, "keywords")

        operator_col = col.column()
        operator_col.operator(ModifyColorspaceOperator.bl_idname, text=ModifyColorspaceOperator.bl_label)


class SmallFeaturePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_sf"
    bl_label = "小功能"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_scene_settings"
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


class ToolsPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_tools"
    bl_label = "工具"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 2

    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout


class RemoveSpecifyContentPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_remove_specify_content"
    bl_label = "物体操作"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 1
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
        elif content_type in ['REMOVE_MODIFIER', 'REMOVE_CONSTRAINT']:
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


class ArrangeObjectPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_arrange_object"
    bl_label = "物体排列"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_arrange_object

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        arrangement_type = props.arrangement_type
        col.prop(props, "arrangement_type")
        if arrangement_type == "ARRAY":
            col.prop(props, "direction")
        col.prop(props, "order")

        if arrangement_type == "ARRAY":
            col2 = col.column(align=True)
            col2.prop(props, "start_trans", index=0, text="起始 X")
            direction = props.direction
            if direction == "HORIZONTAL":
                col2.prop(props, "start_trans", index=1, text="Y")
            else:
                col2.prop(props, "start_trans", index=2, text="Z")
            col2.prop(props, "spacing", index=0, text="间距 X")
            if direction == "HORIZONTAL":
                col2.prop(props, "spacing", index=1, text="Y")
            else:
                col2.prop(props, "spacing", index=2, text="Z")

            col2.prop(props, "num_per_row")
            col2.prop(props, "threshold")
        elif arrangement_type in ["ARC", "CIRCLE"]:
            col2 = col.column(align=True)
            col2.prop(props, "radius")
            col2.prop(props, "num_per_circle")
            col2.prop(props, "spacing_circle")
            col2.prop(props, "offset")
            col2.prop(props, "threshold")

        operator_col = col.column()
        operator_col.operator(ArrangeObjectOperator.bl_idname, text=ArrangeObjectOperator.bl_label)


class ModelModificationPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_model_modification"
    bl_label = "模型修改"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 3

    def draw(self, context):
        scene = context.scene
        layout = self.layout


class ChangeRestPosePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_change_rest_pose"
    bl_label = "初始姿态调整"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_model_modification"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_change_rest_pose

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        prop_col = col.column()
        prop_col.prop(props, "h_joint_strategy")
        prop_col.prop(props, "force_apply")

        operator_col = col.column(align=True)
        operator_row = operator_col.row(align=True)
        operator_row.operator(ChangeRestPoseStartOperator.bl_idname, text=ChangeRestPoseStartOperator.bl_label)
        operator_row.operator(ChangeRestPoseEndOperator.bl_idname, text=ChangeRestPoseEndOperator.bl_label)
        operator_row = operator_col.row(align=True)
        operator_row.operator(ChangeRestPoseEnd2Operator.bl_idname, text=ChangeRestPoseEnd2Operator.bl_label)


class BonePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_bone"
    bl_label = "骨骼操作"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_model_modification"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        operator_col = col.column(align=True)

        # 选择 物理骨骼 烘焙骨骼
        operator_row = operator_col.row(align=True)
        operator_row.operator(SelectPhysicalBoneOperator.bl_idname, text=SelectPhysicalBoneOperator.bl_label,
                              icon="VIEWZOOM")
        operator_row.operator(SelectBakeBoneOperator.bl_idname, text=SelectBakeBoneOperator.bl_label, icon="VIEWZOOM")
        # 选择 关联骨骼 并排骨骼
        operator_row = operator_col.row(align=True)
        link_bone_col = operator_row.column(align=True)
        link_bone_col.operator(SelectLinkedBoneOperator.bl_idname, text=SelectLinkedBoneOperator.bl_label,
                               icon="VIEWZOOM")
        ring_bone_bol = operator_row.column(align=True)
        ring_bone_bol.operator(SelectRingBoneOperator.bl_idname, text=SelectRingBoneOperator.bl_label, icon="VIEWZOOM")

        # 选择 镜像骨骼
        operator_row = operator_col.row(align=True)
        mirror_bone_col = operator_row.column(align=True)
        if bpy.context.active_object and bpy.context.active_object.mode == "EDIT":
            mirror_bone_col.operator("armature.select_mirror", text="镜像骨骼", icon="VIEWZOOM")
        else:
            mirror_bone_col.operator("pose.select_mirror", text="镜像骨骼", icon="VIEWZOOM")
        flip_bone_col = operator_row.column(align=True)
        flip_bone_col.operator(FlipBoneOperator.bl_idname, text=FlipBoneOperator.bl_label, icon='PASTEFLIPDOWN')
        # mirror_bone_col.label(text="")  # 空白标签，占据空间

        # 拓展 缩减选择
        operator_row = operator_col.row(align=True)
        more_col = operator_row.column(align=True)
        more_col.operator(SelectMoreBoneOperator.bl_idname, text=SelectMoreBoneOperator.bl_label, icon="VIEWZOOM")
        less_col = operator_row.column(align=True)
        less_col.operator(SelectLessBoneOperator.bl_idname, text=SelectLessBoneOperator.bl_label, icon="VIEWZOOM")

        # 选择 父子骨骼
        operator_row = operator_col.row(align=True)
        extend_parent_col = operator_row.column(align=True)
        extend_parent_col.operator(SelecExtendParentBoneOperator.bl_idname, text=SelecExtendParentBoneOperator.bl_label,
                                   icon="VIEWZOOM")
        extend_children_col = operator_row.column(align=True)
        extend_children_col.operator(SelectExtendChildrenBoneOperator.bl_idname,
                                     text=SelectExtendChildrenBoneOperator.bl_label,
                                     icon="VIEWZOOM")

        less_parent_col = operator_row.column(align=True)
        less_parent_col.operator(SelectLessParentBoneOperator.bl_idname, text=SelectLessParentBoneOperator.bl_label,
                                 icon="VIEWZOOM")
        less_children_col = operator_row.column(align=True)
        less_children_col.operator(SelectLessChildrenBoneOperator.bl_idname,
                                   text=SelectLessChildrenBoneOperator.bl_label,
                                   icon="VIEWZOOM")

        # 翻转姿态 清理无效刚体Joint
        operator_row = operator_col.row(align=True)
        operator_row.operator(DeleteInvalidRigidbodyJointOperator.bl_idname,
                              text=DeleteInvalidRigidbodyJointOperator.bl_label, icon="TRASH")

        active_object = bpy.context.active_object
        if active_object and active_object.type == "ARMATURE" and active_object.mode in ["EDIT", "POSE"]:
            link_bone_col.enabled = True
            ring_bone_bol.enabled = True
            flip_bone_col.enabled = True
            extend_parent_col.enabled = True
            extend_children_col.enabled = True
            less_parent_col.enabled = True
            less_children_col.enabled = True
            more_col.enabled = True
            less_col.enabled = True
        else:
            link_bone_col.enabled = False
            ring_bone_bol.enabled = False
            flip_bone_col.enabled = False
            extend_parent_col.enabled = False
            extend_children_col.enabled = False
            less_parent_col.enabled = False
            less_children_col.enabled = False
            more_col.enabled = False
            less_col.enabled = False


class TransferVgWeightPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_transfer_vg_weight"
    bl_label = "权重转移"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_model_modification"
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


class QuickOperationPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_quick_operation"
    bl_label = "快捷操作"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_model_modification"
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        operator_col = col.column(align=True)

        # 选择 物理骨骼 烘焙骨骼
        operator_row = operator_col.row(align=True)
        row1 = operator_row.row(align=True)
        row1.operator(MergeVerticesOperator.bl_idname, text=MergeVerticesOperator.bl_label, icon="AUTOMERGE_OFF")
        row2 = operator_row.row(align=True)
        if is_mmd_tools_enabled():
            row2.operator('mmd_tools.separate_by_materials', text='Separate by Materials', icon='MOD_EXPLODE')

            active_object = bpy.context.active_object
            if active_object:
                root = find_pmx_root_with_child(active_object)
                if root and active_object.type == 'MESH':
                    row2.enabled = True
                else:
                    row2.enabled = False
            else:
                row2.enabled = False
        else:
            row2.operator(DummyOperator.bl_idname, text='按材质分开', icon='MOD_EXPLODE')
            row2.enabled = False

        operator_row = operator_col.row(align=True)
        operator_row.operator(SetMatNameByObjNameOperator.bl_idname, text=SetMatNameByObjNameOperator.bl_label,
                              icon='GREASEPENCIL')
        operator_row.operator(SetObjNameByMatNameOperator.bl_idname, text=SetObjNameByMatNameOperator.bl_label,
                              icon='GREASEPENCIL')

        operator_row = operator_col.row(align=True)
        if is_mmd_tools_enabled():
            operator_row.operator(DetectOverlappingFacesOperator.bl_idname,
                                  text=DetectOverlappingFacesOperator.bl_label,
                                  icon='VIEWZOOM')
        else:
            operator_row.operator(DummyOperator.bl_idname, text=DetectOverlappingFacesOperator.bl_label,
                                  icon='VIEWZOOM')
            operator_row.enabled = False
        operator_row.operator(CleanSceneOperator.bl_idname, text=CleanSceneOperator.bl_label, icon='TRASH')


class PrePostProcessingPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_pre_post_processing"
    bl_label = "预处理 / 后处理"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 4

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
        remove_empty_col = col.column()
        remove_empty_col.prop(props, "remove_empty")

        show_batch_props(col, False, True, batch, FillSuffixChangeTexlocOperator)

        change_tex_loc_col = col.column()
        change_tex_loc_col.operator(ChangeTexLocOperator.bl_idname, text=ChangeTexLocOperator.bl_label)


class AddSsbPanel:
# class AddSsbPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_add_ssb"
    bl_label = "修复次标准骨骼"
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
        show_batch_props(box, True, True, batch, FillSuffixSsbOperator)
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
        show_batch_props(col, False, False, batch, FillSuffixRemoveUvMapOperator)

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

        fix_bone_name_flag_row = col.row()
        fix_bone_name_flag_row.prop(props, "fix_bone_name_flag")

        morph_panel_flag_col = col.column()
        morph_panel_flag_col.prop(props, "morph_panel_flag")

        fix_morph_name_flag_row = col.row()
        fix_morph_name_flag_row.prop(props, "fix_morph_name_flag")

        rigid_body_panel_flag_col = col.column()
        rigid_body_panel_flag_col.prop(props, "rigid_body_panel_flag")
        display_panel_flag_col = col.column()
        display_panel_flag_col.prop(props, "display_panel_flag")

        translation_flag_col = col.column()
        translation_flag_col.prop(props, "translation_flag")

        overwrite_flag_row = col.row()
        overwrite_flag_row.separator()
        overwrite_flag_row.separator()
        overwrite_flag_row.prop(props, "overwrite_flag")
        if props.translation_flag is False:
            overwrite_flag_row.enabled = False

        show_batch_props(col, False, True, batch, FillSuffixOrganizePanelOperator)

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

        batch_box = show_batch_props(col, True, True, batch, FillSuffixRenderPreviewOperator)
        if batch_box:
            force_center_col = batch_box.column()
            force_center_col.prop(props, "force_center")

        load_render_preset_row = col.row()
        load_render_preset_row.operator(LoadRenderPresetOperator.bl_idname, text=LoadRenderPresetOperator.bl_label)
        render_row = col.row()
        render_row.operator(GenPreviewCameraOperator.bl_idname, text=GenPreviewCameraOperator.bl_label)
        render_row.operator(RenderPreviewOperator.bl_idname, text=RenderPreviewOperator.bl_label)


class AboutPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_about"
    bl_label = "About"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 5
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene

        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator(
            "wm.url_open",
            text="用户文档",
            icon='URL'
        ).url = r"https://www.yuque.com/laibeikafeizaishuo/xgbdou/qtop1t7zzts9nzgv"

        row = col.row(align=True)
        row.operator(
            "wm.url_open",
            text="开源地址",
            icon='URL'
        ).url = r"https://github.com/kafeijk/mmd_kafei_tools/releases"

        row = col.row(align=True)
        row.label(
            text='Version: ' + str([addon.bl_info.get('version', (-1, -1, -1)) for addon in addon_utils.modules() if
                                    addon.bl_info['name'] == 'mmd_kafei_tools'][0]))


def show_batch_props(col, show_flag, create_box, batch, fill_suffix_operator=None):
    if show_flag:
        batch_col = col.column()
        batch_col.prop(batch, "flag")
        batch_flag = batch.flag
        if not batch_flag:
            return
    if create_box:
        batch_ui = col.box()
    else:
        batch_ui = col

    directory_col = batch_ui.column()
    directory_col.prop(batch, "directory")
    search_strategy_col = batch_ui.column()
    search_strategy_col.prop(batch, "search_strategy")
    threshold_col = batch_ui.column()
    threshold_col.prop(batch, "threshold")
    suffix_col = batch_ui.column()
    if fill_suffix_operator:
        suffix_row = suffix_col.row(align=True)
        suffix_row.prop(batch, "suffix")
        suffix_row.operator(fill_suffix_operator.bl_idname, text="", icon="FILE_REFRESH")
    else:
        suffix_col.prop(batch, "suffix")
    conflict_strategy_col = batch_ui.column()
    conflict_strategy_col.prop(batch, "conflict_strategy")
    return batch_ui


if __name__ == "__main__":
    bpy.utils.register_class(TransferPresetPanel)
