import bpy

from .batch_properties import BatchProperty


class RemoveSpecifyContentProperty(bpy.types.PropertyGroup):
    content_type: bpy.props.EnumProperty(
        name="移除类型",
        description="移除类型",
        items=[
            ("UV_MAP", "UV贴图", "移除类型：UV贴图"),  # 适用场景：某些模型UV数量太多了，没用还占地方（很占体积），提供批量处理  keep_first
            ("MATERIAL", "材质", "移除类型：材质"),  # 适用场景：星铁咒  create_default
            ("MODIFIER", "修改器", "移除类型：修改器"),  # keep_first
            ("VERTEX_GROUP", "顶点组", "移除类型：顶点组"),  # 适用场景：失去权重，但仍有骨骼，如模之屋仅展示时
            # 适用场景：通过形态键value大小来创建差分时（如不同角色眼眶大小的不同）
            # 提供保持当前形态的选项
            # todo 提供一个传递形态键的工具？
            ("SHAPE_KEY", "形态键", "移除类型：形态键"),  # keep_current

        ]
    )
    create_default: bpy.props.BoolProperty(
        name="新建默认材质",
        description="移除材质后，新建默认材质",
        default=True
    )
    keep_first: bpy.props.BoolProperty(
        name="保留首位",
        description="移除时，保留位于首位的内容",
        default=True
    )
    keep_current: bpy.props.BoolProperty(
        name="保留当前形态",
        description="移除形态键时，保留当前形态，否则保留默认姿态",
        default=True
    )
    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_remove_specify_content = bpy.props.PointerProperty(
            type=RemoveSpecifyContentProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_remove_specify_content
