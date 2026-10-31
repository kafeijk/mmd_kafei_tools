import os
import re

from collections import defaultdict

import bpy

from ..utils import deselect_all_objects, find_ancestor, get_mesh_objs, select_and_activate, show_object


if bpy.app.version < (4, 0, 0):
    SUBSURFACE = 'Subsurface'
else:
    SUBSURFACE = 'Subsurface Weight'


def find_nodes(mat, names, total_node_map, by="node", recursive=False):
    """
    在材质 mat 中查找符合条件的节点
    by="node" -> 根据节点名称
    by="tex"  -> 根据贴图名称
    """
    node_map = defaultdict(list)

    if not mat or not mat.node_tree:
        return node_map

    def _match(node, keywords):
        """匹配规则"""
        if node.bl_idname != "ShaderNodeTexImage":
            return False
        if by == "node":
            return any(keyword in node.name.lower().strip() for keyword in keywords)
        elif by == "tex" and node.image:
            return any(keyword in node.image.name.lower().strip() for keyword in keywords)
        return False

    def _search(node_tree, node_tree_name=None):
        for node in node_tree.nodes:
            if _match(node, names):
                node_map[node_tree_name].append(node)
            if recursive and node.type == 'GROUP' and node.node_tree:
                if node.node_tree.name in total_node_map.keys():
                    node_map[node.node_tree.name] = total_node_map.get(node.node_tree.name)
                    continue
                _search(node.node_tree, node.node_tree.name)

    _search(mat.node_tree)
    return node_map


def split_keywords(text, keep_empty=False):
    """拆分关键词：中英文逗号均可作为分隔符，忽略大小写与空白；keep_empty=True 时保留空串"""
    keywords = [keyword.lower().strip() for keyword in re.split(r"[,，]", text)]
    if keep_empty:
        return keywords
    return [keyword for keyword in keywords if keyword]


def get_keywords(props):
    """按定位方式取关键词列表（忽略大小写；允许空串并进入搜索）"""
    text = props.node_keywords if props.search_type == "NODE_NAME" else props.img_keywords
    return split_keywords(text, keep_empty=True)


def get_scope_objs(context, scope):
    """按影响范围返回 {顶层祖先:待处理对象列表}"""
    if scope == "SELECTED_OBJECT":
        return {None: context.selected_objects}

    scope_objs = {}
    for obj in context.selected_objects:
        ancestor = find_ancestor(obj)
        if ancestor is None:
            continue
        # 同一祖先已收集过，跳过重复的递归查询
        if ancestor in scope_objs:
            continue
        scope_objs[ancestor] = get_mesh_objs(ancestor)
    return scope_objs


def get_group_parent_collection(context, ancestor):
    """获取分组挂载的父集合：优先祖先所在集合；祖先不在任何集合中时退回场景根集合"""
    if ancestor is None:
        return context.scene.collection
    if ancestor.users_collection:
        return ancestor.users_collection[0]
    return context.scene.collection


def collect_img_names(obj, keyword_list, by, recursive, node_cache, mat_cache):
    """收集单个物体所有材质中命中的贴图名称"""
    if obj.type != "MESH" or not obj.data.materials:
        return set()

    img_names = set()
    for mat in obj.data.materials:
        # 跳过有材质槽但无材质的mat
        if not mat:
            continue

        # 同一材质常被多个物体共用，按材质缓存节点查询结果避免重复扫描
        mat_key = mat.as_pointer()
        node_map = mat_cache.get(mat_key)
        if node_map is None:
            node_map = find_nodes(mat, keyword_list, node_cache, by=by, recursive=recursive)
            mat_cache[mat_key] = node_map

        for node_tree_name, nodes in node_map.items():
            # 节点组结果按名称缓存，避免同一节点组被重复遍历
            if node_tree_name and node_tree_name not in node_cache:
                node_cache[node_tree_name].extend(nodes)
            for node in nodes:
                if node.image:
                    img_names.add(node.image.name)

    return img_names


def group_objs_by_img(objs, keyword_list, by, recursive, node_cache, mat_cache):
    """按贴图分组：只处理恰好匹配到一张贴图的物体"""
    img_objs = defaultdict(list)
    for obj in objs:
        img_names = collect_img_names(obj, keyword_list, by, recursive, node_cache, mat_cache)
        if len(img_names) == 1:
            img_objs[img_names.pop()].append(obj)
    return img_objs


def get_image_sub_collection(parent, img_name):
    """按贴图名获取/创建子集合：去掉序号后缀与扩展名"""
    name = re.sub(r"\.\d+$", "", img_name)
    coll_name = os.path.splitext(name)[0]
    # https://docs.blender.org/manual/en/latest/advanced/limits.html
    # Blender的ID限定在63个ASCII字符，所以image_name和collection_name限定长度是一致的，即使image_name名称被截断，也不影响collection的创建
    if coll_name in parent.children:
        return parent.children[coll_name]

    sub_col = bpy.data.collections.new(coll_name)
    parent.children.link(sub_col)
    return sub_col


def move_obj_to_collection(obj, collection):
    """把物体从所有原集合移到目标集合"""
    for c in obj.users_collection:
        c.objects.unlink(obj)

    if obj.name not in collection.objects:
        collection.objects.link(obj)


class SceneRootOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.sf_scene_root"
    bl_label = "执行"
    bl_description = "创建场景控制器"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if not self.gen_scene_root(context):
            return {'CANCELLED'}
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def gen_scene_root(self, context):
        """创建一个空物体，以实现对整个场景的统一控制"""
        if len(bpy.data.objects) == 0:
            return False

        # 获取集合类型实例所依赖的源对象
        sources = set()
        for obj in bpy.data.objects:
            if is_collection_instance(obj):
                collection = obj.instance_collection
                for child in collection.objects:
                    sources.add(child)

        has_root = True
        root = next(obj for obj in bpy.data.objects if obj not in sources)
        root = find_ancestor(root)

        for obj in bpy.data.objects:
            if obj in sources:
                continue
            if root == find_ancestor(obj):
                continue
            has_root = False
            break

        if has_root:
            show_object(root)
            deselect_all_objects()
            select_and_activate(root)
            return True

        root = bpy.data.objects.new("root", None)
        root.location = context.scene.cursor.location.copy()
        context.collection.objects.link(root)

        context.view_layer.update()

        # 收集目标
        # 其中不论是本地实例化对象（集合类型），还是外部实例化对象（集合类型），均受root影响
        # 实例化所引用的源对象不受root影响，否则root影响源对象，源对象影响实例化对象，如果实例化对象本身有位移旋转，结果无法控制。
        # 如果先生成场景控制器，再生成集合类型实例，再生成场景控制器...这种绕过校验的生成行为，结果无法控制，不受支持。
        targets = [
            obj for obj in bpy.data.objects
            if obj.parent is None and obj != root and obj not in sources
        ]

        # 保存所有 world matrix
        world_mats = {
            obj: obj.matrix_world.copy()
            for obj in targets
        }

        # 统一设父级
        for obj in targets:
            obj.parent = root

        # 刷新depsgraph，否则恢复world无法生效
        context.view_layer.update()

        # 统一恢复 world
        for obj in targets:
            obj.matrix_world = world_mats[obj]

        # 选中root空物体
        deselect_all_objects()
        select_and_activate(root)
        return True


class RemoveMissingDataOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.sf_remove_missing_data"
    bl_label = "执行"
    bl_description = "移除丢失外部数据"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        removed = self.remove_missing_external_data()
        self.report(type={'INFO'},
                    message=bpy.app.translations.pgettext_iface("已移除 {} 个丢失的外部数据").format(removed))
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def remove_missing_external_data(self):
        """移除丢失的可打包外部数据（图像、字体、声音、影片剪辑、体积），返回移除数量"""
        data_blocks = (
            bpy.data.images,
            bpy.data.fonts,
            bpy.data.sounds,
            bpy.data.movieclips,
            bpy.data.volumes,
        )

        removed = 0
        for data_block in data_blocks:
            removed += self.remove_if_missing(data_block)
        return removed

    @staticmethod
    def remove_if_missing(data_block):
        """移除指定数据块集合中路径已丢失的项，返回移除数量"""
        removed = 0
        for item in list(data_block):
            # 已打包的数据不依赖外部路径
            if getattr(item, "packed_file", None):
                continue
            filepath = getattr(item, "filepath", "")
            if filepath and not os.path.exists(bpy.path.abspath(filepath)):
                data_block.remove(item)
                removed += 1
        return removed


class RepairSSSOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.sf_repair_sss"
    bl_label = "执行"
    bl_description = "修复Eevee显示泛蓝 / 修复Cycles显示模糊"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if len(context.selected_objects) == 0:
            self.report(type={'ERROR'}, message=bpy.app.translations.pgettext_iface("请至少选择一个对象！"))
            return {'CANCELLED'}
        props = context.scene.mmd_kafei_tools_sf
        self.repair_sss(context, props.option)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def repair_sss(self, context, option):
        objs = context.selected_objects

        materials = get_materials(objs)
        for material in materials:
            if not has_node_tree_nodes(material):
                continue

            node_tree = material.node_tree
            nodes = node_tree.nodes

            # 找到当前被使用的材质输出节点
            output_node = None
            linked_node = None
            for node in nodes:
                if node.bl_idname == 'ShaderNodeOutputMaterial' and node.is_active_output:
                    # 确认表面插槽是否被连接
                    for link in node_tree.links:
                        if link.to_node == node and link.to_socket.name == 'Surface':
                            output_node = node
                            linked_node = link.from_node
                            break
                    if output_node:
                        break
            if output_node is None:
                continue

            if option == "SUBSURFACE_CY":
                reset_bsdf_sss(nodes)
            elif option == "SUBSURFACE_EV":
                # 处理原理化BSDF节点
                processed = process_bsdf(linked_node)
                if processed:
                    continue

                # 如果已经强制处理过，则不再处理
                processed = is_force_processed(linked_node, node_tree)
                if processed:
                    continue

                # 强制处理
                force_process(node_tree, output_node)
        if option == "SUBSURFACE_EV":
            result = check_material_node_existing_by_type(materials, "ShaderNodeShaderToRGB")
            if result:
                self.report(type={'WARNING'},
                            message=bpy.app.translations.pgettext_iface("Affected materials: {}").format(", ".join(result)))
                self.report(type={'WARNING'},
                            message=bpy.app.translations.pgettext_iface(
                                "Shader to RGB node detected! Results may be unpredictable. Click to view affected materials ↑↑↑"))


def is_collection_instance(obj):
    """校验物体是否属于实例化集合"""
    return (
            obj
            and obj.type == 'EMPTY'
            and obj.instance_type == 'COLLECTION'
            and obj.instance_collection is not None
    )


def has_node_tree_nodes(material):
    """判断材质是否存在节点树且节点非空"""
    node_tree = material.node_tree
    if not node_tree:  # 有材质但无节点树
        return False

    nodes = node_tree.nodes
    if not nodes:  # 有节点树但无节点
        return False
    return True


def get_materials(objs):
    """收集物体的材质，按材质自身去重（同一材质常被多个物体/材质槽共用）"""
    materials = {}
    for obj in objs:
        for slot in obj.material_slots:
            material = slot.material
            if not material:  # 有材质槽但无材质
                continue
            materials[material.as_pointer()] = material
    return list(materials.values())


def reset_bsdf_sss(nodes):
    for node in nodes:
        if node and node.bl_idname == 'ShaderNodeBsdfPrincipled':
            if not node.inputs[SUBSURFACE].is_linked:
                node.inputs[SUBSURFACE].default_value = 0


def process_bsdf(node):
    """处理原理化BSDF节点，只要类型是原理化BSDF，即返回True"""
    if node and node.bl_idname == 'ShaderNodeBsdfPrincipled':
        if not node.inputs[SUBSURFACE].is_linked:
            if node.inputs["Metallic"].default_value >= 1:
                node.inputs["Metallic"].default_value = 0.999
            if node.inputs[SUBSURFACE].default_value == 0:
                node.inputs[SUBSURFACE].default_value = 0.001
        return True
    else:
        return False


def is_force_processed(node, node_tree):
    """如果强制处理过，则不再处理"""
    if node and node.bl_idname == 'ShaderNodeMixShader':
        mix_shader_node = node
        # 检查混合着色器节点的第二个输入插槽是否连接到次表面散射节点
        sss_connected = False
        if mix_shader_node.inputs[2].is_linked:
            for link in node_tree.links:
                if link.to_socket == mix_shader_node.inputs[2]:
                    if link.from_node.bl_idname == 'ShaderNodeSubsurfaceScattering':
                        sss_connected = True
                        break
        if sss_connected and mix_shader_node.inputs[0].default_value < 0.002:
            return True
    return False


# 类型 https://docs.blender.org/api/current/bpy.types.ShaderNode.html#bpy.types.ShaderNode
# 节点 https://docs.blender.org/api/current/bpy.types.Node.html#bpy.types.Node.type
def check_material_node_existing_by_type(materials, node_type):
    """校验指定类型节点是否被材质使用"""
    # 节点组 -> 是否含有指定类型节点
    checked_groups = {}
    results = []

    def check_nodes(nodes, checked_groups):
        for node in nodes:
            # 如果节点类型匹配，则立即返回
            if node.bl_idname == node_type:
                return True

            # 如果是节点组，检查组内的节点
            if node.bl_idname == 'ShaderNodeGroup' and node.node_tree:
                node_tree_id = id(node.node_tree)

                # 如果节点组已经被校验过
                if node_tree_id in checked_groups:
                    if checked_groups[node_tree_id]:
                        return True  # 匹配则立即返回
                    else:
                        continue  # 不匹配则跳过该节点的检查

                # 检查该组内的节点，并记录结果
                checked_groups[node_tree_id] = check_nodes(node.node_tree.nodes, checked_groups)

                # 如果匹配则立即返回
                if checked_groups[node_tree_id]:
                    return True

        return False

    # 检查每个材质中的节点树
    for material in materials:
        node_tree = material.node_tree
        if node_tree:
            if check_nodes(node_tree.nodes, checked_groups):
                results.append(material.name)
    return results


def force_process(node_tree, output_node):
    """强制处理"""
    nodes = node_tree.nodes
    mix_shader_node = nodes.new(type='ShaderNodeMixShader')  # 混合着色器
    sss_node = nodes.new(type='ShaderNodeSubsurfaceScattering')  # SSS着色器

    # 调整节点位置
    output_node.location.x += 400
    mix_shader_node.location = output_node.location
    mix_shader_node.location.x -= 200
    sss_node.location = output_node.location
    sss_node.location.x -= 400
    sss_node.location.y -= 200

    # 找到连接到材质输出节点的socket
    for link in node_tree.links:
        if link.to_node == output_node and link.to_socket.name == "Surface":
            from_socket = link.from_socket
            to_socket = link.to_socket

            # 原先连到“材质输出”的节点更改为连接到“混合着色器”的第1个槽中
            node_tree.links.new(from_socket, mix_shader_node.inputs[1])
            # “SSS着色器”连到“混合着色器”的第2个槽中
            node_tree.links.new(sss_node.outputs[0], mix_shader_node.inputs[2])
            # “混合着色器”的输出连到“材质输出”节点的表（曲）面上
            node_tree.links.new(mix_shader_node.outputs[0], to_socket)
            # 设置“混合着色器”的系数为0.001
            mix_shader_node.inputs[0].default_value = 0.001
            return True
    return False


class ModifyColorspaceOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.modify_colorspace"
    bl_label = "执行"
    bl_description = "修改贴图色彩空间"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_colorspace

        source_colorspace = props.source_colorspace
        target_colorspace = props.target_colorspace
        keyword_list = split_keywords(props.keywords)

        for image in bpy.data.images:
            if keyword_list:
                if any(keyword in image.name.lower().strip() for keyword in keyword_list):
                    # 修改图像的色彩空间
                    image.colorspace_settings.name = target_colorspace
            else:
                if image.colorspace_settings.name == source_colorspace:
                    image.colorspace_settings.name = target_colorspace


class GroupObjectOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.group_object"
    bl_label = "执行"
    bl_description = "为网格对象分组"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if not self.group_by_tex(context):
            return {'CANCELLED'}
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def group_by_tex(self, context):
        if not self.check_props(context):
            return False

        props = context.scene.mmd_kafei_tools_group_object
        keyword_list = get_keywords(props)
        by = "node" if props.search_type == "NODE_NAME" else "tex"
        # 节点组缓存 + 材质缓存，避免同一节点组/材质被重复查询
        node_cache = defaultdict(list)
        mat_cache = {}

        for ancestor, objs in get_scope_objs(context, props.scope).items():
            img_objs = group_objs_by_img(objs, keyword_list, by, props.recursive, node_cache, mat_cache)
            parent = get_group_parent_collection(context, ancestor)
            for img_name, img_objs_group in img_objs.items():
                sub_col = get_image_sub_collection(parent, img_name)
                for obj in img_objs_group:
                    move_obj_to_collection(obj, sub_col)

        return True

    def check_props(self, context):
        """校验：至少选中一个物体"""
        if not context.selected_objects:
            self.report(type={'ERROR'}, message=bpy.app.translations.pgettext_iface("请至少选择一个对象！"))
            return False
        return True
