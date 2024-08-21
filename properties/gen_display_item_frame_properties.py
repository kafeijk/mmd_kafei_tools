import bpy

from .batch_properties import BatchProperty


class GenDisplayItemFrameProperty(bpy.types.PropertyGroup):
    bone_flag: bpy.props.BoolProperty(
        name="骨骼",
        description="生成骨骼显示枠",
        default=True,
        update=lambda self, context: self.check_selection(context, "bone_flag")
    )
    # 默认不勾选
    # 由于mmd插件在处理表情的时候，是按照表情类型而非表情组别处理的，所以最终顺序和原来顺序会有出入
    # 理想的执行顺序是先对表情面板重排序，然后再生成显示枠
    exp_flag: bpy.props.BoolProperty(
        name="表情",
        description="生成表情显示枠",
        default=False,
        update=lambda self, context: self.check_selection(context, "exp_flag")
    )

    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_gen_display_item_frame = bpy.props.PointerProperty(
            type=GenDisplayItemFrameProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_gen_display_item_frame

    def check_selection(self, context, changed_property):
        """检查选项，如果都未选中则恢复原来的状态"""
        if not (self.bone_flag or self.exp_flag):
            if changed_property == "bone_flag":
                self.bone_flag = True  # 强制保持bone_flag被选中
            else:
                self.exp_flag = True  # 强制保持exp_flag被选中
