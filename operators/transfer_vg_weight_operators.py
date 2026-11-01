import bpy

from ..utils import translate


class TransferVgWeightOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.transfer_vg_weight"  # 引用时的唯一标识符
    bl_label = "执行"  # 显示名称（F3搜索界面，不过貌似需要注册，和panel中显示的内容区别开）
    bl_description = "将选中对象的源顶点组的权重，转移到目标顶点组"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}
        self.transfer_weights(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def transfer_weights(self, context):
        """将选中对象的源顶点组的权重，转移到目标顶点组"""
        props = context.scene.mmd_kafei_tools_transfer_vg_weight
        source_vg_name = props.source_vg_name
        target_vg_name = props.target_vg_name
        selected_v_only = props.selected_v_only

        # 记录进入前的模式，处理完再恢复
        active_object = context.active_object
        mode = active_object.mode if active_object else "OBJECT"
        if mode != "OBJECT":
            bpy.ops.object.mode_set(mode='OBJECT')
        objs = [obj for obj in context.selected_objects if obj.type == 'MESH']
        total_moved = 0
        total_selected = 0

        try:
            for obj in objs:
                vgs = obj.vertex_groups

                # 如果源顶点组不存在，则跳过
                if source_vg_name not in vgs:
                    continue
                source_vg = vgs[source_vg_name]
                source_vg_index = source_vg.index

                # 目标顶点组在出现第一个可转移顶点时才创建，源组无权重时不留下空组
                target_vg = None
                target_vg_index = -1
                for vert in obj.data.vertices:
                    if selected_v_only:
                        if not vert.select:
                            continue
                        total_selected += 1
                    v_index = vert.index
                    groups = [vg.group for vg in vert.groups]  # vert.groups 返回顶点组id和对应权重（只读）
                    if source_vg_index not in groups:
                        continue
                    if target_vg is None:
                        if target_vg_name not in vgs:
                            obj.vertex_groups.new(name=target_vg_name)
                        target_vg = vgs[target_vg_name]
                        target_vg_index = target_vg.index
                    weight_s = source_vg.weight(v_index)    # 顶点在源顶点组中的顶点权重
                    if target_vg_index in groups:
                        weight_t = target_vg.weight(v_index)    # 顶点在目标顶点组中的顶点权重
                        # 正常情况下同一顶点的权重合计不超过 1，超出部分由 Blender 截断到 1.0
                        target_vg.add([v_index], weight_s + weight_t, 'REPLACE')
                    else:
                        target_vg.add([v_index], weight_s, 'ADD')
                    source_vg.remove([v_index])
                    total_moved += 1
        finally:
            # 恢复进入前的模式
            if mode != "OBJECT":
                bpy.ops.object.mode_set(mode=mode)

        if total_moved:
            self.report({'INFO'}, translate("权重转移完成"))
        elif selected_v_only and total_selected == 0:
            self.report(type={'WARNING'}, message=translate("未选中任何顶点"))
        else:
            self.report(type={'WARNING'}, message=translate("源顶点组中无顶点"))

    def check_props(self, context):
        props = context.scene.mmd_kafei_tools_transfer_vg_weight
        objs = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=translate("请至少选择一个网格对象！"))
            return False
        source_vg_name = props.source_vg_name
        if source_vg_name is None or source_vg_name == '':
            self.report(type={'ERROR'}, message=translate("请输入源顶点组名称！"))
            return False
        # 至少要有一个网格存在源顶点组，否则不会有任何权重被转移
        if not any(source_vg_name in obj.vertex_groups for obj in objs):
            self.report(type={'ERROR'}, message=translate("所选网格中不存在源顶点组！"))
            return False
        target_vg_name = props.target_vg_name
        if target_vg_name is None or target_vg_name == '':
            self.report(type={'ERROR'}, message=translate("请输入目标顶点组名称！"))
            return False
        if source_vg_name == target_vg_name:
            self.report(type={'ERROR'}, message=translate("源顶点组与目标顶点组名称相同！"))
            return False
        # mmd_tools 的两个特殊顶点组存放的不是普通蒙皮权重，不允许参与转移
        special_vgs = ("mmd_edge_scale", "mmd_vertex_order")
        if source_vg_name in special_vgs or target_vg_name in special_vgs:
            self.report(type={'ERROR'},
                        message=translate("不支持 mmd_edge_scale / mmd_vertex_order 顶点组！"))
            return False
        # 仅选中顶点依赖编辑模式中的顶点选择，需先进入编辑模式
        active_object = context.active_object
        if props.selected_v_only and (
                not active_object or active_object.type != 'MESH' or active_object.mode != 'EDIT'):
            self.report(type={'ERROR'}, message=translate("请进入编辑模式！"))
            return False
        return True
