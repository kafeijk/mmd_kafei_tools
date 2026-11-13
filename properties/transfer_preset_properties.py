import bpy
from ..utils import find_pmx_armature, find_pmx_root_with_child

# 各传递方向的默认选项，切换方向或勾选三渲二时统一应用
DEFAULT_FLAGS = {
    'PMX2PMX': {
        'material_flag': True,
        'uv_flag': False,
        'vgs_flag': True,
        'modifiers_flag': True,
        'remove_suffix_flag': True,
    },
    'PMX2ABC': {
        'material_flag': True,
        'uv_flag': True,
        'vgs_flag': True,
        'modifiers_flag': True,
        'normal_flag': True,
    },
}


def apply_default_flags(props, enable_only=False):
    """按当前方向应用默认选项；enable_only=True 时只勾选推荐项，不取消用户已勾选的选项"""
    flags = DEFAULT_FLAGS.get(props.direction, {})
    # 先开启后关闭，避免中途触发空选项保护
    for name, value in flags.items():
        if value:
            setattr(props, name, value)
    if enable_only:
        return
    for name, value in flags.items():
        if not value:
            setattr(props, name, value)


def auto_fill(self, context):
    if not self.toon_shading_flag:
        return

    # 勾选三渲二时只勾选该方向的推荐项，不会关闭三渲二或取消已勾选的选项
    apply_default_flags(self, enable_only=True)

    if self.face_locator is not None:
        return
    # 优先按当前源模型查找骨骼父级对象；未选源模型时，仅当场景中只有一个 PMX 根对象才填充
    if self.source is not None:
        root = find_pmx_root_with_child(self.source)
    else:
        roots = [obj for obj in bpy.context.scene.objects if obj.mmd_type == 'ROOT']
        root = roots[0] if len(roots) == 1 else None
    if root is None:
        return
    armature = find_pmx_armature(root)
    if armature is None:
        return
    self.face_locator = next(
        (child for child in armature.children if child.parent_type == 'BONE'), None)


def update_preset(self, context):
    """切换方向时按默认选项重置，并关闭三渲二"""
    apply_default_flags(self)
    self.toon_shading_flag = False


class TransferPresetProperty(bpy.types.PropertyGroup):
    source: bpy.props.PointerProperty(
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
        default='PMX2PMX',
        items=[
            # pmx -> pmx 一定配合强校验，可解决网格顺序不同、网格内容修改后重新导入产生的重复上材质问题
            ('PMX2PMX', 'PMX → PMX', "将PMX模型的预设传递到PMX模型上"),
            ('PMX2ABC', 'PMX → ABC', "将PMX模型的预设传递到ABC模型上"),
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
        default=False,
        update=lambda self, context: self.check_selection(context, "uv_flag")
    )
    vgs_flag: bpy.props.BoolProperty(
        name="顶点组",
        description="传递自定义顶点组及对应权重\n自定义顶点组指的是排在 mmd_vertex_order 之后的顶点组",
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
    remove_suffix_flag: bpy.props.BoolProperty(
        name="移除重名后缀",
        description="传递后移除目标模型对象、数据、材质与贴图名称中的 .001 等重名后缀\n"
                    "与源模型同名时交换名称，目标模型内部同名或与其他数据冲突时跳过",
        default=True,
        update=lambda self, context: self.check_selection(context, "remove_suffix_flag")
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

    force: bpy.props.BoolProperty(
        name="强制跟随",
        description="复制面部对象并使定位器跟随该对象，从而避免原面部对象因几何节点导致的无法跟随问题。可根据实际需求选择启用",
        default=True,
    )

    abc_filepath: bpy.props.StringProperty(
        name="缓存文件",
        description="缓存文件地址",
        subtype='FILE_PATH',
        default=''
    )

    selected_only: bpy.props.BoolProperty(
        name="仅选中",
        description="影响范围为选中物体所属模型",
        default=True,
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_transfer_preset = bpy.props.PointerProperty(type=TransferPresetProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_transfer_preset

    def check_selection(self, context, changed_property):
        """检查选项，至少保持一个选项被选中；PMX2PMX 不传递法向，法向不参与判断"""
        names = ['material_flag', 'uv_flag', 'vgs_flag', 'modifiers_flag']
        if self.direction == 'PMX2PMX':
            # PMX2PMX 的「移除重名后缀」也是独立可用的选项
            names.append('remove_suffix_flag')
        else:
            names.append('normal_flag')
        if not any(getattr(self, name) for name in names):
            setattr(self, changed_property, True)
