import bpy


class SmallFeatureProperty(bpy.types.PropertyGroup):
    option: bpy.props.EnumProperty(
        name="用途",
        description="用途",
        items=[
            ("SCENE_ROOT", "创建场景控制器", "创建一个空物体，以实现对整个场景的统一控制"),
            ("REMOVE_MISSING_IMAGES", "移除丢失图像", "移除丢失的图像，以解决无法打包文件，找不到资源路径的问题"),
            ("SUBSURFACE_EV", "修复Eevee显示泛蓝", "修复Eevee显示泛蓝"),
            ("SUBSURFACE_CY", "修复Cycles显示模糊", "将原理化BSDF节点的次表面值归零"),
            ("MODIFY_COLORSPACE", "修改贴图色彩空间", "修改贴图色彩空间"),
            ("GROUP_OBJECT", "网格对象分组", "为网格对象分组"),
        ],
        default="SCENE_ROOT"
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_sf = bpy.props.PointerProperty(type=SmallFeatureProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_sf


class ModifyColorspaceProperty(bpy.types.PropertyGroup):
    def get_colorspace(self, context):
        # 限定常用色彩空间
        source_list = [
            # ID,名称,描述
            ("sRGB", "sRGB", "sRGB"),
            ("Utility - sRGB - Texture", "Utility - sRGB - Texture", "Utility - sRGB - Texture"),
            ("Utility - Raw", "Utility - Raw", "Utility - Raw"),
            ("Utility - Linear - sRGB", "Utility - Linear - sRGB", "Utility - Linear - sRGB"),
            ("Linear", "线性", "线性"),
            ("Linear Rec.709", "线性 Rec.709", "线性 Rec.709"),
            ("Non-Color", "非彩色", "非彩色"),
        ]
        colorspace_all = []
        for item in bpy.types.Image.bl_rna.properties['colorspace_settings'].fixed_type.properties['name'].enum_items:
            colorspace_all.append(item.identifier)
        target_list = []
        for source in source_list:
            if source[0] in colorspace_all:
                target_list.append((source[0], source[1], source[2]))
        return target_list

    source_colorspace: bpy.props.EnumProperty(
        name="源色彩空间",
        description="源色彩空间",
        items=get_colorspace,
    )
    target_colorspace: bpy.props.EnumProperty(
        name="目标色彩空间",
        description="目标色彩空间",
        items=get_colorspace,
    )
    keywords: bpy.props.StringProperty(
        name="关键词",
        description="贴图名称关键词，用于搜索贴图。忽略大小写，可用英文逗号分隔开。若启用关键词搜索，则源色彩空间参数将被忽略",
        default=''
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_modify_colorspace = bpy.props.PointerProperty(type=ModifyColorspaceProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_modify_colorspace


class GroupObjectProperty(bpy.types.PropertyGroup):
    scope: bpy.props.EnumProperty(
        name="影响范围",
        description="指定受影响的网格对象范围",
        items=[
            ("ROOT", "模型", "作用于选中物体所在的整个模型"),
            ("SELECTED_OBJECT", "物体", "仅作用于当前选中的物体"),
        ],
        default="ROOT"
    )

    search_type: bpy.props.EnumProperty(
        name="定位方式",
        description="根据何种方式定位贴图",
        items=[
            ("NODE_NAME", "节点名称", "根据材质中节点名称定位贴图"),
            ("TEX_NAME", "贴图名称", "根据材质中贴图名称定位贴图"),
        ],
        default="NODE_NAME"
    )

    node_keywords: bpy.props.StringProperty(
        name="关键词",
        description="节点名称关键词，用于搜索贴图。忽略大小写，可用英文逗号分隔开",
        default='mmd_base_tex'
    )

    img_keywords: bpy.props.StringProperty(
        name="关键词",
        description="贴图名称关键词，用于搜索贴图。忽略大小写，可用英文逗号分隔开",
        default='BaseColor,Diffuse,Albedo'
    )

    recursive: bpy.props.BoolProperty(
        name="递归搜索",
        description="当材质中有嵌套节点组时，是否递归查找节点",
        default=False
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_group_object = bpy.props.PointerProperty(type=GroupObjectProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_group_object
