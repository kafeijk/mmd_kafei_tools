import bpy

from ..operaters.transfer_operators import TransferPmxToAbcOperator


class TransferPmxToAbcPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_transfer_pmx_to_abc"
    bl_label = "通用材质传递 pmx -> abc"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 0

    def draw(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_transfer_pmx_to_abc

        layout = self.layout
        multi_material_slots_row = layout.row()
        multi_material_slots_row.prop(props, "multi_material_slots_flag")

        vgs_row = layout.row()
        vgs_row.prop(props, "vgs_flag")

        modifiers_row = layout.row()
        modifiers_row.prop(props, "modifiers_flag")
        if props.modifiers_flag:
            vgs_row.enabled = False
        else:
            vgs_row.enabled = True

        row = layout.row()
        row.prop(props, "gen_skin_uv_flag")

        if props.gen_skin_uv_flag:
            row = layout.row()
            box = row.box()
            box.prop(props, "skin_uv_name")

        row = layout.row()
        row.prop(props, "toon_shading_flag")
        if props.toon_shading_flag:
            row = layout.row()
            box = row.box()
            box.prop(props, "face_locator")
            box.prop(props, "outline_width")

            multi_material_slots_row.enabled = False
            vgs_row.enabled = False
            modifiers_row.enabled = False
        else:
            multi_material_slots_row.enabled = True
            if props.modifiers_flag:
                vgs_row.enabled = False
            else:
                vgs_row.enabled = True
            modifiers_row.enabled = True

        row = layout.row()
        row.operator(TransferPmxToAbcOperator.bl_idname, text=TransferPmxToAbcOperator.bl_label)


class PrePostProcessingPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_pre_post_processing"
    bl_label = "预处理 / 后处理"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'  # N面板
    bl_category = 'KafeiTools'  # 追加到其它面板或独自一个面板
    bl_order = 2

    def draw(self, context):
        layout = self.layout


class PreviewPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_preview"
    bl_label = "渲染预览图"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="渲染预览图")


class TexturePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_texture"
    bl_label = "修改贴图位置"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="修改贴图位置")


class BonePositionPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_bone_position"
    bl_label = "修改骨骼亲子指向"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="修改骨骼亲子指向")


class BoneOrderPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_bone_order"
    bl_label = "修改骨骼面板顺序"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="修改骨骼面板顺序")


class DisplayItemFramePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_display_item_frame"
    bl_label = "生成显示枠"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_pre_post_processing"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="修改显示枠")


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


class ColorSpacePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_color_space"
    bl_label = "修改贴图色彩空间"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="修改贴图色彩空间")


class SubsurfacePanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_subsurface"
    bl_label = "修复皮肤发青问题"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="修复皮肤发青问题")


class BoneSelectionPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_bone_selection"
    bl_label = "选择指定骨骼"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="选择指定骨骼")


class VertexWeightTransferPanel(bpy.types.Panel):
    bl_idname = "KAFEI_PT_vertex_weight_transfer"
    bl_label = "权重转移"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "KAFEI_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="权重转移")


if __name__ == "__main__":
    bpy.utils.register_class(TransferPmxToAbcPanel)
