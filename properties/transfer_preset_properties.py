import bpy
from ..utils import *


def auto_fill(self, context):
    if self.toon_shading_flag:
        self.material_flag = True
        self.uv_flag = True
        self.vgs_flag = True
        self.modifiers_flag = True

        if self.face_locator is None:
            root = find_pmx_root()
            if root is None:
                return
            armature = find_pmx_armature(root)
            if armature is None:
                return
            face_locator = next((child for child in armature.children if child.parent_type == 'BONE'), None)
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
        description="关联材质，如果源物体具有多个材质槽，则将这些材质设置到目标物体对应的面上",
        default=True,
        update=lambda self, context: self.check_selection(context, "material_flag")
    )
    uv_flag: bpy.props.BoolProperty(
        name="UV贴图",
        description="关联UV",
        default=True,
        update=lambda self, context: self.check_selection(context, "uv_flag")
    )
    vgs_flag: bpy.props.BoolProperty(
        name="顶点组",
        description="将源物体自定义的顶点组及顶点权重传递到目标物体上",
        default=True,
        update=lambda self, context: self.check_selection(context, "vgs_flag")

    )
    modifiers_flag: bpy.props.BoolProperty(
        name="修改器",
        description="将源物体拥有的修改器传递到目标物体上",
        default=True,
        update=lambda self, context: self.check_selection(context, "modifiers_flag")
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

    def check_selection(self, context, changed_property):
        """检查选项，至少保持一个选项被选中"""
        if not (self.material_flag or self.uv_flag or self.vgs_flag or self.modifiers_flag):
            if changed_property == "material_flag":
                self.material_flag = True
            elif changed_property == "uv_flag":
                self.uv_flag = True
            elif changed_property == "vgs_flag":
                self.vgs_flag = True
            elif changed_property == "modifiers_flag":
                self.modifiers_flag = True
