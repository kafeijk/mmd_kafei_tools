import bpy

from .batch_properties import BatchProperty
from ..utils import is_module_installed


def get_optimization_flag():
    return is_module_installed("pypinyin")


class OrganizePanelProperty(bpy.types.PropertyGroup):
    bone_panel_flag: bpy.props.BoolProperty(
        name="骨骼面板",
        description="整理骨骼面板",
        default=True,
        update=lambda self, context: self.check_selection(context, "bone_panel_flag")
    )

    optimization_flag: bpy.props.BoolProperty(
        name="名称优化",
        description="优化骨骼日文名称，避免使用时出现乱码。该参数需安装pypinyin模块后生效，详见说明文档",
        default=get_optimization_flag()
    )
    morph_panel_flag: bpy.props.BoolProperty(
        name="表情面板",
        description="整理表情面板",
        default=True,
        update=lambda self, context: self.check_selection(context, "morph_panel_flag")
    )
    rigid_body_panel_flag: bpy.props.BoolProperty(
        name="刚体面板",
        description="整理刚体面板",
        default=True,
        update=lambda self, context: self.check_selection(context, "rigid_body_panel_flag")
    )
    display_panel_flag: bpy.props.BoolProperty(
        name="显示枠面板",
        description="整理显示枠面板",
        default=True,
        update=lambda self, context: self.check_selection(context, "display_panel_flag")
    )

    bone_flag: bpy.props.BoolProperty(
        name="骨骼",
        description="生成骨骼显示枠",
        default=True,
        update=lambda self, context: self.check_selection(context, "bone_flag")
    )
    exp_flag: bpy.props.BoolProperty(
        name="表情",
        description="生成表情显示枠",
        default=True,
        update=lambda self, context: self.check_selection(context, "exp_flag")
    )

    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_organize_panel = bpy.props.PointerProperty(
            type=OrganizePanelProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_organize_panel

    def check_selection(self, context, changed_property):
        """检查选项，如果都未选中则恢复原来的状态"""
        if not (self.bone_panel_flag or self.morph_panel_flag or self.rigid_body_panel_flag or self.display_panel_flag):
            if changed_property == "bone_panel_flag":
                self.bone_panel_flag = True
            elif changed_property == "morph_panel_flag":
                self.morph_panel_flag = True
            elif changed_property == "rigid_body_panel_flag":
                self.rigid_body_panel_flag = True
            elif changed_property == "display_panel_flag":
                self.display_panel_flag = True

        # 上级选项失效后，子级选项随之失效
        if changed_property == "display_panel_flag" and not self.display_panel_flag:
            self.bone_flag = False
            self.exp_flag = False
        elif changed_property == "display_panel_flag" and self.display_panel_flag:
            self.bone_flag = True
            self.exp_flag = True

        # 当display_panel_flag为True时，至少保证bone_flag子级选项有一个被勾选
        if changed_property == "bone_flag" or changed_property == "exp_flag":
            if not (self.bone_flag or self.exp_flag) and self.display_panel_flag:
                if changed_property == "bone_flag":
                    self.bone_flag = True
                elif changed_property == "exp_flag":
                    self.exp_flag = True

        # 上级选项失效后，子级选项随之失效
        if changed_property == "bone_panel_flag" and not self.bone_panel_flag:
            self.optimization_flag = False
