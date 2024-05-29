import math
import random
import time

import bmesh
from mathutils import Vector

from ..utils import *


class TransferVgWeightOperators(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.transfer_vg_weight"  # 引用时的唯一标识符
    bl_label = "执行"  # 显示名称（F3搜索界面，不过貌似需要注册，和panel中显示的内容区别开）
    bl_description = "将源模型顶点组中顶点权重传递到目标模型上"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        main(self, context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成


def main(operator, context):
    """合并key和value对应的顶点组权重后，赋值给新建顶点组，命名为value，并移动到value所在位置"""
    # 检查指定的顶点组名称是否存在
    scene = context.scene
    props = scene.mmd_kafei_tools_transfer_vg_weight
    if check_props(operator, props) is False:
        return
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode='OBJECT')

    active_object = bpy.context.active_object
    objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    source_vg = props.source_vg
    target_vg = props.target_vg
    for index, obj in enumerate(objs):
        deselect_all_objects()
        select_and_activate(obj)
        vgs = obj.vertex_groups
        if source_vg not in vgs:
            print(
                f"源顶点组缺失，已跳过。权重转移进度：{index + 1}/{len(objs)}，当前物体：{obj.name}，源顶点组：{source_vg}，目标顶点组：{target_vg}")
            continue
        print(
            f"权重转移进度：{index + 1}/{len(objs)}，当前物体：{obj.name}，源顶点组：{source_vg}，目标顶点组：{target_vg}")
        if target_vg not in vgs:
            obj.vertex_groups.new(name=target_vg)

        # 构建合并后的临时顶点组名称
        merge_name = f"{source_vg}+{target_vg}"
        # 新建空的顶点组，用于储存合并的结果
        merge_vg = obj.vertex_groups.new(name=merge_name)

        # 合并顶点组权重
        for i, vert in enumerate(obj.data.vertices):
            available_groups = [v_group_elem.group for v_group_elem in vert.groups]
            source_weight = obj.vertex_groups[source_vg].weight(i) if obj.vertex_groups[
                                                                          source_vg].index in available_groups else 0
            target_weight = obj.vertex_groups[target_vg].weight(i) if obj.vertex_groups[
                                                                          target_vg].index in available_groups else 0
            merge_vg.add([i], source_weight + target_weight, 'REPLACE')  # 编辑模式下无法被调用

        # 重建源顶点组
        source_vg_index = obj.vertex_groups.find(source_vg)
        obj.vertex_groups.remove(obj.vertex_groups[source_vg])
        new_source_vg = obj.vertex_groups.new(name=source_vg)
        set_order(obj, new_source_vg.index, source_vg_index)

        # 将临时顶点组移动到指定位置并更名
        target_vg_index = obj.vertex_groups.find(target_vg)
        set_order(obj, merge_vg.index, target_vg_index)
        obj.vertex_groups.remove(obj.vertex_groups[target_vg])
        merge_vg.name = target_vg
    # 恢复选择状态
    for obj in objs:
        select_and_activate(obj)
    select_and_activate(active_object)


def set_order(obj, new_index, old_index):
    diff = new_index - old_index
    obj.vertex_groups.active_index = new_index
    for _ in range(abs(diff)):
        bpy.ops.object.vertex_group_move(direction='UP' if diff > 0 else 'DOWN')


def check_props(operator, props):
    objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    if len(objs) == 0:
        operator.report(type={'ERROR'}, message=f'请选择至少一个网格物体！')
        return False
    source_vg = props.source_vg
    if source_vg is None or source_vg == '':
        operator.report(type={'ERROR'}, message=f'请输入源顶点组！')
        return False
    target_vg = props.target_vg
    if target_vg is None or target_vg == '':
        operator.report(type={'ERROR'}, message=f'请输入目标顶点组！')
        return False
    if source_vg == target_vg:
        operator.report(type={'ERROR'}, message=f'源顶点组与目标顶点组相同！')
        return False
    return True
