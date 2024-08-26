from ..utils import *


class ModifySssOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.modify_sss"
    bl_label = "修复"
    bl_description = "修复因次表面而产生的问题"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        main(self, context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成


def is_valid_material(material):
    node_tree = material.node_tree
    if not node_tree:  # 有材质但无节点树
        return False

    nodes = node_tree.nodes
    if not nodes:  # 有节点树但无节点
        return False
    return True


def reset_bsdf_sss(nodes):
    for node in nodes:
        if node and node.type == 'BSDF_PRINCIPLED':
            if not node.inputs["Subsurface"].is_linked:
                node.inputs["Subsurface"].default_value = 0


def main(operator, context):
    # 不用限定obj的类型，默认都有material_slots属性
    # https://docs.blender.org/api/current/bpy.types.Object.html#bpy.types.Object.material_slots
    objs = bpy.context.selected_objects
    if len(objs) == 0:
        operator.report(type={'ERROR'}, message=f'请选择至少一个物体！')
        return
    scene = context.scene
    props = scene.mmd_kafei_tools_modify_sss
    strategy = props.strategy

    # 获取待处理的材质
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
            if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
                # 确认表面插槽是否被连接
                for link in node_tree.links:
                    if link.to_node == node and link.to_socket.name == "Surface":
                        output_node = node
                        linked_node = link.from_node
                        break
                if output_node:
                    break

        if output_node is None:
            continue

        if strategy == "RESET":
            reset_bsdf_sss(nodes)
        else:
            if strategy == "INTELLIGENCE":
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


def is_force_processed(node, node_tree):
    """如果强制处理过，则不再处理"""
    if node and node.type == 'MIX_SHADER':
        mix_shader_node = node
        # 检查混合着色器节点的第二个输入插槽是否连接到次表面散射节点
        sss_connected = False
        if mix_shader_node.inputs[2].is_linked:
            for link in node_tree.links:
                if link.to_socket == mix_shader_node.inputs[2]:
                    if link.from_node.type == 'SUBSURFACE_SCATTERING':
                        sss_connected = True
                        break
        if sss_connected and mix_shader_node.inputs[0].default_value < 0.002:
            return True
    return False


def process_bsdf(node):
    """处理原理化BSDF节点，只要类型是原理化BSDF，即返回True"""
    if node and node.type == 'BSDF_PRINCIPLED':
        if not node.inputs["Subsurface"].is_linked:
            if node.inputs["Metallic"].default_value >= 1:
                node.inputs["Metallic"].default_value = 0.999
            if node.inputs["Subsurface"].default_value == 0:
                node.inputs["Subsurface"].default_value = 0.001
        return True
    else:
        return False
