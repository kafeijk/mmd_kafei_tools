import bpy

from .batch_properties import BatchProperty


class PrePostProcessingProperty(bpy.types.PropertyGroup):
    change_tex_loc: bpy.props.BoolProperty(
        name="修改贴图路径",
        description="修改贴图路径",
        default=True,
        update=lambda self, context: self.ensure_one_selected("change_tex_loc")
    )
    remove_uv_map: bpy.props.BoolProperty(
        name="移除冗余UV",
        description="移除冗余UV",
        default=True,
        update=lambda self, context: self.ensure_one_selected("remove_uv_map")
    )
    organize_panel: bpy.props.BoolProperty(
        name="面板整理",
        description="整理面板",
        default=True,
        update=lambda self, context: self.ensure_one_selected("organize_panel")
    )

    # 面板展开状态（仅用于界面，不影响处理流程）
    change_tex_loc_expanded: bpy.props.BoolProperty(
        name="展开贴图路径参数",
        default=False
    )
    organize_panel_expanded: bpy.props.BoolProperty(
        name="展开面板整理参数",
        default=False
    )
    compatibility_expanded: bpy.props.BoolProperty(
        name="展开兼容优化参数",
        default=False
    )

    # 修改贴图路径
    new_folder: bpy.props.StringProperty(
        name="贴图文件夹名称",
        description="新贴图文件夹名称，区分大小写，忽略首尾空格",
        default='textures',
        maxlen=100
    )
    remove_empty: bpy.props.BoolProperty(
        name="删除空文件夹",
        description="贴图路径修改后，是否删除模型目录下空文件夹",
        default=True
    )
    texture_conflict_strategy: bpy.props.EnumProperty(
        name="贴图重名时",
        description="贴图文件夹存在同名文件时的处理方式",
        items=[
            ("AUTO", "自动覆盖或改名", "内容相同则合并，不同则按规则改名"),
            ("SKIP", "跳过", "存在同名文件时跳过该文件的处理"),
        ],
        default="AUTO"
    )
    keep_names: bpy.props.StringProperty(
        name="图像保留关键词",
        description="名称含保留关键词的图像不会被处理，可按中英文逗号分隔。\n可防止预览图等图像文件被误认为贴图文件被处理",
        default="preview,3view",
        maxlen=200
    )

    # 面板整理
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
        update=lambda self, context: self.ensure_one_selected("compatibility_flag")
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
        bpy.types.Scene.mmd_kafei_tools_pre_post_processing = bpy.props.PointerProperty(
            type=PrePostProcessingProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_pre_post_processing

    def ensure_one_selected(self, changed_property):
        """至少保留一项勾选：全部取消时恢复刚取消的项"""
        if not (self.change_tex_loc or self.remove_uv_map or self.organize_panel or self.compatibility_flag):
            setattr(self, changed_property, True)

    def check_selection(self, context, changed_property):
        """检查选项，如果都未选中则恢复原来的状态"""
        # 面板整理至少保留一项
        if not any((
                self.bone_panel_flag,
                self.morph_panel_flag,
                self.rigid_body_panel_flag,
                self.display_panel_flag,
                self.translation_flag,
        )):
            if changed_property in (
                    "bone_panel_flag",
                    "morph_panel_flag",
                    "rigid_body_panel_flag",
                    "display_panel_flag",
                    "translation_flag",
            ):
                setattr(self, changed_property, True)

        # 上级选项失效后，子级选项随之失效
        if changed_property == "translation_flag":
            self.overwrite_flag = self.translation_flag

        elif changed_property in (
                "fix_bone_name_flag",
                "fix_morph_name_flag",
                "fix_all_materials_flag",
                "fix_rigid_body_size_flag",
        ):
            # 兼容优化被勾选时，至少保留一个子项
            if self.compatibility_flag and not any((
                    self.fix_bone_name_flag,
                    self.fix_morph_name_flag,
                    self.fix_all_materials_flag,
                    self.fix_rigid_body_size_flag,
            )):
                setattr(self, changed_property, True)
