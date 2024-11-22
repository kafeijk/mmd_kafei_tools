from ..utils import *


class ModifyColorspaceOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.modify_colorspace"
    bl_label = "修改"
    bl_description = "色彩空间调整"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_colorspace

        source_colorspace = props.source_colorspace
        target_colorspace = props.target_colorspace
        keywords = props.keywords

        for image in bpy.data.images:
            if keywords:
                keyword_list = [keyword.lower().strip() for keyword in keywords.split(",")]
                if any(keyword in image.name.lower().strip() for keyword in keyword_list):
                    # 修改图像的色彩空间
                    image.colorspace_settings.name = target_colorspace
            else:
                if image.colorspace_settings.name == source_colorspace:
                    image.colorspace_settings.name = target_colorspace
