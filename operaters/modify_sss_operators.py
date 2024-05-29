from ..utils import *


class ModifySssOperators(bpy.types.Operator):
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

        for node in nodes:
            # 检查节点是否是BSDF节点
            if node.type == 'BSDF_PRINCIPLED' and not node.inputs["Subsurface"].is_linked:
                if node.inputs["Subsurface"].default_value == 0:
                    node.inputs["Subsurface"].default_value = 0.001
