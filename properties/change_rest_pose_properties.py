import bpy


class ChangeRestPoseProperty(bpy.types.PropertyGroup):
    h_joint_strategy: bpy.props.EnumProperty(
        name="横Joint变换策略",
        description="用何种方式重新设定横Joint的变换",  # Joint的缩放值对最终结果无影响
        items=[
            # 生成横Joint时的逻辑
            # public IPEVector3[,] GetSideJointPos(IPEVector3[,] bodyPos)
            # public IPEVector3[,] GetSideJointRot(IPEVector3[,] bodyRot)
            ("CENTROID", "平均", "根据连接的刚体A与刚体B计算平均值"),
            # PE修改骨骼时横Joint的变换逻辑
            ("RIGIDBODY_A", "跟随刚体A", "跟随刚体A")
        ]
    )

    force_apply: bpy.props.BoolProperty(
        name="强制应用修改器",
        description="当网格对象存在形态键时，强制应用修改器",
        default=True
    )


    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_change_rest_pose = bpy.props.PointerProperty(type=ChangeRestPoseProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_change_rest_pose
