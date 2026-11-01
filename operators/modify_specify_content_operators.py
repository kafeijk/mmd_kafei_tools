import math
import bpy

from ..constants import PMX_NAME_PATTERN

from ..utils import (
    alphanum_key,
    deselect_all_objects,
    find_ancestor,
    find_pmx_root_with_child,
    get_collection,
    get_mesh_objs,
    is_mmd_tools_enabled,
    restore_selection,
    select_and_activate,
)


class ModifySpecifyContentOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.modify_specify_content"
    bl_label = "执行"
    bl_description = "修改指定内容"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}
        self.modify_content(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self, context):
        """校验：至少选中一个对象"""
        if len(context.selected_objects) == 0:
            self.report(type={'ERROR'}, message=bpy.app.translations.pgettext_iface("请至少选择一个对象！"))
            return False
        return True

    def modify_content(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_specify_content

        # 记录选择状态
        active_object = context.active_object
        selected_objects = context.selected_objects

        content_type = props.content_type
        objs = get_obj_by_type(selected_objects, content_type)

        try:
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
            elif content_type == 'REMOVE_CONSTRAINT':
                self.remove_constraint(objs, props)
            elif content_type == 'REMOVE_VERTEX_GROUP':
                self.remove_vgs(objs, props)
            elif content_type == 'REMOVE_SHAPE_KEY':
                self.remove_shape_keys(objs, props)
            elif content_type == 'RESET_SHAPE_KEY':
                self.reset_shape_key_values(objs, props)
        finally:
            # 恢复选择状态（异常时同样恢复）
            restore_selection(selected_objects, active_object)

    def add_uv_map(self, objs, props):
        uv_name = props.uv_name
        average_islands_flag = props.average_islands_flag
        average_islands_list = []
        uv_render_map = {}

        # 以网格为单位处理，避免多个物体共用同一网格时重复新建UV
        meshes = {}
        for obj in objs:
            meshes[obj.data.as_pointer()] = obj.data

        # 新建uv
        for mesh_ptr, mesh in meshes.items():
            # 记录uv激活状态
            if mesh.uv_layers:
                active_render_index = next(i for i in range(len(mesh.uv_layers)) if mesh.uv_layers[i].active_render)
                uv_render_map[mesh_ptr] = (mesh.uv_layers.active_index, active_render_index)

            # 新建UV  name='',创建的名称为属性;如果不填写，创建的名称为UVMap
            if uv_name != '':
                new_uv = mesh.uv_layers.new(name=uv_name)
            else:
                new_uv = mesh.uv_layers.new()

            # 激活新建uv
            if new_uv:
                new_uv.active = True
                new_uv.active_render = True
                # 只有成功创建UV的网格才加入列表，否则后续操作会破坏其原始UV的布局
                average_islands_list.extend(obj for obj in objs if obj.data.as_pointer() == mesh_ptr)

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
        for mesh_ptr, mesh in meshes.items():
            if mesh.uv_layers and len(mesh.uv_layers) > 1:
                active_index, active_render_index = uv_render_map[mesh_ptr]
                mesh.uv_layers[active_index].active = True
                mesh.uv_layers[active_render_index].active_render = True
            mesh.update()

    def add_color_attribute(self, objs, props):
        """添加颜色属性：重名时由 Blender 自动追加数字后缀，名称为空时生成默认名称"""
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
            # 每个面角一份颜色：将 [R, G, B, A] 重复 len(mesh.loops) 次，
            color_values = list(color) * len(mesh.loops)
            color_attribute.data.foreach_set("color", color_values)

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
                    # 保留首个 UV 贴图
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
        mmd_tools_enabled = is_mmd_tools_enabled()
        for obj in objs:
            mesh = obj.data

            # 移除材质
            mesh.materials.clear()
            if not create_default:
                continue

            # PMX 模型去掉名称前缀（如 000_xxx → xxx）
            pmx_root = find_pmx_root_with_child(obj) if mmd_tools_enabled else None
            target_name = obj.name
            match = PMX_NAME_PATTERN.match(obj.name) if pmx_root else None
            if match:
                target_name = match.group('name')

            # 同名且无用户的旧材质会导致新建材质变成 xxx.001，先移除
            remove_orphan_material(target_name)

            # 新建默认材质
            mat = bpy.data.materials.new(name=target_name)

            if bpy.app.version < (5, 0, 0):  # Blender 5.0之后，use_nodes始终为True，之后将会被移除
                mat.use_nodes = True

            mesh.materials.append(mat)

            # 如果开启mmd_tools，进行额外调整
            if not pmx_root:
                continue

            modify_mmd_material(mat)

        # 转换材质
        if create_default and mmd_tools_enabled and any(obj.type == 'MESH' for obj in objs):
            deselect_all_objects()
            for obj in objs:
                obj.select_set(True)
            bpy.ops.mmd_tools.convert_materials()

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

    def remove_constraint(self, objs, props):
        """移除约束"""
        keep_first = props.keep_first
        for obj in objs:
            constraints = obj.constraints
            if keep_first:
                constraints_to_remove = constraints[1:]
            else:
                constraints_to_remove = constraints
            for constraint in reversed(constraints_to_remove):
                obj.constraints.remove(constraint)

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

    def reset_shape_key_values(self, objs, props):
        """
        Blender逻辑 -> 重置所有形态键权重为0，或最接近限制的值.
        当前逻辑 -> 重置所有形态键权重为0
        """
        for obj in objs:
            mesh = obj.data
            if not mesh.shape_keys:
                continue

            key_blocks = mesh.shape_keys.key_blocks

            for kb in key_blocks[1:]:  # 跳过 Basis 形态键（索引0），它是基础形状，不应被重置
                kb.slider_max = 1.0  # 先放开上限
                kb.slider_min = 0.0  # 再设下限，此时 0.0 < 1.0，合法
                kb.value = 0.0


def remove_orphan_material(name):
    """删除同名且无用户的材质，避免新建材质被自动重命名为 xxx.001"""
    material = bpy.data.materials.get(name)
    if material and material.users == 0:
        bpy.data.materials.remove(material)


def get_obj_by_type(objs, content_type):
    # https://docs.blender.org/api/current/bpy_types_enum_items/object_type_items.html#rna-enum-object-type-items
    mesh_only_types = {
        'REMOVE_VERTEX_GROUP',
        'REMOVE_SHAPE_KEY',
        'RESET_SHAPE_KEY',
        'ADD_UV_MAP',
        'REMOVE_UV_MAP',
        'ADD_COLOR_ATTRIBUTE',
        'REMOVE_COLOR_ATTRIBUTE',
    }

    if content_type == 'REMOVE_CONSTRAINT':
        # 物体级 constraints 属性对所有类型恒存在，这里只做能力校验；空集合删除时为空操作
        return [obj for obj in objs if hasattr(obj, "constraints")]

    if content_type == 'REMOVE_MODIFIER':
        # 同理 modifiers 属性恒存在；融球等无法添加修改器，空集合删除时为空操作
        return [obj for obj in objs if hasattr(obj, "modifiers")]

    if content_type == 'REMOVE_MATERIAL':
        # 按数据块是否支持材质判断，避免类型枚举随版本变化（如 GPENCIL → GREASEPENCIL）
        return [obj for obj in objs if obj.data is not None and hasattr(obj.data, "materials")]

    if content_type in mesh_only_types:
        return [obj for obj in objs if obj.type == 'MESH']

    return []


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
    # 脚本
    mmd_material.comment = ""


def create_curve(arrangement_type, radius):
    if arrangement_type == "CIRCLE":
        bpy.ops.curve.spirals(
            align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0),
            spiral_type='ARCH', steps=100, radius=radius, curve_type='BEZIER',
            edit_mode=False
        )
    elif arrangement_type == "ARC":
        bpy.ops.curve.simple(
            align='WORLD', location=(0, 0, 0), rotation=(0, 0, math.radians(45)),
            Simple_Type='Arc', Simple_endangle=90, Simple_sides=3, Simple_radius=radius,
            shape='2D', outputType='BEZIER', use_cyclic_u=False,
            handleType='VECTOR', edit_mode=False
        )
    return bpy.context.active_object


class ArrangeObjectOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.arrange_object"
    bl_label = "执行"
    bl_description = "排列物体"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}
        self.arrange_objects(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self, context):
        objs = context.selected_objects
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=bpy.app.translations.pgettext_iface("请至少选择一个对象！"))
            return False
        props = context.scene.mmd_kafei_tools_arrange_object
        arrangement_type = props.arrangement_type
        if arrangement_type in ["ARC", "CIRCLE"]:
            found = False
            for addon in context.preferences.addons.keys():
                # add_curve_extra_objects 3.6
                # extra_curve_objectes 4.2 4.5
                if "extra" in addon and "curve" in addon and "object" in addon:
                    found = True
                    break
            if not found:
                self.report({'ERROR'},
                            bpy.app.translations.pgettext_iface(
                                "请在偏好设置中启用 Extra Objects / Extra Curve Objects 插件"))
                return False
        return True

    def arrange_objects(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_arrange_object

        # 记录选择状态
        active_object = context.active_object
        selected_objects = context.selected_objects

        arrangement_type = props.arrangement_type
        direction = props.direction
        order = props.order
        start_x = props.start_trans[0]
        start_y = props.start_trans[1]
        start_z = props.start_trans[2]
        spacing_x = props.spacing[0]
        spacing_y = props.spacing[1]
        spacing_z = props.spacing[2]
        num_per_row = props.num_per_row
        threshold = props.threshold
        radius = props.radius
        num_per_circle = props.num_per_circle
        spacing_circle = props.spacing_circle
        offset = props.offset

        big_objs = []
        normal_objs = []

        # 获取选中物体的祖先节点（按选中顺序去重，保证 DEFAULT 排列顺序稳定）
        ancestors = []
        for obj in selected_objects:
            ancestor = find_ancestor(obj)
            if ancestor not in ancestors:
                ancestors.append(ancestor)

        # 分离大小物体
        normal_mesh_objs = []  # 与 normal_objs 一一对应，复用网格列表避免重复递归
        for ancestor in ancestors:
            if "arrangement" in ancestor.keys():
                continue
            mesh_objs = get_mesh_objs(ancestor)
            if has_big_obj(mesh_objs, threshold):
                big_objs.append(ancestor)
            else:
                normal_objs.append(ancestor)
                normal_mesh_objs.append(mesh_objs)

        # 对原来的选中物体按面数进行排序
        normal_objs_sorted = []
        if order in {"FACE_ASC", "FACE_DESC"}:
            # 计算每个对象的总面数：[(ancestor1,face_count1),(ancestor2,face_count2),...]
            obj_face_counts = []
            for ancestor, mesh_objs in zip(normal_objs, normal_mesh_objs):
                face_count = sum(len(mesh_obj.data.polygons) for mesh_obj in mesh_objs)
                obj_face_counts.append((ancestor, face_count))
            reverse = order == "FACE_DESC"
            obj_face_counts.sort(key=lambda x: x[1], reverse=reverse)
            normal_objs_sorted = [ancestor for ancestor, _ in obj_face_counts]
        elif order in {"NAME_ASC", "NAME_DESC"}:
            normal_objs_sorted = normal_objs.copy()
            reverse = order == "NAME_DESC"
            normal_objs_sorted.sort(key=lambda ancestor: alphanum_key(ancestor.name), reverse=reverse)
        elif order in {"SIZE_ASC", "SIZE_DESC"}:
            reverse = order == "SIZE_DESC"
            obj_size_list = [(ancestor, get_max_length(mesh_objs))
                             for ancestor, mesh_objs in zip(normal_objs, normal_mesh_objs)]
            obj_size_list.sort(key=lambda x: x[1], reverse=reverse)
            normal_objs_sorted = [ancestor for ancestor, _ in obj_size_list]
        elif order == "DEFAULT":
            normal_objs_sorted = normal_objs.copy()

        for ancestor in normal_objs_sorted:
            # 移除原先约束
            for constraint in ancestor.constraints:
                if constraint.type in {'FOLLOW_PATH', 'LOCKED_TRACK'}:
                    ancestor.constraints.remove(constraint)

        # 每次复用集合
        coll = get_collection("Controller Collection")
        for obj in coll.objects:
            if "arrangement" in obj.keys():
                bpy.data.objects.remove(obj, do_unlink=True)

        if arrangement_type == "ARRAY":
            for i, ancestor in enumerate(normal_objs_sorted):
                if direction == "HORIZONTAL":
                    row = i // num_per_row
                    col = i % num_per_row
                    x = start_x + col * spacing_x
                    y = start_y + row * spacing_y
                    ancestor.location = (x, y, 0)
                else:
                    row = i // num_per_row
                    col = i % num_per_row
                    x = start_x + col * spacing_x
                    z = start_z + row * spacing_z
                    ancestor.location = (x, 0, z)

            if len(coll.objects) == 0:
                bpy.data.collections.remove(coll)
        elif arrangement_type in ["ARC", "CIRCLE"]:
            # 在TMP_SCENE中预先创建圆弧/圆环，以解决性能问题
            curr_scene = context.scene
            tmp_scene = bpy.data.scenes.new("TMP_SCENE")
            try:
                context.window.scene = tmp_scene

                # 添加空物体作为锁定追踪目标
                bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
                empty = context.active_object
                empty.name = "Locked Track Target"
                empty["arrangement"] = "Locked Track Target"

                # 创建圆环
                curves = []
                num_circles = math.ceil(len(normal_objs_sorted) / num_per_circle)
                for i in range(num_circles):
                    curve = create_curve(arrangement_type, radius + i * spacing_circle)
                    curve["arrangement"] = "Curve"
                    curves.append(curve)
            finally:
                # 无论是否异常都切回原场景并删除临时场景，避免把用户留在临时场景
                context.window.scene = curr_scene
                bpy.data.scenes.remove(tmp_scene)
            # 恢复Link
            coll.objects.link(empty)
            for curve in curves:
                coll.objects.link(curve)

            curr_curve_character_index = 0
            curr_curve_index = 0
            for ancestor in normal_objs_sorted:
                if curr_curve_character_index >= num_per_circle:
                    curr_curve_character_index = 0
                    curr_curve_index += 1
                curr_curve = curves[curr_curve_index]
                # 位置归零，旋转暂不处理
                ancestor.location = (0, 0, 0)

                # 添加跟随路径约束
                follow_path_cons = ancestor.constraints.new(type='FOLLOW_PATH')
                follow_path_cons.target = curr_curve
                follow_path_cons.use_fixed_location = True

                if offset:
                    # (1 / num_per_circle) 一个身位
                    # (1 / num_per_circle) * unit   几分之一个身位
                    # ((curr_curve_index + (1 / unit)) % (1 / unit) 当前环数对(1 / unit)求模，使其结果小于(1 / unit)
                    # curr_offset 当前环所有物体共同的偏移量，其结果始终小于1个身位
                    unit = 0.25  # 暂不对外提供参数
                    curr_offset = (1 / num_per_circle) * unit * ((curr_curve_index + (1 / unit)) % (1 / unit))
                    offset_factor = curr_curve_character_index / num_per_circle + curr_offset
                else:
                    if arrangement_type == "ARC":
                        if num_per_circle == 1:
                            offset_factor = 0.5
                        else:
                            offset_factor = curr_curve_character_index / (num_per_circle - 1)
                    else:
                        offset_factor = curr_curve_character_index / num_per_circle
                offset_factor = 1 - offset_factor  # 使圆弧从左到右排列，不处理圆环实际左右情况
                follow_path_cons.offset_factor = offset_factor
                follow_path_cons.forward_axis = 'FORWARD_Y'
                follow_path_cons.up_axis = 'UP_Z'
                follow_path_cons.influence = 1

                locked_track_cons = ancestor.constraints.new(type='LOCKED_TRACK')
                locked_track_cons.target = empty
                locked_track_cons.track_axis = 'TRACK_NEGATIVE_Y'
                locked_track_cons.influence = 1

                curr_curve_character_index += 1

        # 排列X长度大于 threshold 的物体
        for ancestor in big_objs:
            ancestor.location = (0, 300, 0)

        # 恢复选中状态
        restore_selection(selected_objects, active_object)


def has_big_obj(objs, threshold):
    """任一网格对象在 X、Y 或 Z 方向上的尺寸超过阈值时返回 True"""
    for mesh_obj in objs:
        x_length = mesh_obj.dimensions[0]
        y_length = mesh_obj.dimensions[1]
        z_length = mesh_obj.dimensions[2]
        if x_length > threshold or y_length > threshold or z_length > threshold:
            return True
    return False


def get_max_length(objs):
    """返回所有网格对象在 X、Y、Z 三个方向上的最大尺寸"""
    max_length = 0
    for mesh_obj in objs:
        x_length = mesh_obj.dimensions[0]
        y_length = mesh_obj.dimensions[1]
        z_length = mesh_obj.dimensions[2]

        max_length = max(max_length, x_length)
        max_length = max(max_length, y_length)
        max_length = max(max_length, z_length)

    return max_length
