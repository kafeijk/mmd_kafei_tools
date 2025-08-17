import bpy


class RenderSettingsProperty(bpy.types.PropertyGroup):
    engine: bpy.props.EnumProperty(
        name="渲染引擎",
        description="用于渲染的引擎",
        items=[
            ("EEVEE", "EEVEE", "EEVEE"),
            ("CYCLES", "Cycles", "Cycles")

        ],
        default="EEVEE"
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_render_settings = bpy.props.PointerProperty(type=RenderSettingsProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_render_settings
