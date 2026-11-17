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
        description="面部特写占画面宽度的比例，0 表示不渲染特写，1 表示只渲染特写",
        default=0.25,
        min=0.0,
        max=1.0,
    )
    arm_angle: bpy.props.EnumProperty(
        name="手臂姿态",
        description="在预览或渲染三视图时，自动调整模型的手臂姿态",
        items=[
            ("AUTO", "自动", "两侧手臂沿前后轴逐渐向内旋转，直至即将与身体或其它部位发生穿模时停止，以减小角色横向占用空间，使角色在视图中显示得更大"),
            ("T_POSE", "T-Pose", "将手臂调整为 T-Pose 姿态"),
            ("REST", "静置", "将手臂恢复至静置姿态"),
        ],
        default="AUTO",
    )
    visible_only: bpy.props.BoolProperty(
        name="仅可见网格",
        description="忽略完全透明的隐藏部位，不将其纳入布局计算与穿模检测，避免隐藏部位影响计算结果",
        default=True,
    )
    show_more_params: bpy.props.BoolProperty(
        name="显示更多参数",
        description="展开更多参数，以便进一步调整三视图的布局与显示效果",
        default=False,
    )
    upper_arm_names: bpy.props.StringProperty(
        name="大臂骨骼",
        description="大臂骨骼名称，可用中英文逗号分隔多个名称\n用于调整手臂姿态",
        default="腕.L, 腕.R",
    )
    forearm_names: bpy.props.StringProperty(
        name="小臂骨骼",
        description="小臂骨骼名称，可用中英文逗号分隔多个名称\n当「手臂姿态」设置为自动时，用于手臂姿态的穿模检测",
        default="ひじ.L, ひじ.R",
    )
    # 虽然写作头骨骼，但实际起作用的是顶点组，为了面板语义及操作统一，这里写作头骨骼
    head_vg_names: bpy.props.StringProperty(
        name="头骨骼",
        description="头部骨骼名称，可用中英文逗号分隔多个名称\n仅当「目」骨骼或其对应网格不存在时，才参与面部特写布局计算",
        default="頭",
    )
    eye_vg_names: bpy.props.StringProperty(
        name="目骨骼",
        description="眼部顶点组名称，可用中英文逗号分隔多个名称\n"
                    "其全部子孙骨骼也会被视为眼部骨骼，用于确定面部特写的宽度与高度",
        default="目.L, 目.R",
    )
    closeup_head_ratio: bpy.props.FloatProperty(
        name="特写头部比例",
        description="设置头部占面部特写画面高度的比例。仅在不存在眼部数据时生效，数值越大，头部显示越大",
        default=2 / 3,
        min=0.05,
        max=1.0,
    )
    closeup_face_width_ratio: bpy.props.FloatProperty(
        name="特写宽度比例",
        description="调整面部特写的宽度。数值越大，面部显示越大，两侧裁剪范围也越大。仅在存在眼部数据时生效",
        default=1.0,
        min=0.2,
        max=5.0,
    )
    closeup_face_height_ratio: bpy.props.FloatProperty(
        name="特写高度比例",
        description="调整面部特写中面部的垂直位置。数值越大，角色整体位置越靠上；数值越小，位置越靠下。仅在存在眼部数据时生效",
        default=1.0,
        min=0.2,
        max=2.5,
    )
    height_margin: bpy.props.FloatProperty(
        name="视图高度比例",
        description="设置三视图中角色高度占画面高度的比例。数值越小，上下留白越多",
        default=0.95,
        min=0.25,
        max=1.0,
    )
    width_margin: bpy.props.FloatProperty(
        name="视图宽度比例",
        description="设置三视图中角色在各自视图范围内的宽度占比。数值越小，左右留白越多",
        default=0.95,
        min=0.25,
        max=1.0,
    )
    side_view_angle: bpy.props.FloatProperty(
        name="侧视图角度",
        description="设置侧视图中角色的旋转角度",
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
