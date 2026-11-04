import bpy


class FixEyeWhiteProperty(bpy.types.PropertyGroup):
    eye_white: bpy.props.StringProperty(
        name="眼白",
        description="眼白对象名称，可用中英文逗号分隔多个名称",
        default=''
    )
    eye: bpy.props.StringProperty(
        name="眼睛",
        description="眼睛对象名称，可用中英文逗号分隔多个名称",
        default=''
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_fix_eye_white = bpy.props.PointerProperty(type=FixEyeWhiteProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_fix_eye_white
