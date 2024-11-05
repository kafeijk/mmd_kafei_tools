import bpy


def update_keywords(self, context):
    non_color_preset = ['lightmap', 'metalness', 'roughness', 'normal', 'displacement', 'opacity']
    other_preset = ['diffuse']
    existing_keywords = set([keyword.strip() for keyword in self.keywords.split(',') if keyword.strip()])

    print(self.colorspace)
    if self.colorspace == 'Non-Color':
        existing_keywords.difference_update(other_preset)
        # 重新设置关键字
        if len(existing_keywords) == 0:
            self.keywords = ','.join(non_color_preset)
        else:
            self.keywords = ','.join(existing_keywords)
    else:
        existing_keywords.difference_update(non_color_preset)
        # 重新设置关键字
        if len(existing_keywords) == 0:
            self.keywords = ','.join(other_preset)
        else:
            self.keywords = ','.join(existing_keywords)

    print(existing_keywords)


class ModifyColorspaceProperty(bpy.types.PropertyGroup):
    def get_colorspace(self, context):
        # 限定常用色彩空间
        source_list = [
            # ID,名称,描述
            ("sRGB", "sRGB", "sRGB"),
            ("Utility - sRGB - Texture", "Utility - sRGB - Texture", "Utility - sRGB - Texture"),
            ("Utility - Raw", "Utility - Raw", "Utility - Raw"),
            ("Utility - Linear - sRGB", "Utility - Linear - sRGB", "Utility - Linear - sRGB"),
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

    colorspace: bpy.props.EnumProperty(
        name="色彩空间",
        description="贴图的色彩空间",
        items=get_colorspace,
        update=lambda self, context: update_keywords(self, context)
    )
    keywords: bpy.props.StringProperty(
        name="关键词",
        description="贴图名称关键词，用于搜索贴图。可填写多个关键词，用英文逗号隔开。没有填写则代表所有图像都将被修改为指定色彩空间",
        default='diffuse'
    )
    selected_only: bpy.props.BoolProperty(
        name="仅选中",
        description="修改范围仅限于选中物体",
        default=True
    )

    # todo 关键词为空时必须勾选仅选中

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_modify_colorspace = bpy.props.PointerProperty(type=ModifyColorspaceProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_modify_colorspace
