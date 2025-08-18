import math

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


class LightSettingsProperty(bpy.types.PropertyGroup):
    target_type: bpy.props.EnumProperty(
        name="目标类型",
        description="灯光跟随目标的类型",
        items=[
            ("ARMATURE", "骨架", "骨架"),
            ("MESH", "网格", "网格")

        ],
        default="ARMATURE"
    )

    bone_name: bpy.props.StringProperty(
        name="骨骼",
        description="骨骼名称",
        default='頭'
    )

    vg_name: bpy.props.StringProperty(
        name="顶点组",
        description="顶点组名称",
        default='頭'
    )

    # ---------------------- 灯光参数 ----------------------
    main_distance: bpy.props.FloatProperty(
        name="主光距离",
        description="主光到目标的水平距离",
        subtype='DISTANCE',
        default=2,
        min=0.0
    )

    fill_distance: bpy.props.FloatProperty(
        name="辅光距离",
        description="辅光到目标的水平距离",
        subtype='DISTANCE',
        default=1.5,
        min=0.0
    )

    back_distance: bpy.props.FloatProperty(
        name="背光直线距离",
        description="背光到目标的直线距离",
        subtype='DISTANCE',
        default=1,
        min=0.0
    )

    main_position: bpy.props.EnumProperty(
        name="主光位置",
        description="主光位置",
        items=[
            ("LEFT", "左", "左"),
            ("RIGHT", "右", "右")

        ],
        default="RIGHT",
    )

    back_angle: bpy.props.FloatProperty(
        name="背光角度",
        description="背光的旋转角度",
        subtype="ANGLE",
        default=math.radians(-45)
    )


    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_light_settings = bpy.props.PointerProperty(type=LightSettingsProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_light_settings
