import bpy


def update_vgs_flag(self, context):
    if self.modifiers_flag:
        self.vgs_flag = True


def auto_fill(self, context):
    if self.toon_shading_flag:
        self.multi_material_slots_flag = True
        self.vgs_flag = True
        self.modifiers_flag = True

        if self.face_locator is None:
            pmx_model = next((obj for obj in bpy.context.scene.objects if obj.mmd_type == 'ROOT'), None)
            if pmx_model is None:
                return
            pmx_armature = next((child for child in pmx_model.children if child.type == 'ARMATURE'), None)
            if pmx_armature is None:
                return
            face_locator = next((child for child in pmx_armature.children if child.parent_type == 'BONE'), None)
            self.face_locator = face_locator


def update_preset(self, context):
    if self.direction == 'PMX2PMX':
        self.toon_shading_flag = False


class TransferPresetProperty(bpy.types.PropertyGroup):
    source: bpy.props.PointerProperty(
        name="源物体",
        description="源物体",
        type=bpy.types.Object
    )
    target: bpy.props.PointerProperty(
        name="目标物体",
        description="目标物体",
        type=bpy.types.Object
    )
    direction: bpy.props.EnumProperty(
        name="传递方向",
        description="传递方向",
        default='PMX2ABC',
        items=[
            # pmx -> abc 较为常用
            ('PMX2ABC', 'pmx -> abc', "将pmx源物体的材质传递到abc目标物体上"),
            # pmx -> pmx 一定配合强校验，可解决网格顺序不同、网格内容修改后重新导入产生的重复上材质问题
            ('PMX2PMX', 'pmx -> pmx', "将pmx源物体的材质传递到pmx目标物体上")
        ],
        update=lambda self, context: update_preset(self, context)
    )
    material_flag: bpy.props.BoolProperty(
        name="材质",
        description="关联材质与UV，如果源物体具有多个材质槽，则将这些材质设置到目标物体对应的面上",
        default=True
    )
    vgs_flag: bpy.props.BoolProperty(
        name="顶点组",
        description="将源物体自定义的顶点组及顶点权重传递到目标物体上",
        default=True,

    )
    modifiers_flag: bpy.props.BoolProperty(
        name="修改器",
        description="将源物体拥有的修改器传递到目标物体上",
        default=True,
        update=lambda self, context: update_vgs_flag(self, context)
    )
    normal_flag: bpy.props.BoolProperty(
        name="法向",
        description="将源物体拥有的自定义拆边法向数据传递到目标物体上",
        default=True
    )
    gen_skin_uv_flag: bpy.props.BoolProperty(
        name="皮肤UV",
        description="对目标物体添加指定名称的UV，这些UV是孤岛比例平均化之后的结果",
        default=False
    )
    skin_uv_name: bpy.props.StringProperty(
        name="UV名称",
        description="皮肤UV名称",
        default='skin_uv'
    )
    toon_shading_flag: bpy.props.BoolProperty(
        name="三渲二",
        description="将源物体三渲二预设应用到目标物体上",
        default=False,
        update=lambda self, context: auto_fill(self, context)
    )
    face_locator: bpy.props.PointerProperty(
        name="面部定位器",
        description="面部定位器",
        type=bpy.types.Object,
    )

    auto_face_location: bpy.props.BoolProperty(
        name="自动面部识别",
        description="自动面部识别",
        default=True,
    )

    face_object: bpy.props.PointerProperty(
        name="面部对象",
        description="源模型面部所在对象",
        type=bpy.types.Object
    )

    face_vg: bpy.props.StringProperty(
        name="面部顶点组",
        description="源模型面部顶点组"
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_transfer_preset = bpy.props.PointerProperty(type=TransferPresetProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_transfer_preset
