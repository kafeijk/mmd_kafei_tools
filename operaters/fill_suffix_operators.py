import bpy


class FillSuffixChangeTexlocOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_change_tex_loc"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_change_tex_loc.batch.suffix = bpy.app.translations.pgettext(" 修改贴图路径")
        return {'FINISHED'}


class FillSuffixSsbOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_ssb"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_add_ssb.batch.suffix = bpy.app.translations.pgettext(" 修复次标准骨骼")
        return {'FINISHED'}


class FillSuffixRemoveUvMapOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_remove_uv_map"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_remove_uv_map.batch.suffix = bpy.app.translations.pgettext(" 移除冗余UV")
        return {'FINISHED'}


class FillSuffixOrganizePanelOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_organize_panel"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_organize_panel.batch.suffix = bpy.app.translations.pgettext(" 面板整理")
        return {'FINISHED'}


class FillSuffixRenderPreviewOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.fill_suffix_render_preview"
    bl_label = "填充"
    bl_description = "填充名称后缀"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mmd_kafei_tools_render_preview.batch.suffix = "_preview"
        return {'FINISHED'}
