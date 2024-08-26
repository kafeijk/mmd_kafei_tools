
from ..utils import *


class TransferVgWeightOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.transfer_vg_weight"  # 引用时的唯一标识符
    bl_label = "执行"  # 显示名称（F3搜索界面，不过貌似需要注册，和panel中显示的内容区别开）
    bl_description = "将选中对象的源顶点组的权重，转移到目标顶点组"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        """将选中对象的源顶点组的权重，转移到目标顶点组"""
        scene = context.scene
        props = scene.mmd_kafei_tools_transfer_vg_weight
        if self.check_props(props) is False:
            return

        source_vg_name = props.source_vg_name
        target_vg_name = props.target_vg_name

        if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode='OBJECT')

        # 记录选择状态
        active_object = bpy.context.active_object
        objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

        for index, obj in enumerate(objs):
            deselect_all_objects()
            select_and_activate(obj)
            vgs = obj.vertex_groups

            # 如果源顶点组不存在，则跳过；如果目标顶点组不存在，则新建
            if source_vg_name not in vgs:
                continue
            if target_vg_name not in vgs:
                obj.vertex_groups.new(name=target_vg_name)

            source_vg = vgs[source_vg_name]
            target_vg = vgs[target_vg_name]
            source_vg_index = source_vg.index
            target_vg_index = target_vg.index

            for vert in obj.data.vertices:
                v_index = vert.index
                groups = [vgs.group for vgs in vert.groups]  # vert.groups 返回顶点组id和对应权重（只读）
                if source_vg_index in groups:
                    weight_s = source_vg.weight(v_index)    # 顶点在源顶点组中的顶点权重
                    if target_vg_index in groups:
                        weight_t = target_vg.weight(v_index)    # 顶点在目标顶点组中的顶点权重
                        target_vg.add([v_index], weight_s + weight_t, 'REPLACE')
                    else:
                        target_vg.add([v_index], weight_s, 'ADD')
                    source_vg.remove([v_index])

        # 恢复选择状态
        deselect_all_objects()
        for obj in objs:
            select_and_activate(obj)
        select_and_activate(active_object)
        self.report({'INFO'}, "权重转移完成")

    def check_props(self, props):
        objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=f'请选择至少一个网格物体！')
            return False
        source_vg_name = props.source_vg_name
        if source_vg_name is None or source_vg_name == '':
            self.report(type={'ERROR'}, message=f'请输入源顶点组名称！')
            return False
        target_vg_name = props.target_vg_name
        if target_vg_name is None or target_vg_name == '':
            self.report(type={'ERROR'}, message=f'请输入目标顶点组名称！')
            return False
        if source_vg_name == target_vg_name:
            self.report(type={'ERROR'}, message=f'源顶点组与目标顶点组名称相同！')
            return False
        return True
