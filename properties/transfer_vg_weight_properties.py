import bpy


class TransferVgWeightProperty(bpy.types.PropertyGroup):
    source_vg_name: bpy.props.StringProperty(
        name="源顶点组",
        description="源顶点组名称，必填项，如果不存在，则跳过处理"
    )
    target_vg_name: bpy.props.StringProperty(
        name="目标顶点组",
        description="目标顶点组名称，必填项，如果不存在，则会自动创建一个新的顶点组"
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_transfer_vg_weight = bpy.props.PointerProperty(type=TransferVgWeightProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_transfer_vg_weight
