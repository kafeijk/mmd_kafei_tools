import bpy
from ..utils import *


def auto_fill(self, context):
    if self.toon_shading_flag:
        self.material_flag = True
        self.uv_flag = True
        self.vgs_flag = True
        self.modifiers_flag = True
        self.normal_flag = True

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
        name="源模型",
        description="提供预设的模型",
        type=bpy.types.Object
    )
    source_pmx2abc: bpy.props.PointerProperty(
        name="源模型",
        description="提供预设的模型",
        type=bpy.types.Object
    )
    target: bpy.props.PointerProperty(
        name="目标模型",
        description="接受预设的模型",
        type=bpy.types.Object
    )
    direction: bpy.props.EnumProperty(
        name="传递方向",
        description="预设传递方向",
        default='PMX2ABC',
        items=[
            # pmx -> abc 较为常用
            ('PMX2ABC', 'PMX → ABC', "将PMX模型的预设传递到ABC模型上"),
            # pmx -> pmx 一定配合强校验，可解决网格顺序不同、网格内容修改后重新导入产生的重复上材质问题
            ('PMX2PMX', 'PMX → PMX', "将PMX模型的预设传递到PMX模型上"),
            ('ABC2ABC', 'ABC → ABC', "根据缓存文件重新设定网格序列缓存修改器参数")
        ],
        update=lambda self, context: update_preset(self, context)
    )
    material_flag: bpy.props.BoolProperty(
        name="材质",
        description="关联材质，支持多材质槽",
        default=True,
        update=lambda self, context: self.check_selection(context, "material_flag")
    )
    uv_flag: bpy.props.BoolProperty(
        name="UV贴图",
        description="复制UV贴图",
        default=True,
        update=lambda self, context: self.check_selection(context, "uv_flag")
    )
    vgs_flag: bpy.props.BoolProperty(
        name="顶点组",
        description="传递自定义顶点组及对应权重",
        default=True,
        update=lambda self, context: self.check_selection(context, "vgs_flag")

    )
    modifiers_flag: bpy.props.BoolProperty(
        name="修改器",
        description="复制修改器",
        default=True,
        update=lambda self, context: self.check_selection(context, "modifiers_flag")
    )
    normal_flag: bpy.props.BoolProperty(
        name="法向",
        description="传递自定义拆边法向数据",
        default=True,
        update=lambda self, context: self.check_selection(context, "normal_flag")
    )
    toon_shading_flag: bpy.props.BoolProperty(
        name="三渲二",
        description="编辑三渲二预设中的相关参数设置",
        default=False,
        update=lambda self, context: auto_fill(self, context)
    )
    face_locator: bpy.props.PointerProperty(
        name="面部定位器",
        description="源物体中父级类型为骨骼的对象（该骨骼通常为“頭”），用于定位面部。默认情况下，该值会自动填充",
        type=bpy.types.Object,
    )

    auto_face_location: bpy.props.BoolProperty(
        name="自动面部识别",
        description="根据面部定位器识别面部顶点",
        default=True,
    )

    face_object: bpy.props.PointerProperty(
        name="面部对象",
        description="面部对象",
        type=bpy.types.Object
    )

    face_vg: bpy.props.StringProperty(
        name="面部顶点组",
        description="面部对象的顶点组"
    )

    abc_filepath: bpy.props.StringProperty(
        name="缓存文件",
        description="缓存文件地址",
        subtype='FILE_PATH',
        default=''
    )

    selected_only: bpy.props.BoolProperty(
        name="仅选中",
        description="影响范围为选中物体",
        default=True,
    )

    tolerance: bpy.props.FloatProperty(
        name="误差",
        description="匹配过程中，顶点数、顶点位置的误差百分比。",
        default=0.0,
        min=0.0,
        max=1
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_transfer_preset = bpy.props.PointerProperty(type=TransferPresetProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_transfer_preset

    def check_selection(self, context, changed_property):
        """检查选项，至少保持一个选项被选中"""
        if not (self.material_flag or self.uv_flag or self.vgs_flag or self.modifiers_flag or self.normal_flag):
            if changed_property == "material_flag":
                self.material_flag = True
            elif changed_property == "uv_flag":
                self.uv_flag = True
            elif changed_property == "vgs_flag":
                self.vgs_flag = True
            elif changed_property == "modifiers_flag":
                self.modifiers_flag = True
            elif changed_property == "normal_flag":
                self.normal_flag = True
