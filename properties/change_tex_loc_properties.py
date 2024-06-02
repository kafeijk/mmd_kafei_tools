import bpy


class ChangeTexLocProperty(bpy.types.PropertyGroup):
    new_folder: bpy.props.StringProperty(
        name="贴图文件夹名称",
        description="新贴图文件夹名称，区分大小写，忽略空格",
        default='texture'
    )
    batch: bpy.props.BoolProperty(
        name="批量",
        description="是否批量执行修改贴图位置的操作",
        default=True
    )
    directory: bpy.props.StringProperty(
        name="模型目录",
        description="pmx模型所在目录（可跨越层级）",
        subtype='DIR_PATH',
        default=''
    )
    threshold: bpy.props.FloatProperty(
        name="文件大小阈值",
        description="需要排除的pmx文件大小（单位kb），忽略体积小于该值的文件",
        default=0.0,
        min=0.0
    )
    suffix: bpy.props.StringProperty(
        name="名称后缀",
        description="在原有名称的基础上，添加的名称后缀，不填写则覆盖原文件",
        default=' 贴图路径调整',
        maxlen=50,  # 防止用户随意输入
    )
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
