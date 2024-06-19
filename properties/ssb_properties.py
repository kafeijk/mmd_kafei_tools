import bpy

from .batch_properties import BatchProperty


class SsbBaseProperty(bpy.types.PropertyGroup):
    root_checked: bpy.props.BoolProperty(
        name="全ての親",
        description="全ての親",
        default=True
    )
    arm_twist_checked: bpy.props.BoolProperty(
        name="腕弯曲骨骼 *",
        description="腕弯曲骨骼 *",
        default=True
    )
    enable_elbow_offset_checked: bpy.props.BoolProperty(
        name="自动补正旋转轴",
        description="自动补正旋转轴",
        default=True
    )
    wrist_twist_checked: bpy.props.BoolProperty(
        name="手弯曲骨骼 *",
        description="手弯曲骨骼 *",
        default=True
    )
    upper_body2_checked: bpy.props.BoolProperty(
        name="上半身2骨骼 *",
        description="上半身2骨骼 *",
        default=True
    )
    groove_checked: bpy.props.BoolProperty(
        name="グルーブ骨",
        description="グルーブ骨",
        default=True
    )
    waist_checked: bpy.props.BoolProperty(
        name="腰骨骼",
        description="腰骨骼",
        default=True
    )
    ik_p_checked: bpy.props.BoolProperty(
        name="足IK親",
        description="足IK親",
        default=True
    )
    view_center_checked: bpy.props.BoolProperty(
        name="操作中心",
        description="操作中心",
        default=True
    )
    ex_checked: bpy.props.BoolProperty(
        name="足先EX *",
        description="足先EX *",
        default=True
    )
    enable_leg_d_controllable_checked: bpy.props.BoolProperty(
        name="将足D骨骼变成可以操作",
        description="将足D骨骼变成可以操作",
        default=True
    )
    dummy_checked: bpy.props.BoolProperty(
        name="手持骨",
        description="手持骨",
        default=True
    )
    shoulder_p_checked: bpy.props.BoolProperty(
        name="肩P",
        description="肩P",
        default=True
    )
    thumb0_checked: bpy.props.BoolProperty(
        name="大拇指０骨骼 *",
        description="大拇指０骨骼 *",
        default=True
    )
    enable_thumb_local_axes_checked: bpy.props.BoolProperty(
        name="设定親指Local轴",
        description="设定親指Local轴",
        default=True
    )
    enable_gen_frame_checked: bpy.props.BoolProperty(
        name="自动注册到骨骼显示枠",
        description="自动注册到骨骼显示枠",
        default=True
    )


class AddSsbProperty(bpy.types.PropertyGroup):
    model: bpy.props.PointerProperty(
        name="模型",
        description="MMD模型",
        type=bpy.types.Object
    )
    # 创建骨骼的时候需要考虑到mmd和blender之间的缩放，通常是0.08，即12.5
    # 但是这个缩放值并不会在blender中保存，所以无法得知用户导入模型时的具体数值
    # mmd插件导入时，scale参数是通过ImportHelper传递的，不清楚如何获取，就算能获取也无法处理多模型的情况，且该值不会被保存，再次打开文件时丢失。
    # 所以这里提供一个scale参数让用户填写
    scale: bpy.props.FloatProperty(
        name="缩放",
        description="导入模型时的缩放倍数",
        default=0.08
    )
    base: bpy.props.PointerProperty(type=SsbBaseProperty)

    batch: bpy.props.PointerProperty(type=BatchProperty)
    # blender相比PE的好处是，删除骨骼后，顶点权重依然被保留。
    # 重新创建ssb时，如果权重正确，则不会改变（所以赋予权重时要用ADD而不是REPLACE）；如果权重不正确，将重新分配。
    # 利用上述特点，增加强制重建选项
    force: bpy.props.BoolProperty(
        name="强制重建",
        description="如果骨骼已经存在，将重建骨骼。可以保证在满足先决条件的情况下，必定能成功创建骨骼\n"
                    "本选项仅应在权重正确但骨骼缺失的情况下开启",
        default=False
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_add_ssb = bpy.props.PointerProperty(type=AddSsbProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_add_ssb
