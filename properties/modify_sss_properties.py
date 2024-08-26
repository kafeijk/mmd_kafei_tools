import bpy


class ModifySssProperty(bpy.types.PropertyGroup):
    strategy: bpy.props.EnumProperty(
        name="类型/方式",
        description="修复方式",
        items=[
            ("INTELLIGENCE", "Eevee泛蓝问题（智能）", "根据节点的实际连接情况进行修复"),
            ("FORCE", "Eevee泛蓝问题（强制）", "通过创建额外的SSS着色器进行修复"),
            ("RESET", "Cycles显示问题（归零）", "将原理化BSDF节点的次表面恢复为默认值")
        ],
        default='INTELLIGENCE'
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_modify_sss = bpy.props.PointerProperty(type=ModifySssProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_modify_sss
