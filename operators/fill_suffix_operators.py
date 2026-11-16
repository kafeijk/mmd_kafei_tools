import bpy


class FillSuffixPrePostProcessingOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_pre_post_processing"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_pre_post_processing.batch.suffix = bpy.app.translations.pgettext(" 预处理")
        return {'FINISHED'}


class FillSuffixSsbOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_ssb"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_add_ssb.batch.suffix = bpy.app.translations.pgettext(" 修复次标准骨骼")
        return {'FINISHED'}


class FillSuffixRenderPreviewOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_render_preview"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_render_preview.batch.suffix = "_preview"
        return {'FINISHED'}


class FillSuffixRenderThreeViewOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_render_three_view"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_render_three_view.batch.suffix = "_3view"
        return {'FINISHED'}
