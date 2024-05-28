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


class TransferPmxToAbcProperties(bpy.types.PropertyGroup):
    # todo 是否可以不强制重叠在一起而是分开一定距离的情况下进行设置
    multi_material_slots_flag: bpy.props.BoolProperty(
        name="多材质槽",
        description="如果pmx物体具有多个材质槽，则将这些材质设置到abc物体对应的面上",
        default=True
    )
    # todo 更稳妥的方式是溜一遍pose bone，去除pose bone和mmd标识顶点组之后的内容为要关联的内容
    # todo 操作完成后应恢复原状（激活状态及之前激活的内容）
    vgs_flag: bpy.props.BoolProperty(
        name="顶点组",
        description="将pmx物体自定义的顶点组及顶点权重传递到abc的对应物体上",
        default=True,

    )
    modifiers_flag: bpy.props.BoolProperty(
        name="修改器",
        description="将pmx物体拥有的修改器传递到abc物体上",
        default=True,
        update=lambda self, context: update_vgs_flag(self, context)
    )
    gen_skin_uv_flag: bpy.props.BoolProperty(
        name="皮肤UV",
        description="对abc物体添加指定名称的UV，这些UV是孤岛比例平均化之后的结果",
        default=False
    )
    skin_uv_name: bpy.props.StringProperty(
        name="皮肤UV名称",
        description="皮肤UV名称",
        default='skin_uv'
    )
    toon_shading_flag: bpy.props.BoolProperty(
        name="三渲二",
        description="将三渲二预设应用到abc对应物体上",
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
        description="pmx模型面部所在对象",
        type=bpy.types.Object
    )

    face_vg: bpy.props.StringProperty(
        name="面部顶点组",
        description="pmx模型面部顶点组"
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_transfer_pmx_to_abc = bpy.props.PointerProperty(type=TransferPmxToAbcProperties)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_transfer_pmx_to_abc
