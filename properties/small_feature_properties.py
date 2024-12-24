import bpy


class SmallFeatureProperty(bpy.types.PropertyGroup):
    option: bpy.props.EnumProperty(
        name="用途",
        description="用途",
        items=[
            ("SCENE_ROOT", "创建场景控制器", "创建一个空物体，以实现对整个场景的统一控制"),
            ("BAKE_BONE", "选择烘焙动作骨骼", "选择用于烘焙VMD动作的MMD骨骼"),
            ("PHYSICAL_BONE", "选择物理骨骼", "选择受物理影响的MMD骨骼"),
            ("INVALID_RIGIDBODY_JOINT", "移除失效刚体Joint", "移除失效刚体Joint"),
            ("SUBSURFACE_EV", "修复Eevee显示泛蓝", "修复Eevee显示泛蓝问题"),
            ("SUBSURFACE_CY", "修复Cycles显示模糊", "将原理化BSDF节点的次表面值归零")
        ],
        default="SCENE_ROOT"
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_sf = bpy.props.PointerProperty(type=SmallFeatureProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_sf
