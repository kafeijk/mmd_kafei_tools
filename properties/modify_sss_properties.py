import bpy


class ModifySssProperty(bpy.types.PropertyGroup):
    strategy: bpy.props.EnumProperty(
        name="问题",
        description="修复方式",
        items=[
            ("INTELLIGENCE", "Eevee显示泛蓝", "根据节点的实际连接情况进行修复"),
            ("RESET", "Cycles显示模糊", "将原理化BSDF节点的次表面值归零")
        ],
        default='INTELLIGENCE'
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_modify_sss = bpy.props.PointerProperty(type=ModifySssProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_modify_sss
