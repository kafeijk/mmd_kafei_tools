import bpy

from .batch_properties import BatchProperty


class RemoveUvMapProperty(bpy.types.PropertyGroup):

    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_remove_uv_map = bpy.props.PointerProperty(
            type=RemoveUvMapProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_remove_uv_map
