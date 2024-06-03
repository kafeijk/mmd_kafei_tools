from ..utils import *


class RemoveSpecifyContentOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.remove_specify_content"
    bl_label = "执行"
    bl_description = "移除指定内容"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_remove_specify_content
        if not self.check_props(props):
            return
        content_type = props.content_type
        create_default = props.create_default
        keep_first = props.keep_first
        keep_current = props.keep_current
        batch = props.batch
        batch_flag = batch.flag

        active_object = bpy.context.active_object
        selected_objects = bpy.context.selected_objects
        objs = get_obj_by_type(selected_objects, content_type)
        if not batch_flag:
            for obj in objs:
                deselect_all_objects()
                select_and_activate(obj)
                if content_type == 'MATERIAL':
                    self.process_material(obj, create_default)
                elif content_type == 'MODIFIER':
                    self.process_modifiers(obj, keep_first)
                elif content_type == 'VERTEX_GROUP':
                    self.process_vgs(obj)
                elif content_type == 'SHAPE_KEY':
                    self.process_shape_keys(obj, keep_current)
                elif content_type == 'UV_MAP':
                    self.process_uvs(obj, keep_first)
            for selected_object in selected_objects:
                select_and_activate(selected_object)
            restore_selection(selected_objects, active_object)
        else:
            batch_process(self.do_remove, props)

    def check_props(self, props):
        batch = props.batch
        batch_flag = batch.flag
        if not batch_flag:
            objs = bpy.context.selected_objects
            if len(objs) == 0:
                self.report(type={'ERROR'}, message=f'请选择至少一个物体！')
                return False
        else:
            if not check_batch_props(self, batch):
                return False
        return True

    def process_uvs(self, obj, keep_first):
        uv_maps = obj.data.uv_layers
        if keep_first:
            uv_maps_to_remove = uv_maps[1:]
        else:
            uv_maps_to_remove = uv_maps
        for uv_map in reversed(uv_maps_to_remove):
            obj.data.uv_layers.remove(uv_map)
        # https://blender.stackexchange.com/questions/163300/how-to-update-an-object-after-changing-its-uv-coordinates
        obj.data.update()

    def process_shape_keys(self, obj, keep_current):
        if not obj.data.shape_keys:
            return
        if keep_current:
            sk = obj.shape_key_add(name='Basis', from_mix=True)
        else:
            sk = obj.shape_key_add(name='Basis', from_mix=False)

        # 从后向前删除形态键（除了最后一个）
        shape_keys = obj.data.shape_keys.key_blocks[:-1]
        for shape_key in reversed(shape_keys):
            obj.shape_key_remove(shape_key)
        # 这里最后再修改名字，无法像材质那样直接修改
        # 仅有Basis不会对文件体积造成影响
        if sk.name != 'Basis':
            sk.name = 'Basis'

    def process_vgs(self, obj):
        vertex_groups = obj.vertex_groups
        for vertex_group in reversed(vertex_groups):
            obj.vertex_groups.remove(vertex_group)

    def process_modifiers(self, obj, keep_first):
        modifiers = obj.modifiers
        if keep_first:
            modifiers_to_remove = modifiers[1:]
        else:
            modifiers_to_remove = modifiers
        for modifier in reversed(modifiers_to_remove):
            obj.modifiers.remove(modifier)

    def process_material(self, obj, create_default):
        obj.data.materials.clear()
        if not create_default:
            return
        mat = bpy.data.materials.new(name=obj.name)
        mat.use_nodes = True

        if mat.name != obj.name:
            mat.name = obj.name  # 不清楚为什么要设置两次...
            mat.name = obj.name
        if obj.data.materials:
            obj.data.materials[0] = mat  # assign to 1st material slot
        else:
            obj.data.materials.append(mat)  # no slots
        # 针对pmx模型处理
        pmx_root = find_pmx_root_with_child(obj)
        if not pmx_root:
            return
        match = PMX_NAME_PATTERN.match(obj.name)
        if match:
            original_name = match.group('name')
            mat.name = original_name
            mat.name = original_name
        modify_mmd_material(mat)

    def do_remove(self, pmx_root, props):
        pmx_armature = find_pmx_armature(pmx_root)
        pmx_objects = find_pmx_objects(pmx_armature)
        if not pmx_objects:
            return
        content_type = props.content_type
        create_default = props.create_default
        keep_first = props.keep_first
        keep_current = props.keep_current

        if content_type == 'MATERIAL':
            single_obj = pmx_objects[0]
            select_and_activate(single_obj)
            bpy.ops.mmd_tools.separate_by_materials()
            pmx_objects = find_pmx_objects(pmx_armature)  # 重新获取模型网格物体

        objs = get_obj_by_type(pmx_objects, content_type)
        for obj in objs:
            deselect_all_objects()
            select_and_activate(obj)
            if content_type == 'MATERIAL':
                self.process_material(obj, create_default)
            elif content_type == 'MODIFIER':
                self.process_modifiers(obj, keep_first)
            elif content_type == 'VERTEX_GROUP':
                self.process_vgs(obj)
            elif content_type == 'SHAPE_KEY':
                self.process_shape_keys(obj, keep_current)
            elif content_type == 'UV_MAP':
                self.process_uvs(obj, keep_first)


def get_obj_by_type(objs, content_type):
    # https://docs.blender.org/api/current/bpy_types_enum_items/object_type_items.html#rna-enum-object-type-items
    if content_type == 'MATERIAL':
        return [obj for obj in objs if obj.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME', 'GPENCIL']]
    elif content_type == 'MODIFIER':
        return [obj for obj in objs if obj.type in ['MESH', 'CURVE', 'SURFACE', 'FONT', 'VOLUME', 'LATTICE', 'GPENCIL']]
    elif content_type == 'VERTEX_GROUP':
        return [obj for obj in objs if obj.type in ['MESH']]
    elif content_type == 'SHAPE_KEY':
        return [obj for obj in objs if obj.type in ['MESH']]
    elif content_type == 'UV_MAP':
        return [obj for obj in objs if obj.type in ['MESH']]


def modify_mmd_material(material):
    if not material:
        return
    mmd_material = material.mmd_material
    # 非透视率
    mmd_material.alpha = 1
    # 反射强度
    mmd_material.shininess = 50
    # 扩散色
    mmd_material.diffuse_color = (1, 1, 1)
    # 反射色
    mmd_material.specular_color = (0, 0, 0)
    # 环境色
    mmd_material.ambient_color = (0.5, 0.5, 0.5)
    # 双面描绘
    mmd_material.is_double_sided = True
    # 地面阴影
    mmd_material.enabled_drop_shadow = True
    # 本影标示
    mmd_material.enabled_self_shadow_map = True
    # 本影
    mmd_material.enabled_self_shadow = True
    # 轮廓线
    mmd_material.enabled_toon_edge = True
    # 轮廓线颜色
    mmd_material.edge_color = (0, 0, 0, 1)
    # 轮廓线尺寸
    mmd_material.edge_weight = 1
    # 共用卡通纹理
    mmd_material.is_shared_toon_texture = False
    # 移除卡通纹理
    mmd_material.toon_texture = ""
    # 移除材质纹理
    bpy.ops.mmd_tools.material_remove_texture()
    # 移除球形纹理
    bpy.ops.mmd_tools.material_remove_sphere_texture()
    # 脚本
    mmd_material.comment = ""