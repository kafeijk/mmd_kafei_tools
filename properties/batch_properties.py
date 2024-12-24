import bpy


class BatchProperty(bpy.types.PropertyGroup):
    flag: bpy.props.BoolProperty(
        name="批量",
        description="是否执行批量操作",
        default=False
    )
    directory: bpy.props.StringProperty(
        name="模型目录",
        description="模型文件所在目录（可跨越层级）",
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
        description="在源文件名的基础上，为输出文件添加的名称后缀",
        default='',
        maxlen=50,  # 防止用户随意输入
    )
    search_strategy: bpy.props.EnumProperty(
        name="检索模式",
        description="如果检索到多个符合条件的文件，应该如何处理",
        items=[
            ("LATEST", "最新", "获取修改日期最新的文件"),
            ("ALL", "全部", "获取所有文件")],
        default="LATEST"
    )
    conflict_strategy: bpy.props.EnumProperty(
        name="冲突时",
        description="如果目录中已存在具有指定名称后缀的同名文件，应该如何处理",
        items=[
            ("SKIP", "不处理", "跳过对这些文件的后续处理"),
            ("OVERWRITE", "覆盖", "继续对这些文件进行后续处理，产生的新文件会覆盖原文件")],
        default="SKIP"
    )
