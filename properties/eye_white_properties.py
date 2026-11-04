import math

import bpy


class FixEyeWhiteProperty(bpy.types.PropertyGroup):
    eye_white: bpy.props.StringProperty(
        name="眼白",
        description="眼白对象名称，可用中英文逗号分隔多个名称",
        default=''
    )
    eye: bpy.props.StringProperty(
        name="眼睛",
        description="眼睛对象名称，可用中英文逗号分隔多个名称",
        default=''
    )
    show_sweep_params: bpy.props.BoolProperty(
        name="显示采样参数",
        description="勾选后显示具体采样参数",
        default=False,
    )
    sweep_limit: bpy.props.FloatProperty(
        name="横向采样区域",
        description="眼睛横向左右扫过的角度范围，输入值即正负范围",
        subtype='ANGLE',
        default=math.radians(30),
        min=0,
        max=math.radians(90),
    )
    sweep_limit_x: bpy.props.FloatProperty(
        name="竖向采样区域",
        description="眼白竖向上下扫过的角度范围，输入值即正负范围",
        subtype='ANGLE',
        default=math.radians(25),
        min=0,
        max=math.radians(90),
    )
    sweep_step: bpy.props.FloatProperty(
        name="采样步长",
        description="采样步长，值越小扫过区域越精细",
        subtype='ANGLE',
        default=math.radians(5),
        min=math.radians(1),
        max=math.radians(90),
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_fix_eye_white = bpy.props.PointerProperty(type=FixEyeWhiteProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_fix_eye_white
