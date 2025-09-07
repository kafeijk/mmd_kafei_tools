from collections import defaultdict

from ..utils import *

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


class SmallFeatureOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.sf"
    bl_label = "执行"
    bl_description = "执行"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):

        scene = context.scene
        props = scene.mmd_kafei_tools_sf
        if self.check_props(props) is False:
            return

        option = props.option
        if option == 'SCENE_ROOT':
            self.gen_scene_root()
        elif option == "REMOVE_MISSING_DATA":
            self.remove_missing_external_data()
        elif option in ['SUBSURFACE_EV', 'SUBSURFACE_CY']:
            self.repair_sss(option)

    def remove_missing_external_data(self):
        """移除丢失的可打包外部数据（图像、字体、声音）"""

        def remove_if_missing(data_block):
            for item in list(data_block):
                if item.packed_file:
                    continue
                filepath = getattr(item, "filepath", "")
                if filepath and not os.path.exists(bpy.path.abspath(filepath)):
                    data_block.remove(item)

        remove_if_missing(bpy.data.images)
        remove_if_missing(bpy.data.fonts)
        remove_if_missing(bpy.data.sounds)

    def repair_sss(self, option):
        objs = bpy.context.selected_objects

        materials = get_materials(objs)
        for material in materials:
            if not is_valid_material(material):
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
            if len(result) > 0:
                self.report(type={'WARNING'},
                            message=bpy.app.translations.pgettext_iface("Affected materials: {}").format(result))
                self.report(type={'WARNING'},
                            message="Shader to RGB node detected! Results may be unpredictable. Click to view affected materials ↑↑↑")

    def gen_scene_root(self):
        """创建一个空物体，以实现对整个场景的统一控制"""
        if len(bpy.data.objects) == 0:
            return

        has_root = True
        root = find_ancestor(bpy.data.objects[0])
        for obj in bpy.data.objects:
            if root == find_ancestor(obj):
                continue
            has_root = False
            break

        if has_root:
            deselect_all_objects()
            select_and_activate(root)
            return

        root = bpy.data.objects.new("root", None)
        bpy.context.collection.objects.link(root)
        # 遍历场景中的物体
        for obj in bpy.data.objects:
            # 检查物体是否没有parent
            if obj.parent is None and obj != root:
                # 将其parent设置为root（保持变换）
                obj.parent = root
                obj.matrix_parent_inverse = root.matrix_world.inverted()
        # 选中root空物体
        deselect_all_objects()
        select_and_activate(root)

    def check_props(self, props):
        option = props.option
        if option in ['SUBSURFACE_EV', 'SUBSURFACE_CY']:
            objs = bpy.context.selected_objects
            if len(objs) == 0:
                self.report(type={'ERROR'}, message=f'Select at least one object!')
                return False
        return True


def is_valid_material(material):
    node_tree = material.node_tree
    if not node_tree:  # 有材质但无节点树
        return False

    nodes = node_tree.nodes
    if not nodes:  # 有节点树但无节点
        return False
    return True


def get_materials(objs):
    materials = []
    for obj in objs:
        if not obj.material_slots:  # 材质槽为空
            continue
        for slot in obj.material_slots:
            material = slot.material
            if not material:  # 有材质槽但无材质
                continue
            materials.append(material)
    return materials


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


class GroupObjectOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.group_object"
    bl_label = "执行"
    bl_description = "为网格对象分组"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.group_by_tex(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def group_by_tex(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_group_object

        selected_objects = bpy.context.selected_objects
        if len(selected_objects) == 0:
            self.report(type={'ERROR'}, message=f'Select at least one object!')
            return
        active_object = bpy.context.active_object
        if active_object is None:
            self.report(type={'ERROR'}, message=f'Activate the object!')
            return

        scope = props.scope
        search_type = props.search_type
        node_keywords = props.node_keywords
        img_keywords = props.img_keywords
        recursive = props.recursive

        ancestors = set()
        for obj in selected_objects:
            ancestor = find_ancestor(obj)
            if not ancestor:
                continue
            ancestors.add(ancestor)

        # 影响范围
        ancestor_objs = {}
        if scope == "ROOT":
            for ancestor in ancestors:
                objs = get_mesh_objs(ancestor)
                ancestor_objs[ancestor] = objs
        elif scope == "SELECTED_OBJECT":
            objs = bpy.context.selected_objects
            ancestor_objs[None] = objs

        # 关键词
        if search_type == "NODE_NAME":
            keywords = node_keywords
        else:
            keywords = img_keywords
        keyword_list = [keyword.lower().strip() for keyword in keywords.split(",")]

        # 记录 节点组 - 匹配节点列表 避免重复查询
        total_node_map = defaultdict(list)
        for ancestor, objs in ancestor_objs.items():
            img_objs = defaultdict(list)
            for obj in objs:
                if obj.type != "MESH":
                    continue
                if not obj.data.materials:
                    continue

                # 单物体所有材质匹配的贴图数量
                img_names = set()
                for mat in obj.data.materials:
                    # 跳过有材质槽但无材质的mat
                    if not mat:
                        continue

                    # 获取节点
                    if search_type == "NODE_NAME":
                        node_map = find_nodes(mat, keyword_list, total_node_map, by="node", recursive=recursive)

                    else:
                        node_map = find_nodes(mat, keyword_list, total_node_map, by="tex", recursive=recursive)

                    for node_tree_name, nodes in node_map.items():
                        if node_tree_name and node_tree_name not in total_node_map.keys():
                            total_node_map[node_tree_name].extend(nodes)
                        for node in nodes:
                            if node.image:
                                img_names.add(node.image.name)

                if len(img_names) == 1:
                    img_name = img_names.pop()
                    img_objs[img_name].append(obj)

            if ancestor:
                collection = ancestor.users_collection[0]
            else:
                collection = bpy.context.scene.collection

            for img_name, objs in img_objs.items():
                img_name = re.sub(r"\.\d+$", "", img_name)  # 去掉.xxx后缀
                coll_name = os.path.splitext(img_name)[0]
                # 检查是否已存在同名子集合
                # https://docs.blender.org/manual/en/latest/advanced/limits.html
                # Blender的ID限定在63个ASCII字符，所以image_name和collection_name限定长度是一致的，即使image_name名称被截断，也不影响collection的创建
                if coll_name in collection.children:
                    sub_col = collection.children[coll_name]
                else:
                    sub_col = bpy.data.collections.new(coll_name)
                    collection.children.link(sub_col)
                for obj in objs:
                    # 先把 obj 从所属集合里移除
                    for c in obj.users_collection:
                        c.objects.unlink(obj)

                    # 再加到新子集合
                    if obj.name not in sub_col.objects:
                        sub_col.objects.link(obj)
