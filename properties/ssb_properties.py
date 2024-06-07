import bpy

from .batch_properties import BatchProperty


class AddSsbProperty(bpy.types.PropertyGroup):
    model: bpy.props.PointerProperty(
        name="模型",
        description="MMD模型",
        type=bpy.types.Object
    )
    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_add_ssb = bpy.props.PointerProperty(type=AddSsbProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_add_ssb
