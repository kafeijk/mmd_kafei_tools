import bpy

from .batch_properties import BatchProperty


class ModifySpecifyContentProperty(bpy.types.PropertyGroup):
    content_type: bpy.props.EnumProperty(
        name="内容",
        description="操作内容",
        items=[
            ("ADD_UV_MAP", "添加UV贴图", "添加UV贴图"),
            ("ADD_COLOR_ATTRIBUTE", "添加颜色属性", "添加颜色属性"),

            ("REMOVE_UV_MAP", "移除UV贴图", "移除UV贴图"),  # keep_first
            ("REMOVE_COLOR_ATTRIBUTE", "移除颜色属性", "移除颜色属性"),  # keep_first
            ("REMOVE_MATERIAL", "移除材质", "移除材质"),  # create_default
            ("REMOVE_MODIFIER", "移除修改器", "移除修改器"),  # keep_first
            ("REMOVE_VERTEX_GROUP", "移除顶点组", "移除顶点组"),
            ("REMOVE_SHAPE_KEY", "移除形态键", "移除形态键"),  # keep_current

        ]
    )
    uv_name: bpy.props.StringProperty(
        name="名称",
        description="UV名称",
        default=''
    )
    average_islands_flag: bpy.props.BoolProperty(
        name="孤岛比例平均化",
        description="孤岛比例平均化",
        default=True
    )

    color_attribute_name: bpy.props.StringProperty(
        name="名称",
        description="UV名称",
        default=''
    )
    color: bpy.props.FloatVectorProperty(
        name="颜色",
        description="颜色",
        subtype='COLOR',
        size=4,
        min=0.0,  # 最小值为0
        max=1.0,  # 最大值为1
        default=(0, 0, 0, 1)

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
    keep_locked: bpy.props.BoolProperty(
        name="保留锁定组",
        description="移除时，保留锁定组",
        default=False
    )
    keep_current: bpy.props.BoolProperty(
        name="保留当前形态",
        description="移除形态键时，保留当前形态，否则保留默认姿态",
        default=True
    )
    batch: bpy.props.PointerProperty(type=BatchProperty)

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_modify_specify_content = bpy.props.PointerProperty(
            type=ModifySpecifyContentProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_modify_specify_content
