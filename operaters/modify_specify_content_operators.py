from ..utils import *


class ModifySpecifyContentOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.modify_specify_content"
    bl_label = "执行"
    bl_description = "修改指定内容"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_specify_content
        if not self.check_props(props):
            return

        # 记录选择状态
        active_object = bpy.context.active_object
        selected_objects = bpy.context.selected_objects

        content_type = props.content_type
        objs = get_obj_by_type(selected_objects, content_type)

        if content_type == 'ADD_UV_MAP':
            self.add_uv_map(objs, props)
        elif content_type == 'ADD_COLOR_ATTRIBUTE':
            self.add_color_attribute(objs, props)
        elif content_type == 'REMOVE_UV_MAP':
            self.remove_uvs(objs, props)
        elif content_type == 'REMOVE_COLOR_ATTRIBUTE':
            self.remove_color_attribute(objs, props)
        elif content_type == 'REMOVE_MATERIAL':
            self.remove_material(objs, props)
        elif content_type == 'REMOVE_MODIFIER':
            self.remove_modifiers(objs, props)
        elif content_type == 'REMOVE_VERTEX_GROUP':
            self.remove_vgs(objs, props)
        elif content_type == 'REMOVE_SHAPE_KEY':
            self.remove_shape_keys(objs, props)

        # 恢复选择状态
        restore_selection(selected_objects, active_object)

    def check_props(self, props):
        objs = bpy.context.selected_objects
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=f'Select at least one object!')
            return False
        return True

    def add_uv_map(self, objs, props):
        uv_name = props.uv_name
        average_islands_flag = props.average_islands_flag
        average_islands_list = []
        uv_render_map = {}

        # 新建uv
        for obj in objs:
            mesh = obj.data

            # 记录uv激活状态
            if mesh.uv_layers:
                active_render_index = next(i for i in range(len(mesh.uv_layers)) if mesh.uv_layers[i].active_render)
                uv_render_map[obj.name] = (mesh.uv_layers.active_index, active_render_index)

            # 新建UV  name='',创建的名称为属性;如果不填写，创建的名称为UVMap
            if uv_name != '':
                new_uv = mesh.uv_layers.new(name=uv_name)
            else:
                new_uv = mesh.uv_layers.new()

            # 激活新建uv
            if new_uv:
                new_uv.active = True
                new_uv.active_render = True
                # 只有成功创建UV的物体才会被添加进列表，否则后续操作会破坏其原始UV的布局
                average_islands_list.append(obj)
            else:
                # 达到可创建uv数量上限
                continue

        # 孤岛比例平均化
        if average_islands_flag and average_islands_list:
            deselect_all_objects()
            for obj in average_islands_list:
                select_and_activate(obj)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.average_islands_scale()
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')

        # 恢复uv激活状态
        for obj in objs:
            mesh = obj.data
            if mesh.uv_layers and len(mesh.uv_layers) > 1:
                mesh.uv_layers[uv_render_map[obj.name][0]].active = True
                mesh.uv_layers[uv_render_map[obj.name][1]].active_render = True
            mesh.update()

    def add_color_attribute(self, objs, props):
        """添加颜色属性，重名则覆盖（空串名称除外）"""
        name = props.color_attribute_name
        color = props.color

        for obj in objs:
            mesh = obj.data

            # 新建颜色属性
            color_attribute = mesh.color_attributes.new(
                name=name,
                type='BYTE_COLOR',
                domain='CORNER'
            )
            for loop in mesh.loops:
                color_attribute.data[loop.index].color = color

            mesh.update()

    def remove_uvs(self, objs, props):
        """移除uv"""
        keep_first = props.keep_first
        for obj in objs:
            mesh = obj.data

            if not mesh.uv_layers:
                continue

            for i in range(len(mesh.uv_layers) - 1, -1, -1):
                if keep_first and i == 0:
                    # 保留第一个颜色属性
                    continue
                uv = mesh.uv_layers[i]
                mesh.uv_layers.remove(uv)
            # https://blender.stackexchange.com/questions/163300/how-to-update-an-object-after-changing-its-uv-coordinates
            mesh.update()

    def remove_color_attribute(self, objs, props):
        """移除颜色属性"""
        keep_first = props.keep_first
        for obj in objs:
            mesh = obj.data

            if not mesh.color_attributes:
                continue

            for i in range(len(mesh.color_attributes) - 1, -1, -1):
                if keep_first and i == 0:
                    # 保留第一个颜色属性
                    continue
                attr = mesh.color_attributes[i]
                mesh.color_attributes.remove(attr)
            mesh.update()

    def remove_material(self, objs, props):
        """移除材质"""
        create_default = props.create_default
        for obj in objs:
            deselect_all_objects()
            select_and_activate(obj)
            mesh = obj.data

            # 移除材质
            mesh.materials.clear()
            if not create_default:
                continue

            # 新建默认材质
            mat = bpy.data.materials.new(name=obj.name)
            mat.use_nodes = True

            if mat.name != obj.name:
                mat.name = obj.name  # 不清楚为什么要设置两次...
                mat.name = obj.name
            if mesh.materials:
                mesh.materials[0] = mat  # assign to 1st material slot
            else:
                mesh.materials.append(mat)  # no slots

            # 如果开启mmd_tools，进行额外调整
            if not is_mmd_tools_enabled():
                continue
            # 针对pmx模型处理
            pmx_root = find_pmx_root_with_child(obj)
            if not pmx_root:
                continue
            match = PMX_NAME_PATTERN.match(obj.name)
            if match:
                original_name = match.group('name')
                mat.name = original_name
                mat.name = original_name
            modify_mmd_material(mat)

    def remove_modifiers(self, objs, props):
        """移除修改器"""
        keep_first = props.keep_first
        for obj in objs:
            modifiers = obj.modifiers
            if keep_first:
                modifiers_to_remove = modifiers[1:]
            else:
                modifiers_to_remove = modifiers
            for modifier in reversed(modifiers_to_remove):
                obj.modifiers.remove(modifier)

    def remove_vgs(self, objs, props):
        """移除顶点组"""
        keep_locked = props.keep_locked
        for obj in objs:
            vertex_groups = obj.vertex_groups
            for vertex_group in reversed(vertex_groups):
                if keep_locked and vertex_group.lock_weight:
                    continue
                obj.vertex_groups.remove(vertex_group)

    def remove_shape_keys(self, objs, props):
        """移除形态键"""
        keep_current = props.keep_current
        for obj in objs:
            mesh = obj.data
            if not mesh.shape_keys:
                continue

            # 创建形态键（保留/不保留当前形态）
            if keep_current:
                sk = obj.shape_key_add(name='Basis', from_mix=True)
            else:
                sk = obj.shape_key_add(name='Basis', from_mix=False)

            # 删除形态键，应用场景如删除形态键之后应用修改器
            # 是否保留首位的修改器？意义不大，blender会默认新建初始形态
            shape_keys = mesh.shape_keys.key_blocks[:-1]
            for shape_key in reversed(shape_keys):
                obj.shape_key_remove(shape_key)
            obj.shape_key_remove(sk)


def get_obj_by_type(objs, content_type):
    # https://docs.blender.org/api/current/bpy_types_enum_items/object_type_items.html#rna-enum-object-type-items
    if content_type == 'REMOVE_MATERIAL':
        return [obj for obj in objs if obj.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME', 'GPENCIL']]
    elif content_type == 'REMOVE_MODIFIER':
        return [obj for obj in objs if obj.type in ['MESH', 'CURVE', 'SURFACE', 'FONT', 'VOLUME', 'LATTICE', 'GPENCIL']]
    elif content_type == 'REMOVE_VERTEX_GROUP':
        return [obj for obj in objs if obj.type in ['MESH']]
    elif content_type == 'REMOVE_SHAPE_KEY':
        return [obj for obj in objs if obj.type in ['MESH']]
    elif content_type in ['ADD_UV_MAP', 'REMOVE_UV_MAP']:
        return [obj for obj in objs if obj.type in ['MESH']]
    elif content_type in ['ADD_COLOR_ATTRIBUTE', 'REMOVE_COLOR_ATTRIBUTE']:
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
