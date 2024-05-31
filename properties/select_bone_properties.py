import bpy


class SelectBoneProperty(bpy.types.PropertyGroup):
    category: bpy.props.EnumProperty(
        name="用途",
        description="骨骼用途",
        items=[
            ("MIXAMO", "Mixamo烘焙VMD", "Mixamo烘焙VMD")
        ],
        default="MIXAMO"
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_select_bone = bpy.props.PointerProperty(type=SelectBoneProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_select_bone
