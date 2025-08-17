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


class OutputSettingsProperty(bpy.types.PropertyGroup):
    resolution: bpy.props.EnumProperty(
        name="分辨率",
        description="视频分辨率",
        items=[
            ("1080P", "1080p", "1920x1080"),
            ("2K", "2K", "2560x1440"),
            ("4K", "4K", "3840x2160"),
            ("360P", "360p", "640x360"),
            ("480P", "480p", "854x480"),
            ("540P", "540p", "960x540"),
            ("720P", "720p", "1280x720"),
            ("8K", "8K", "7680x4320"),
        ],
        default="1080P"
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_output_settings = bpy.props.PointerProperty(type=OutputSettingsProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_output_settings

