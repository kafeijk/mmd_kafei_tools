import bpy

from .batch_properties import BatchProperty


class GenDisplayItemFrameProperty(bpy.types.PropertyGroup):
    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_gen_display_item_frame = bpy.props.PointerProperty(
            type=GenDisplayItemFrameProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_gen_display_item_frame
