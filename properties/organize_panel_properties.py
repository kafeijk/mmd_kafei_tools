import bpy

from .batch_properties import BatchProperty


class OrganizePanelProperty(bpy.types.PropertyGroup):
    bone_panel_flag: bpy.props.BoolProperty(
        name="骨骼面板",
        description="整理骨骼面板",
        default=True,
        update=lambda self, context: self.check_selection(context, "bone_panel_flag")
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

    translation_flag: bpy.props.BoolProperty(
        name="面板翻译",
        description="为面板中的项目（骨骼、表情、显示枠）设置有限且紧凑的英文名称，以增强在MMD本体英文模式中模型操作的能力",
        default=True,
        update=lambda self, context: self.check_selection(context, "translation_flag")
    )

    overwrite_flag: bpy.props.BoolProperty(
        name="覆盖",
        description="如果面板项目已经存在英文名称，则覆盖原有名称",
        default=True,
        update=lambda self, context: self.check_selection(context, "overwrite_flag")
    )

    compatibility_flag: bpy.props.BoolProperty(
        name="兼容优化",
        description="兼容优化，解决MMD模型在MikuMikuDance与Blender之间的差异",
        default=True,
        update=lambda self, context: self.check_selection(context, "compatibility_flag")
    )

    fix_bone_name_flag: bpy.props.BoolProperty(
        name="骨骼名称修复",
        description="修复骨骼日文名称，避免使用时出现乱码及名称过长的情况",
        default=True,
        update=lambda self, context: self.check_selection(context, "fix_bone_name_flag")
    )

    fix_morph_name_flag: bpy.props.BoolProperty(
        name="表情名称修复",
        description="修复表情日文名称，避免使用时出现乱码及名称过长的情况",
        default=True,
        update=lambda self, context: self.check_selection(context, "fix_morph_name_flag")
    )

    fix_all_materials_flag: bpy.props.BoolProperty(
        name="表情兼容处理",
        description="移除范围为“全材質”的材质表情，避免装配变形引发的性能问题",
        default=True,
        update=lambda self, context: self.check_selection(context, "fix_all_materials_flag")
    )

    fix_rigid_body_size_flag: bpy.props.BoolProperty(
        name="刚体兼容处理",
        description="检测尺寸为0的受物理影响的刚体并设置默认值0.1，避免物理烘焙因尺寸为0出现异常",
        default=True,
        update=lambda self, context: self.check_selection(context, "fix_rigid_body_size_flag")
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
        if not any((
                self.bone_panel_flag,
                self.morph_panel_flag,
                self.rigid_body_panel_flag,
                self.display_panel_flag,
                self.translation_flag,
                self.compatibility_flag,
        )):
            if hasattr(self, changed_property):
                setattr(self, changed_property, True)

        # 上级选项失效后，子级选项随之失效
        if changed_property == "translation_flag":
            self.overwrite_flag = self.translation_flag

        elif changed_property == "compatibility_flag":
            state = self.compatibility_flag
            self.fix_bone_name_flag = state
            self.fix_morph_name_flag = state
            self.fix_all_materials_flag = state
            self.fix_rigid_body_size_flag = state
