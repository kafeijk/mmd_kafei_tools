from ..utils import *

if bpy.app.version < (4, 0, 0):
    SUBSURFACE = 'Subsurface'
else:
    SUBSURFACE = 'Subsurface Weight'


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
        if option == 'BAKE_BONE':
            self.select_bake_bone()
        elif option == 'PHYSICAL_BONE':
            self.select_physical_bone()
        elif option == 'INVALID_RIGIDBODY_JOINT':
            self.remove_invalid_rigidbody_joint()
        elif option == 'SCENE_ROOT':
            self.gen_scene_root()
        elif option in ['SUBSURFACE_EV', 'SUBSURFACE_CY']:
            self.repair_sss(option)

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
                self.report(type={'WARNING'}, message=f'受影响材质:{result}')
                self.report(type={'WARNING'},
                            message=f'检测到Shader To RGB节点，修改结果不可预期，点击查看受影响材质↑↑↑')

    def select_bake_bone(self):
        """选择用于烘焙VMD的骨骼"""
        obj = bpy.context.active_object
        pmx_root = find_pmx_root_with_child(obj)
        armature = find_pmx_armature(pmx_root)
        # 选中骨架并进入姿态模式
        deselect_all_objects()
        show_object(armature)
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='POSE')
        for bone in armature.pose.bones:
            if bone.mmd_bone.name_j in PMX_BAKE_BONES:
                bone.bone.select = True
            else:
                bone.bone.select = False

    def select_physical_bone(self):
        """选择用于烘焙VMD的骨骼"""
        obj = bpy.context.active_object
        root = find_pmx_root_with_child(obj)
        armature = find_pmx_armature(root)
        bl_names = get_physical_bone(root)
        # 选中骨架并进入姿态模式
        deselect_all_objects()
        show_object(armature)
        select_and_activate(armature)
        bpy.ops.object.mode_set(mode='POSE')
        for bone in armature.pose.bones:
            if bone.name in bl_names:
                bone.bone.select = True
            else:
                bone.bone.select = False

    def remove_invalid_rigidbody_joint(self):
        """选择用于烘焙VMD的骨骼"""
        obj = bpy.context.active_object
        root = find_pmx_root_with_child(obj)
        armature = find_pmx_armature(root)
        rigidbody_parent = find_rigid_body_parent(root)
        joint_parent = find_joint_parent(root)

        joint_rigid_bodies_map = {}

        # （预先）删除无效关节（并记录有效关节）
        for joint in reversed(joint_parent.children):
            rigidbody1 = joint.rigid_body_constraint.object1
            rigidbody2 = joint.rigid_body_constraint.object2
            if any(r not in rigidbody_parent.children for r in [rigidbody1, rigidbody2]):
                bpy.data.objects.remove(joint, do_unlink=True)
            else:
                joint_rigid_bodies_map[joint] = [rigidbody1, rigidbody2]

        # 处理刚体
        for rigidbody in reversed(rigidbody_parent.children):
            bl_name = rigidbody.mmd_rigid.bone
            # 当刚体没有关联的骨骼时，可能是本身设置错误，也可能是本来就没有关联的骨骼，这里不处理
            if not bl_name:
                continue
            # 关联骨骼不存在则删除这个刚体
            if bl_name not in armature.pose.bones:
                bpy.data.objects.remove(rigidbody, do_unlink=True)

        # 删除无效关节
        joints_to_remove = []
        for joint, rigid_bodies in joint_rigid_bodies_map.items():
            if any(not r for r in rigid_bodies):
                joints_to_remove.append(joint)
        for joint in reversed(joints_to_remove):
            bpy.data.objects.remove(joint, do_unlink=True)

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
        if option in ("BAKE_BONE", "PHYSICAL_BONE", "INVALID_RIGIDBODY_JOINT"):
            active_object = bpy.context.active_object
            if not active_object:
                self.report(type={'ERROR'}, message=f'请选择MMD模型！')
                return False
            pmx_root = find_pmx_root_with_child(active_object)
            if not pmx_root:
                self.report(type={'ERROR'}, message=f'请选择MMD模型！')
                return False
            armature = find_pmx_armature(pmx_root)
            if not armature:
                self.report(type={'ERROR'}, message=f'模型缺少骨架！')
                return False
            return True
        elif option in ['SUBSURFACE_EV', 'SUBSURFACE_CY']:
            objs = bpy.context.selected_objects
            if len(objs) == 0:
                self.report(type={'ERROR'}, message=f'请选择至少一个物体！')
                return


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
