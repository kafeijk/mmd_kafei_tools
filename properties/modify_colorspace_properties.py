import bpy


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
