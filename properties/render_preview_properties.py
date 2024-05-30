import math

import bpy
from mathutils import Euler


class RenderPreviewProperties(bpy.types.PropertyGroup):
    # todo 相机角度预设暂时连接到说明文档上面，这里暂不提供相关功能
    type: bpy.props.EnumProperty(
        name="类型",
        description="类型",
        items=[
            ("PERSPECTIVE", "透视", "透视"),
            ("ORTHOGRAPHIC", "正交", "正交")

        ],
        default="PERSPECTIVE"

    )
    scale: bpy.props.FloatProperty(
        name="边距",
        description="对齐物体后，视野/正交比例的倍数",
        default=1.0,
        min=1.0,
        max=2.0
    )
    rotation: bpy.props.FloatVectorProperty(
        name="相机旋转",
        description="相机旋转角度",
        subtype="EULER",
        default=Euler((math.radians(90), 0, 0), 'XYZ')
    )
    batch: bpy.props.BoolProperty(
        name="批量",
        description="是否批量执行渲染缩略图的操作",
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
        description="需要排除的pmx文件大小（单位kb），体积小于该值的文件不会被渲染",
        default=0.0,
        min=0.0
    )
    suffix: bpy.props.StringProperty(
        name="预览图名称后缀",
        description="在原有名称的基础上，添加的名称后缀，忽略空格",
        default='_preview',
        maxlen=50,  # 防止用户随意输入
    )
    force_center: bpy.props.BoolProperty(
        name="强制居中",
        description="受隐藏部位的影响，某些角色渲染的结果可能不会居中。此选项可使角色强制居中，但会花费更多的时间",
        default=False
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_render_preview = bpy.props.PointerProperty(type=RenderPreviewProperties)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_render_preview
