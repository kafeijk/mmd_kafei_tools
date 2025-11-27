from ..operaters.modify_specify_content_operators import ModifySpecifyContentOperator
from ..operaters.modify_specify_content_operators import ArrangeObjectOperator
from ..operaters.change_tex_loc_operators import ChangeTexLocOperator
from ..operaters.small_feature_operators import ModifyColorspaceOperator
from ..operaters.organize_panel_operators import OrganizePanelOperator
from ..operaters.remove_uv_map_operators import RemoveUvMapOperator
from ..operaters.render_preview_operators import GenPreviewCameraOperator
from ..operaters.scene_settings_operators import LoadRenderPresetOperator
from ..operaters.render_preview_operators import RenderPreviewOperator
from ..operaters.small_feature_operators import SmallFeatureOperator
from ..operaters.small_feature_operators import GroupObjectOperator
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
from ..operaters.scene_settings_operators import RenderSettingsOperator
from ..operaters.scene_settings_operators import WorldSettingsOperator
from ..operaters.scene_settings_operators import ResolutionSettingsOperator
from ..operaters.scene_settings_operators import SwapResolutionOperator
from ..operaters.scene_settings_operators import LightSettingsOperator
from ..operaters.scene_settings_operators import CameraSettingsOperator
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

        col.prop(props, "direction")
        param_box = col.box()
        param_col = param_box.column()

        direction = props.direction
        if direction in ['PMX2ABC', 'PMX2PMX']:
            if direction == 'PMX2ABC':
                param_col.prop(props, "source_pmx2abc")
            else:
                param_col.prop(props, "source")
                param_col.prop(props, "target")

            transfer_param_col = param_col.column()
            transfer_param_col.prop(props, "material_flag")
            transfer_param_col.prop(props, "uv_flag")
            transfer_param_col.prop(props, "vgs_flag")
            transfer_param_col.prop(props, "modifiers_flag")

            if direction == 'PMX2ABC':
                transfer_param_col.prop(props, "normal_flag")

                param_col.prop(props, "toon_shading_flag")
                if props.toon_shading_flag:
                    toon_shading_box = param_col.box()
                    toon_shading_col = toon_shading_box.column()

                    toon_shading_col.prop(props, "face_locator")
                    toon_shading_col.prop(props, "auto_face_location")

                    if not props.auto_face_location:
                        face_object_box = toon_shading_col.box()
                        face_object_col = face_object_box.column()

                        face_object_col.prop(props, "face_object")
                        face_object_col.prop(props, "face_vg", icon='GROUP_VERTEX')

                    toon_shading_col.prop(props, "force")

                    transfer_param_col.enabled = False
                else:
                    transfer_param_col.enabled = True
            else:
                param_col.prop(props, "tolerance")
        else:
            param_col.prop(props, "abc_filepath")
            param_col.prop(props, "selected_only")
        col.operator(TransferPresetOperator.bl_idname, text=TransferPresetOperator.bl_label)


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
        props = scene.mmd_kafei_tools_output_settings
        rd = context.scene.render

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        row = col.row(align=True)
        props_col = row.column(align=True)
        button_col = row.column(align=True)
        button_col.scale_x = 0.3

        # 分辨率
        props_col.prop(props, "resolution", text="Resolution")
        props_col.prop(rd, "resolution_x", text="X")
        props_col.prop(rd, "resolution_y", text="Y")
        button_col.operator(ResolutionSettingsOperator.bl_idname, text="", icon="TRIA_RIGHT")
        button_col.operator(SwapResolutionOperator.bl_idname, text="⇅", emboss=True)

        # 帧率
        props_col.separator()
        frame_col = props_col.column(heading="Frame Rate")
        if bpy.types.RENDER_PT_format._preset_class is None:
            bpy.types.RENDER_PT_format._preset_class = bpy.types.RENDER_MT_framerate_presets
        args = rd.fps, rd.fps_base, bpy.types.RENDER_PT_format._preset_class.bl_label
        fps_label_text, show_framerate = bpy.types.RENDER_PT_format._draw_framerate_label(*args)
        frame_col.menu("RENDER_MT_framerate_presets", text=fps_label_text)
        if show_framerate:
            custom_fps_col = frame_col.column(align=True)
            custom_fps_col.prop(rd, "fps")
            custom_fps_col.prop(rd, "fps_base", text="Base")

        # 输出文件格式
        props_col.separator()
        image_settings = rd.image_settings
        props_col.template_image_settings(image_settings, color_management=False)


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

        col.prop(props, "target_type")
        target_type = props.target_type
        if target_type == "ARMATURE":
            col.prop(props, "bone_name", icon='BONE_DATA')
        elif target_type == "MESH":
            col.prop(props, "vg_name", icon='GROUP_VERTEX')

        col.prop(props, "preset")
        col.prop(props, "preset_flag")
        col.prop(props, "main_distance")
        col.prop(props, "fill_distance")
        col.prop(props, "main_position")
        col.prop(props, "back_distance")
        col.prop(props, "back_angle")

        col.operator(LightSettingsOperator.bl_idname, text=LightSettingsOperator.bl_label)


class CameraSettingsPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_camera_settings"
    bl_label = "相机设置"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_scene_settings"
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_camera_settings

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()

        col.prop(props, "target_type")
        target_type = props.target_type
        if target_type == "ARMATURE":
            col.prop(props, "bone_name", icon='BONE_DATA')
        elif target_type == "MESH":
            col.prop(props, "vg_name", icon='GROUP_VERTEX')
            frame_col = col.column(align=True)
            frame_col.prop(scene, "frame_start", text="起始帧")
            frame_col.prop(scene, "frame_end", text="结束帧")

        col.prop(props, "rotation_euler_x")

        threshold_col = col.column(align=True)
        threshold_col.prop(props, "threshold_x")
        threshold_col.prop(props, "threshold_y")
        threshold_col.prop(props, "threshold_z")

        col.prop(props, "max_gap")

        col.operator(CameraSettingsOperator.bl_idname, text=CameraSettingsOperator.bl_label)


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
        props2 = scene.mmd_kafei_tools_modify_colorspace
        props3 = scene.mmd_kafei_tools_group_object

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()

        col.prop(props, "option")

        option = props.option
        if option == "MODIFY_COLORSPACE":
            source_colorspace_col = col.column()
            source_colorspace_col.prop(props2, "source_colorspace")
            keywords = props2.keywords
            if keywords:
                source_colorspace_col.enabled = False
            else:
                source_colorspace_col.enabled = True

            col.prop(props2, "target_colorspace")
            col.prop(props2, "keywords", icon="FILE_IMAGE")
            col.operator(ModifyColorspaceOperator.bl_idname, text=ModifyColorspaceOperator.bl_label)
        elif option == "GROUP_OBJECT":
            col.prop(props3, "scope")
            col.prop(props3, "search_type")
            search_type = props3.search_type
            if search_type == "NODE_NAME":
                col.prop(props3, "node_keywords", icon="NODE")
            else:
                col.prop(props3, "img_keywords", icon="FILE_IMAGE")
            col.prop(props3, "recursive")
            col.operator(GroupObjectOperator.bl_idname, text=GroupObjectOperator.bl_label)

        else:
            col.operator(SmallFeatureOperator.bl_idname, text=SmallFeatureOperator.bl_label)


class ToolsPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_tools"
    bl_label = "工具"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

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

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()

        col.prop(props, "content_type")
        content_type = props.content_type
        if content_type == 'ADD_UV_MAP':
            col.prop(props, "uv_name", icon="GROUP_UVS")
            col.prop(props, "average_islands_flag")
        elif content_type == 'ADD_COLOR_ATTRIBUTE':
            col.prop(props, "color_attribute_name", icon="GROUP_VCOL")
            col.prop(props, "color")
        elif content_type == 'REMOVE_UV_MAP':
            col.prop(props, "keep_first")
        elif content_type == 'REMOVE_COLOR_ATTRIBUTE':
            col.prop(props, "keep_first")
        elif content_type == 'REMOVE_MATERIAL':
            col.prop(props, "create_default")
        elif content_type in ['REMOVE_MODIFIER', 'REMOVE_CONSTRAINT']:
            col.prop(props, "keep_first")
        elif content_type == 'REMOVE_VERTEX_GROUP':
            col.prop(props, "keep_locked")
        elif content_type == 'REMOVE_SHAPE_KEY':
            col.prop(props, "keep_current")

        col.operator(ModifySpecifyContentOperator.bl_idname, text=ModifySpecifyContentOperator.bl_label)


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
            start_trans_col = col.column(align=True)
            start_trans_col.prop(props, "start_trans", index=0, text="起始 X")
            direction = props.direction
            if direction == "HORIZONTAL":
                start_trans_col.prop(props, "start_trans", index=1, text="Y")
            else:
                start_trans_col.prop(props, "start_trans", index=2, text="Z")

            spacing_col = col.column(align=True)
            spacing_col.prop(props, "spacing", index=0, text="间距 X")
            if direction == "HORIZONTAL":
                spacing_col.prop(props, "spacing", index=1, text="Y")
            else:
                spacing_col.prop(props, "spacing", index=2, text="Z")

            col.prop(props, "num_per_row")
            col.prop(props, "threshold")
        elif arrangement_type in ["ARC", "CIRCLE"]:
            col.prop(props, "radius")
            col.prop(props, "num_per_circle")
            col.prop(props, "spacing_circle")
            col.prop(props, "offset")
            col.prop(props, "threshold")

        col.operator(ArrangeObjectOperator.bl_idname, text=ArrangeObjectOperator.bl_label)


class ModelModificationPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_model_modification"
    bl_label = "模型修改"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

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

        col.prop(props, "h_joint_strategy")
        col.prop(props, "force_apply")

        col = col.column(align=True)
        row = col.row(align=True)
        row.operator(ChangeRestPoseStartOperator.bl_idname, text=ChangeRestPoseStartOperator.bl_label)
        row.operator(ChangeRestPoseEndOperator.bl_idname, text=ChangeRestPoseEndOperator.bl_label)
        row = col.row(align=True)
        row.operator(ChangeRestPoseEnd2Operator.bl_idname, text=ChangeRestPoseEnd2Operator.bl_label)


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

        col.prop(props, "source_vg_name", icon='GROUP_VERTEX')
        col.prop(props, "target_vg_name", icon='GROUP_VERTEX')
        col.prop(props, "selected_v_only")

        col.operator(TransferVgWeightOperator.bl_idname, text=TransferVgWeightOperator.bl_label)


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
        operator_row = operator_col.row(align=True)
        mmd_row = operator_row.row(align=True)
        if is_mmd_tools_enabled():
            mmd_row.operator('mmd_tools.import_model', text='Import', icon='OUTLINER_OB_ARMATURE')
            mmd_row.operator('mmd_tools.export_pmx', text='Export', icon='OUTLINER_OB_ARMATURE')
        else:
            mmd_row.operator(DummyOperator.bl_idname, text='Import', icon='OUTLINER_OB_ARMATURE')
            mmd_row.operator(DummyOperator.bl_idname, text='Export', icon='OUTLINER_OB_ARMATURE')
            mmd_row.enabled = False

        operator_row = operator_col.row(align=True)
        mmd_row = operator_row.row(align=True)
        if is_mmd_tools_enabled():
            mmd_row.operator('mmd_tools.convert_materials', text='Convert to Blender', icon='BLENDER')
        else:
            mmd_row.operator(DummyOperator.bl_idname, text='Convert to Blender', icon='BLENDER')
            mmd_row.enabled = False

        mmd_row2 = operator_row.row(align=True)
        if is_mmd_tools_enabled():
            mmd_row2.operator('mmd_tools.separate_by_materials', text='Separate by Materials', icon='MOD_EXPLODE')

            active_object = bpy.context.active_object
            if active_object:
                root = find_pmx_root_with_child(active_object)
                if root and active_object.type == 'MESH':
                    mmd_row2.enabled = True
                else:
                    mmd_row2.enabled = False
            else:
                mmd_row2.enabled = False
        else:
            mmd_row2.operator(DummyOperator.bl_idname, text='Separate by Materials', icon='MOD_EXPLODE')
            mmd_row2.enabled = False

        operator_row = operator_col.row(align=True)
        row = operator_row.row(align=True)
        row.operator(MergeVerticesOperator.bl_idname, text=MergeVerticesOperator.bl_label, icon="AUTOMERGE_OFF")
        mmd_row = operator_row.row(align=True)
        if is_mmd_tools_enabled():
            mmd_row.operator(DetectOverlappingFacesOperator.bl_idname,
                             text=DetectOverlappingFacesOperator.bl_label,
                             icon='VIEWZOOM')
        else:
            mmd_row.operator(DummyOperator.bl_idname, text=DetectOverlappingFacesOperator.bl_label,
                             icon='VIEWZOOM')
            mmd_row.enabled = False

        row = operator_col.row(align=True)
        row.operator(SetMatNameByObjNameOperator.bl_idname, text=SetMatNameByObjNameOperator.bl_label,
                     icon='GREASEPENCIL')
        row.operator(SetObjNameByMatNameOperator.bl_idname, text=SetObjNameByMatNameOperator.bl_label,
                     icon='GREASEPENCIL')

        row = operator_col.row(align=True)
        row.operator(CleanSceneOperator.bl_idname, text=CleanSceneOperator.bl_label, icon='TRASH')


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

        col.prop(props, "new_folder")
        col.prop(props, "remove_empty")

        show_batch_props(col, False, True, batch, FillSuffixChangeTexlocOperator)

        col.operator(ChangeTexLocOperator.bl_idname, text=ChangeTexLocOperator.bl_label)


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

        col.operator(RemoveUvMapOperator.bl_idname, text=RemoveUvMapOperator.bl_label)


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
        col.prop(props, "bone_panel_flag")
        col.prop(props, "morph_panel_flag")
        col.prop(props, "rigid_body_panel_flag")
        col.prop(props, "display_panel_flag")
        col.prop(props, "translation_flag")

        overwrite_flag_row = col.row()
        overwrite_flag_row.separator()
        overwrite_flag_row.separator()
        overwrite_flag_row.prop(props, "overwrite_flag")
        if props.translation_flag is False:
            overwrite_flag_row.enabled = False

        col.prop(props, "compatibility_flag")
        compatibility_flag_row = col.row()
        compatibility_flag_row.separator()
        compatibility_flag_row.separator()
        compatibility_flag_col = compatibility_flag_row.column()
        compatibility_flag_col.prop(props, "fix_bone_name_flag")
        compatibility_flag_col.prop(props, "fix_morph_name_flag")
        compatibility_flag_col.prop(props, "fix_all_materials_flag")
        compatibility_flag_col.prop(props, "fix_rigid_body_size_flag")
        if props.compatibility_flag is False:
            compatibility_flag_col.enabled = False

        show_batch_props(col, False, True, batch, FillSuffixOrganizePanelOperator)

        col.operator(OrganizePanelOperator.bl_idname, text=OrganizePanelOperator.bl_label)


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

        col.prop(props, "type")
        col.prop(props, "scale")

        rotation_col = col.column(align=True)
        rotation_col.prop(props, "rotation_euler_x")
        rotation_col_y = rotation_col.column(align=True)
        rotation_col_y.prop(props, "rotation_euler_y")
        rotation_col_y.enabled = not align
        rotation_col.prop(props, "rotation_euler_z")

        col.prop(props, "auto_follow")
        if props.auto_follow:
            bpy.context.space_data.lock_camera = True
        col.prop(props, "align")

        batch_ui = show_batch_props(col, True, True, batch, FillSuffixRenderPreviewOperator)

        if batch_ui:
            batch_ui.prop(props, "force_center")

        col = col.column(align=True)
        load_render_preset_row = col.row(align=True)
        load_render_preset_row.operator(LoadRenderPresetOperator.bl_idname, text=LoadRenderPresetOperator.bl_label)
        render_row = col.row(align=True)
        render_row.operator(GenPreviewCameraOperator.bl_idname, text=GenPreviewCameraOperator.bl_label)
        if batch.flag:
            render_row.operator(RenderPreviewOperator.bl_idname, text="批量渲染")
        else:
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
        props = scene.mmd_kafei_tools_developer_extras

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column(align=True)

        col.operator(
            "wm.url_open",
            text="用户文档",
            icon='URL'
        ).url = r"https://www.yuque.com/laibeikafeizaishuo/xgbdou/qtop1t7zzts9nzgv"

        col.operator(
            "wm.url_open",
            text="开源地址",
            icon='URL'
        ).url = r"https://github.com/kafeijk/mmd_kafei_tools/releases"

        # 版本号
        row = col.row(align=True)
        row.label(
            text='Version: ' + str([addon.bl_info.get('version', (-1, -1, -1)) for addon in addon_utils.modules() if
                                    addon.bl_info['name'] == 'mmd_kafei_tools'][0]))

        # 开发者选项开关
        icon = 'HIDE_ON' if not props.flag else 'HIDE_OFF'
        row.prop(props, "flag", text="", icon=icon, emboss=False)

        # 语言选择
        if props.flag:
            row = col.row(align=True)
            row.prop(props, "language", expand=True)


def show_batch_props(col, show_flag, create_box, batch, fill_suffix_operator=None):
    if show_flag:
        col.prop(batch, "flag")
        if not batch.flag:
            return
    if create_box:
        batch_box = col.box()
        batch_ui = batch_box.column()
    else:
        batch_ui = col

    batch_ui.prop(batch, "directory")
    batch_ui.prop(batch, "search_strategy")
    batch_ui.prop(batch, "threshold")
    if fill_suffix_operator:
        suffix_row = batch_ui.row(align=True)
        suffix_row.prop(batch, "suffix")
        suffix_row.operator(fill_suffix_operator.bl_idname, text="", icon="FILE_REFRESH")
    else:
        suffix_row = batch_ui.row(align=True)
        suffix_row.prop(batch, "suffix")
    batch_ui.prop(batch, "conflict_strategy")
    return batch_ui


if __name__ == "__main__":
    bpy.utils.register_class(TransferPresetPanel)
