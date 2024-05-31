import bpy


class GenDisplayItemFrameProperty(bpy.types.PropertyGroup):
    batch: bpy.props.BoolProperty(
        name="批量",
        description="是否批量执行生成显示枠的操作",
        default=False
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
        description="在原有名称的基础上，添加的名称后缀",
        default=' 显示枠调整',
        maxlen=50,  # 防止用户随意输入
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_gen_display_item_frame = bpy.props.PointerProperty(
            type=GenDisplayItemFrameProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_gen_display_item_frame
