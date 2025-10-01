import bpy

from ..utils import safe_set


class DeveloperExtrasProperty(bpy.types.PropertyGroup):
    flag: bpy.props.BoolProperty(
        name="Developer Extras",
        description="Developer Extras",
        default=False
    )

    language: bpy.props.EnumProperty(
        name="Language",
        description="Language",
        items=[
            ("zh_HANS", "Chinese (Simplified) - 简体中文", "Chinese (Simplified) - 简体中文"),
            ("en_GB", "English", "English"),
            ("ja_JP", "Japanese", "Japanese"),
        ],
        update=lambda self, context: self.update_preset(context)
    )

    def update_preset(self, context):
        # 界面语言设置
        prefs = context.preferences

        if self.language == "zh_HANS":
            safe_set(prefs.view, "language", "zh_CN")
        elif self.language == "en_GB":
            safe_set(prefs.view, "language", "en_US")

        safe_set(prefs.view, "language", self.language)
        safe_set(prefs.view, "use_translate_tooltips", True)
        safe_set(prefs.view, "use_translate_interface", True)
        safe_set(prefs.view, "use_translate_reports", True)
        safe_set(prefs.view, "use_translate_new_dataname", False)


    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_developer_extras = bpy.props.PointerProperty(type=DeveloperExtrasProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_developer_extras
