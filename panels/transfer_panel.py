import bpy


class PresetTransferPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_preset_transfer"
    bl_label = "预设转移"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MMD'

    def draw(self, context):
        layout = self.layout

        layout.label(text="小二5.0预设转移 pmx -> abc:")
        layout.prop(context.scene, "outline_width")
        layout.operator("transfer.preset_xiaoer", text="转移")

        layout.label(text="根据关键词修改贴图色彩空间:")
        layout.prop(context.scene, "image_keyword_list_str")
        layout.prop(context.scene, "colorspace")
        layout.operator("transfer.modify_image_colorspace", text="修改色彩空间")

        layout.label(text="修改调色节点组色相/饱和度/明度:")
        layout.prop(context.scene, "hue")
        layout.prop(context.scene, "saturation")
        layout.prop(context.scene, "value")
        layout.operator("transfer.modify_hue_sat", text="修改HSV")
