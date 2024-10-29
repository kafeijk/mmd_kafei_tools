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
    # 一些权重如左右对称，如果涂抹过界的话，会比较麻烦
    # 比如裤子的足D骨权重，左边的涂到右边一些，在加入动作的时候会发生穿模，且这个穿模发生在右边。
    # 这个穿模本不应该发生，需排除左足D对右侧的影响，但涂权重手残费劲（裤子受到足D，臀骨，下半身的影响），直接通过框选顶点的方式处理更方便些
    selected_v_only: bpy.props.BoolProperty(
        name="仅选中顶点",
        description="权重转移时，影响范围为编辑模式下被选中的顶点",
        default=False

    )
    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_transfer_vg_weight = bpy.props.PointerProperty(type=TransferVgWeightProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_transfer_vg_weight
