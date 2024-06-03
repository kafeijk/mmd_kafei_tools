from ..utils import *


class ModifySssOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.modify_sss"
    bl_label = "修复"
    bl_description = "修复因次表面而产生的如皮肤颜色发青问题"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        main(self, context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成


def main(operator, context):
    # 不用限定obj的类型，默认都有material_slots属性
    # https://docs.blender.org/api/current/bpy.types.Object.html#bpy.types.Object.material_slots
    objs = bpy.context.selected_objects
    if len(objs) == 0:
        operator.report(type={'ERROR'}, message=f'请选择至少一个物体！')
        return

    material_set = set()
    # 获取待处理的材质
    for obj in objs:
        if not obj.material_slots:  # 材质槽为空
            continue
        for slot in obj.material_slots:
            material = slot.material
            if not material:  # 有材质槽但无材质
                continue
            material_set.add(material)

    for material in material_set:
        node_tree = material.node_tree
        if not node_tree:  # 有材质但无节点树
            continue

        nodes = node_tree.nodes
        if not nodes:  # 有节点树但无节点
            continue

        founded = False
        for node in nodes:
            # 检查节点是否是原理化BSDF节点
            if node.type == 'BSDF_PRINCIPLED':
                founded = True
                if not node.inputs["Subsurface"].is_linked:
                    if node.inputs["Subsurface"].default_value == 0:
                        node.inputs["Subsurface"].default_value = 0.001
        if not founded:
            # 找到材质输出节点
            output_node = None
            for node in nodes:
                if node.type == 'OUTPUT_MATERIAL':
                    output_node = node
                    break

            if output_node:
                # 在材质输出节点旁边创建一个混合着色器节点和一个次表面散射节点
                mix_shader_node = nodes.new(type='ShaderNodeMixShader')
                sss_node = nodes.new(type='ShaderNodeSubsurfaceScattering')

                # 调整位置
                output_node.location.x += 400
                mix_shader_node.location = output_node.location
                mix_shader_node.location.x -= 200
                sss_node.location = output_node.location
                sss_node.location.x -= 400
                sss_node.location.y -= 200

                # 找到连接到材质输出节点的socket
                for link in node_tree.links:
                    if link.to_node == output_node:
                        from_socket = link.from_socket
                        to_socket = link.to_socket

                        # 原先连到材质输出节点的节点连接到混合着色器上第一位
                        node_tree.links.new(from_socket, mix_shader_node.inputs[1])
                        # 次表面散射连到混合着色器第二位
                        node_tree.links.new(sss_node.outputs[0], mix_shader_node.inputs[2])
                        # 混合着色器的输出连到材质输出节点
                        node_tree.links.new(mix_shader_node.outputs[0], to_socket)
                        # 设置混合着色器的系数为0.001
                        mix_shader_node.inputs[0].default_value = 0.001
                        break
