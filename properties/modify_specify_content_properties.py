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
            ("REMOVE_CONSTRAINT", "移除约束", "移除约束"),  # keep_first
            ("REMOVE_VERTEX_GROUP", "移除顶点组", "移除顶点组"),
            ("REMOVE_SHAPE_KEY", "移除形态键", "移除形态键"),  # keep_current
        ]
    )
    uv_name: bpy.props.StringProperty(
        name="名称",
        description="UV贴图名称",
        default=''
    )
    average_islands_flag: bpy.props.BoolProperty(
        name="孤岛比例平均化",
        description="孤岛比例平均化",
        default=True
    )

    color_attribute_name: bpy.props.StringProperty(
        name="名称",
        description="颜色属性名称",
        default=''
    )
    color: bpy.props.FloatVectorProperty(
        name="颜色",
        description="颜色",
        subtype='COLOR',
        size=4,
        min=0.0,  # 最小值为0
        max=1.0,  # 最大值为0   # 说是最大值，但会受到HEX等影响而大于1，并不能完全拦住，但能防止一下子拉到一个较高值
        default=(1, 1, 1, 1)  # RGBA

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
        description="移除形态键时，保留当前形态，否则保留默认形态",
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


class ArrangeObjectProperty(bpy.types.PropertyGroup):
    arrangement_type: bpy.props.EnumProperty(
        name="类型",
        description="排列类型",
        items=[
            ("ARRAY", "阵列", "阵列"),
            ("ARC", "圆弧", "曲线"),
            ("CIRCLE", "圆环", "圆环"),

        ],
        default="ARRAY"
    )
    direction: bpy.props.EnumProperty(
        name="方向",
        description="排列方向",
        items=[
            ("HORIZONTAL", "水平", "水平"),
            ("VERTICAL", "垂直", "垂直"),
        ],
        default="HORIZONTAL"
    )
    order: bpy.props.EnumProperty(
        name="顺序",
        description="排列顺序",
        items=[
            ("DEFAULT", "默认", "默认排序"),
            ("FACE_ASC", "面数升序", "按面数从小到大排序"),
            ("FACE_DESC", "面数降序", "按面数从大到小排序"),
            ("NAME_ASC", "名称升序", "按名称自然排序升序"),
            ("NAME_DESC", "名称降序", "按名称自然排序降序"),
            ("SIZE_ASC", "尺寸升序", "按物体尺寸从小到大排序"),
            ("SIZE_DESC", "尺寸降序", "按物体尺寸从大到小排序"),
        ],
        default="DEFAULT"
    )
    start_trans: bpy.props.FloatVectorProperty(
        name="起始位置",
        description="起始位置",
        subtype='TRANSLATION',
        size=3,
        default=(0, 0, 0)
    )
    num_per_row: bpy.props.IntProperty(
        name="每行数量",
        description="每行数量",
        default=20
    )
    spacing: bpy.props.FloatVectorProperty(
        name="间距",
        description="排列间距",
        subtype='TRANSLATION',
        size=3,
        default=(1, 1.5, 2)
    )
    threshold: bpy.props.FloatProperty(
        name="尺寸阈值",
        # 300m在默认视图裁剪点（1000m）之内，且大于建筑等模型尺寸（100m~300m），故设为默认值
        description="如果物体的任意子级网格对象在 X、Y 或 Z 方向上的尺寸大于设定阈值，则该物体将跳过排列处理，并统一放置在坐标 (0, 300, 0) 处。",
        default=5,
        subtype='DISTANCE',
    )

    radius: bpy.props.FloatProperty(
        name="起始半径",
        description="起始半径",
        default=7,
        subtype='DISTANCE'
    )
    num_per_circle: bpy.props.IntProperty(
        name="每环数量",
        description="每个圆环/圆弧放置角色的数量",
        default=20
    )
    spacing_circle: bpy.props.FloatProperty(
        name="间距",
        description="圆环/圆弧间距",
        default=1,
        subtype='DISTANCE'
    )
    offset: bpy.props.BoolProperty(
        name="偏移",
        description="对不同圆环/圆弧上的角色进行偏移",
        default=True,
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_arrange_object = bpy.props.PointerProperty(type=ArrangeObjectProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_arrange_object
