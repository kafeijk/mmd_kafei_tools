import bpy

from .batch_properties import BatchProperty


class ChangeTexLocProperty(bpy.types.PropertyGroup):
    new_folder: bpy.props.StringProperty(
        name="贴图文件夹名称",
        description="新贴图文件夹名称，区分大小写，忽略空格",
        default='texture',
        maxlen=100
    )
    batch: bpy.props.PointerProperty(type=BatchProperty)
    remove_empty: bpy.props.BoolProperty(
        name="删除空文件夹",
        description="贴图路径修改后，是否删除pmx目录下空文件夹（不含递归）",
        default=True
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_change_tex_loc = bpy.props.PointerProperty(type=ChangeTexLocProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_change_tex_loc
