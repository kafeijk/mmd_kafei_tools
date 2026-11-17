import math

import bpy
from bpy.app.handlers import persistent
from .batch_properties import BatchProperty


@persistent
def update_rotation(scene, depsgraph):
    active_camera = scene.camera
    props = scene.mmd_kafei_tools_render_preview
    if not props.auto_follow or not active_camera:
        return
    # 暂时仅支持xyz1
    rotation_euler_x = active_camera.rotation_euler[0]
    rotation_euler_y = active_camera.rotation_euler[1]
    rotation_euler_z = active_camera.rotation_euler[2]
    # 仅在数值变化时写入，避免每次依赖图更新都触发属性写入和重绘
    if props.rotation_euler_x != rotation_euler_x:
        props.rotation_euler_x = rotation_euler_x
    if props.rotation_euler_y != rotation_euler_y:
        props.rotation_euler_y = rotation_euler_y
    if props.rotation_euler_z != rotation_euler_z:
        props.rotation_euler_z = rotation_euler_z


def update_auto_follow(self, context):
    """开启“自动”时锁定摄像机到视图方位；关闭时不解除"""
    if not self.auto_follow:
        return
    space_data = context.space_data
    if space_data and space_data.type == 'VIEW_3D':
        space_data.lock_camera = True


class RenderPreviewProperty(bpy.types.PropertyGroup):
    type: bpy.props.EnumProperty(
        name="类型",
        description="预览相机的类型",
        items=[
            ("PERSPECTIVE", "透视", "透视"),
            ("ORTHOGRAPHIC", "正交", "正交")

        ],
        default="PERSPECTIVE",
        update = lambda self, context: self.update_rotation_x(context)

    )
    scale: bpy.props.FloatProperty(
        name="边距",
        description="模型主体与预览图边界之间的留白程度，边距为n时，角色的宽度和高度约占画面尺寸的1/n",
        default=1.0,
        min=0.25,
        max=2.0
    )
    rotation_euler_x: bpy.props.FloatProperty(
        name="旋转 X",
        description="欧拉旋转",
        subtype="ANGLE",
        default=math.radians(80)
    )
    rotation_euler_y: bpy.props.FloatProperty(
        name="Y",
        description="欧拉旋转",
        subtype="ANGLE",
        default=math.radians(0)
    )
    rotation_euler_z: bpy.props.FloatProperty(
        name="Z",
        description="欧拉旋转",
        subtype="ANGLE",
        default=math.radians(0)
    )
    auto_follow: bpy.props.BoolProperty(
        name="自动",
        description="相机旋转值跟随活动相机视角",
        default=False,
        update=update_auto_follow
    )
    visible_only: bpy.props.BoolProperty(
        name="仅可见网格",
        description="排除隐藏部位的干扰，使模型尽可能居中",
        default=True,
    )
    # 如何在其它视角对齐角色？
    # 方案1
    # 添加shift_x，shift_y
    # 模型放大缩小，对镜头XY移位的结果不会产生影响
    # XY移位并不是XY方向移动相机，应提供最大最小值来控制范围
    # 焦距和XY移位的先后顺序，对结果不会产生影响，但是XY移位和镜头对准选中物体的顺序会对结果造成影响
    # 每个角色的XY移位都不可控，无法统一适用
    # 方案2
    # 为相机添加锁定追踪，目标是一个隐藏的临时圆柱，跟随轴-z，锁定轴y，对齐前先关闭约束，对齐后开启约束
    # 优点是能够对准角色，可以统一适用
    # 但是这个过程会微调相机的旋转，这会给用户带来困惑
    # 方案3
    # 为相机添加限定位置约束，让相机的局部x的最小最大值都为0
    # 优点是能够对准角色，所有角色可以统一适用，且拥有统一的旋转角度
    # 但是用户不能调整相机y旋转值，否则无法对齐角色
    # 考虑到实际使用场景，提供一个参数控制该功能的开启与否，默认情况下，是开启的
    # 开启后可以解决角色不居中的问题（不含隐藏物体的情况下），不开启可解决y旋转无法调节的问题，测试发现，后者一般不需要考虑居中问题
    # 方案4
    # 通过向量计算来获取z轴和视角中心的偏差（模拟测量工具），然后在相机视图坐标下移动偏差值的距离使视角中心对齐z轴（未实现）
    # 该目的可由方案3的约束实现，且同样无法调节相机y旋转
    batch: bpy.props.PointerProperty(type=BatchProperty)

    def update_rotation_x(self, context):
        if self.rotation_euler_y != math.radians(0) or self.rotation_euler_z != math.radians(0):
            return
        if self.type == "PERSPECTIVE":
            self.rotation_euler_x = math.radians(80)
        if self.type == "ORTHOGRAPHIC":
            self.rotation_euler_x = math.radians(90)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_render_preview = bpy.props.PointerProperty(type=RenderPreviewProperty)
        bpy.app.handlers.depsgraph_update_post.append(update_rotation)

    @staticmethod
    def unregister():
        bpy.app.handlers.depsgraph_update_post.remove(update_rotation)
        del bpy.types.Scene.mmd_kafei_tools_render_preview


class RenderThreeViewProperty(bpy.types.PropertyGroup):
    closeup_scale: bpy.props.FloatProperty(
        name="特写比例",
        description="近身特写占画面宽度的比例，0 表示不渲染特写，1 表示只渲染特写",
        default=0.25,
        min=0.0,
        max=1.0,
    )
    arm_angle: bpy.props.EnumProperty(
        name="手臂姿态",
        description="手臂姿态：自动取不穿模的最大内旋角度，T-Pose 摆成 T 字姿态，静置则保持绑定姿态",
        items=[
            ("AUTO", "自动", "自动计算不穿模的最大角度"),
            ("T_POSE", "T-Pose", "把手臂摆成 T 字姿态"),
            ("REST", "静置", "保持静置姿态，不做手臂旋转"),
        ],
        default="AUTO",
    )
    visible_only: bpy.props.BoolProperty(
        name="仅可见网格",
        description="忽略完全透明的隐藏部位（如隐藏的尾巴、耳朵）参与布局与穿模判断",
        default=True,
    )
    show_more_params: bpy.props.BoolProperty(
        name="显示更多参数",
        description="显示更多参数",
        default=False,
    )
    upper_arm_names: bpy.props.StringProperty(
        name="大臂骨骼",
        description="大臂骨骼名称，可用中英文逗号分隔多个名称\n用于调整手臂姿态",
        default="腕.L, 腕.R",
    )
    forearm_names: bpy.props.StringProperty(
        name="小臂骨骼",
        description="小臂骨骼名称，可用中英文逗号分隔多个名称\n用于调整手臂姿态时的穿模检测",
        default="ひじ.L, ひじ.R",
    )
    # 虽然写作头骨骼，但实际起作用的是顶点组，为了面板语义及操作统一，这里写作头骨骼
    head_vg_names: bpy.props.StringProperty(
        name="头骨骼",
        description="头部顶点组名称，可用中英文逗号分隔多个名称\n用于面部特写时头部的识别\n"
                    "当目骨骼或其对应网格不存在时启用该参数",
        default="頭",
    )
    eye_vg_names: bpy.props.StringProperty(
        name="目骨骼",
        description="眼部顶点组名称，可用中英文逗号分隔多个名称\n用于限制面部特写的横向范围",
        default="目.L, 目.R",
    )
    closeup_head_ratio: bpy.props.FloatProperty(
        name="特写头部占比",
        description="特写中头部占画面高度的比例，数值越大头部越大\n"
                    "当目骨骼或其对应网格不存在时启用该参数",
        default=2 / 3,
        min=0.05,
        max=1.0,
    )
    closeup_face_width_ratio: bpy.props.FloatProperty(
        name="特写面部宽度比例",
        description="数值越大越贴近面部（两侧裁剪更多、面部更大），数值越小保留更多头发\n当目骨骼或其对应网格不存在时，该参数失效",
        default=1.0,
        min=0.2,
        max=5.0,
    )
    closeup_face_height_ratio: bpy.props.FloatProperty(
        name="特写面部高度比例",
        description="调整特写中面部的高度位置，数值越大角色越靠上，数值越小越靠下\n当目骨骼或其对应网格不存在时，该参数失效",
        default=1.0,
        min=0.2,
        max=2.5,
    )
    height_margin: bpy.props.FloatProperty(
        name="高度留白比例",
        description="角色高度占画面高度的比例，数值越小上下留白越多",
        default=0.95,
        min=0.25,
        max=1.0,
    )
    width_margin: bpy.props.FloatProperty(
        name="宽度留白比例",
        description="三视图在各自列内占用的宽度比例，数值越小左右留白越多",
        default=0.95,
        min=0.25,
        max=1.0,
    )
    side_view_angle: bpy.props.FloatProperty(
        name="侧视图角度",
        description="侧视图相对主视图绕竖直轴旋转的角度",
        subtype="ANGLE",
        default=math.radians(90),
        min=math.radians(-180),
        max=math.radians(180),
    )
    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_render_three_view = bpy.props.PointerProperty(type=RenderThreeViewProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_render_three_view
