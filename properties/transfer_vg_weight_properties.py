import bpy


class TransferVgWeightProperty(bpy.types.PropertyGroup):
    source_vg: bpy.props.StringProperty(
        name="源顶点组",
        description="源顶点组，必填项，不存在则跳过"
    )
    target_vg: bpy.props.StringProperty(
        name="目标顶点组",
        description="源顶点组，必填项，不存在则默认新建"
    )

    # todo 是否提供仅选中顶点的选项，以修复如足尖部分权重因某些误操作跑到足首上面的问题（单一物体），但这种情况并不普遍

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_transfer_vg_weight = bpy.props.PointerProperty(type=TransferVgWeightProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_transfer_vg_weight
