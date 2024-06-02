import math

import bpy
from bpy.app.handlers import persistent
from mathutils import Euler


@persistent
def update_rotation(scene, depsgraph):
    active_camera = bpy.context.scene.camera
    props = scene.mmd_kafei_tools_render_preview
    auto_follow = props.auto_follow
    align = props.align
    if auto_follow and active_camera:
        # 暂时仅支持xyz1
        props.rotation_euler_x = active_camera.rotation_euler[0]
        if align:
            props.rotation_euler_y = math.radians(0)
        else:
            props.rotation_euler_y = active_camera.rotation_euler[1]

        props.rotation_euler_z = active_camera.rotation_euler[2]


class RenderPreviewProperty(bpy.types.PropertyGroup):
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
    rotation_euler_x: bpy.props.FloatProperty(
        name="旋转 X",
        description="欧拉旋转",
        subtype="ANGLE",
        default=math.radians(90)
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
        default=False
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
    align: bpy.props.BoolProperty(
        name="对齐角色",
        description="尽可能使角色处于画面中心。\n"
                    "（重要）该参数在角色处于静置状态时效果良好，如果出现意料外的情况请手动关闭\n"
                    "开启时Y轴旋转失效，不适用于多角色",
        default=False,
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_render_preview = bpy.props.PointerProperty(type=RenderPreviewProperty)
        bpy.app.handlers.depsgraph_update_post.append(update_rotation)

    @staticmethod
    def unregister():
        bpy.app.handlers.depsgraph_update_post.remove(update_rotation)
        del bpy.types.Scene.mmd_kafei_tools_render_preview
