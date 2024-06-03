import bpy


class BatchProperty(bpy.types.PropertyGroup):
    flag: bpy.props.BoolProperty(
        name="批量",
        description="是否执行批量操作",
        default=False
    )
    directory: bpy.props.StringProperty(
        name="模型目录",
        description="模型所在目录（可跨越层级）",
        subtype='DIR_PATH',
        default=''
    )
    threshold: bpy.props.FloatProperty(
        name="阈值",
        description="需要排除的文件大小（单位kb），忽略体积小于该值的文件",
        default=0.0,
        min=0.0,
        max=1024 * 1024
    )
    suffix: bpy.props.StringProperty(
        name="名称后缀",
        description="在原有名称的基础上，添加的名称后缀，不填写则覆盖原文件",
        default='',
        maxlen=50,  # 防止用户随意输入
    )
