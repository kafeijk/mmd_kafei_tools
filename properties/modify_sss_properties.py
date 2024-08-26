import bpy


class ModifySssProperty(bpy.types.PropertyGroup):
    strategy: bpy.props.EnumProperty(
        name="修复方式",
        description="修复方式",
        items=[
            ("INTELLIGENCE", "智能", "根据节点的实际连接情况进行修复"),
            ("FORCE", "强制", "通过创建额外的SSS着色器进行修复")
        ],
        default='INTELLIGENCE'
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_modify_sss = bpy.props.PointerProperty(type=ModifySssProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_modify_sss
