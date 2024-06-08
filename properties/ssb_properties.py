import bpy

from .batch_properties import BatchProperty


class AddSsbProperty(bpy.types.PropertyGroup):
    model: bpy.props.PointerProperty(
        name="模型",
        description="MMD模型",
        type=bpy.types.Object
    )
    # 创建骨骼的时候需要考虑到mmd和blender之间的缩放，通常是0.08，即12.5
    # 但是这个缩放值并不会在blender中保存，所以无法得知用户导入模型时的具体数值
    # mmd插件导入时，scale参数是通过ImportHelper传递的，不清楚如何获取，就算能获取也无法处理多模型的情况，且该值不会被保存，再次打卡文件时丢失。
    # 所以这里提供一个scale参数让用户填写
    scale: bpy.props.FloatProperty(
        name="缩放",
        description="导入模型时的缩放倍数",
        default=0.08
    )
    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_add_ssb = bpy.props.PointerProperty(type=AddSsbProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_add_ssb
