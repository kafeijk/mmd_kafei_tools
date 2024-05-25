import math

import bmesh

from ..utils import *


class TransferPmxToAbcOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.transfer_pmx_to_abc"  # 引用时的唯一标识符
    bl_label = "传递"  # 显示名称（F3搜索界面，不过貌似需要注册，和panel中显示的内容区别开）
    bl_description = "将pmx模型的材质传递到abc模型上"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        main(self, context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成


def main(operator, context):
    # 获取abc和pmx对应的mesh对象并生成字典
    pmx_root = find_pmx_root()
    if pmx_root is None:
        operator.report(type={'WARNING'}, message=f'没有找到pmx对象')
        return
    pmx_armature = find_pmx_armature(pmx_root)
    if pmx_armature is None:
        operator.report(type={'WARNING'}, message=f'在{pmx_root.name}中没有找到pmx骨架')
        return
    pmx_objects = find_pmx_objects(pmx_armature)
    if len(pmx_objects) == 0:
        operator.report(type={'WARNING'}, message=f'在{pmx_root.name}中没有找到网格对象')
        return
    abc_objects = find_abc_objects()
    if len(abc_objects) == 0:
        operator.report(type={'WARNING'}, message=f'没有找到abc文件对应的网格对象')
        return

    scene = context.scene
    props = scene.mmd_kafei_tools_transfer_pmx_to_abc

    toon_shading_flag = props.toon_shading_flag
    face_locator = props.face_locator
    outline_width = props.outline_width

    sort_pmx_objects(pmx_objects)
    sort_abc_objects(abc_objects)
    pmx2abc_mapping = dict(zip(pmx_objects, abc_objects))

    # 考虑到可能会对pmx的网格物体进行隐藏（如多套衣服、耳朵、尾巴、皮肤冗余处等），处理时需要将这些物体取消隐藏使其处于可选中的状态，处理完成后恢复
    # 记录pmx和abc物体的可见性
    visibility_map = {}
    for source, target in pmx2abc_mapping.items():
        visibility_map[source] = (source.hide_select, source.hide_get(), source.hide_viewport, source.hide_render)
        visibility_map[target] = (target.hide_select, target.hide_get(), target.hide_viewport, target.hide_render)
    for source, target in pmx2abc_mapping.items():
        set_visibility(source, False, False, False, False)
        set_visibility(target, False, False, False, False)

    # 关联pmx材质到abc上面
    link_materials(operator, pmx2abc_mapping)

    # 关联pmx材质到abc上面（多材质槽情况下）
    multi_material_slots_flag = props.multi_material_slots_flag
    if multi_material_slots_flag:
        link_multi_slot_materials(operator, pmx2abc_mapping)

    # 为每个abc网格对象赋予顶点色，新建uv并使这些uv孤岛比例平均化
    gen_skin_uv_flag = props.gen_skin_uv_flag
    if gen_skin_uv_flag:
        skin_uv_name = props.skin_uv_name
        gen_skin_uv(operator, pmx2abc_mapping, skin_uv_name)

    # 关联pmx顶点组及顶点权重到abc上面（正序）
    vgs_flag = props.vgs_flag
    if vgs_flag:
        link_vertices_group(pmx2abc_mapping)
        link_vertices_weight(pmx2abc_mapping)

    # 复制pmx修改器到abc上面（同时保留网格序列缓存修改器，删除骨架修改器）
    modifiers_flag = props.modifiers_flag
    if modifiers_flag:
        link_modifiers(pmx2abc_mapping)

    # 恢复原有可见性
    for obj, visibility in visibility_map.items():
        set_visibility(obj, visibility[0], visibility[1], visibility[2], visibility[3])


def get_mesh_objects(obj):
    """获取空物体下面的mesh对象，顺序为大纲顺序"""
    mesh_objects = [obj] if obj.type == 'MESH' else []
    for child in obj.children:
        if child.type in {'ARMATURE', 'MESH'}:
            mesh_objects.extend(get_mesh_objects(child))
    return mesh_objects


def modifiers_by_name(obj, name):
    """ 通过名称获取修改器 """
    return [x for x in obj.modifiers if x.name == name]


def modifiers_by_type(obj, typename):
    """ 通过类型获取修改器 """
    return [x for x in obj.modifiers if x.type == typename]


def link_materials(operator, mapping):
    """关联source材质到target上面"""
    for source, target in mapping.items():
        source_mesh = source.data
        target_mesh = target.data
        if len(source_mesh.uv_layers) == 0:
            continue
        # 如果loop值不一致，则跳过本次循环，但这不意味着错误
        # 比如3.x导入abc复制uv出问题，用2.x导入并拷贝到当前工程，执行插件依然可以进行后续逻辑
        if len(source_mesh.loops) != len(target_mesh.loops):
            operator.report(type={'WARNING'},
                            message=f'传递材质时未能成功复制UV，请检查。'
                                    f'源物体：{source.name}，loops：{len(source_mesh.loops)}，面数：{len(source_mesh.polygons)}。'
                                    f'目标物体：{target.name}，loops：{len(target_mesh.loops)}，面数：{len(target_mesh.polygons)}')
            continue
        # 记录源物体活动的UV、用于渲染的UV、原始uv数量
        source_uv_active_index = source_mesh.uv_layers.active_index
        source_uv_render_index = 0
        for index, uv_layer in enumerate(source_mesh.uv_layers):
            if uv_layer.active_render:
                source_uv_render_index = index
        source_original_uv_count = len(source_mesh.uv_layers)
        # 记录目标物体原始uv数量
        target_original_uv_count = len(target_mesh.uv_layers)

        for uv_layer in source.data.uv_layers:
            # 复制UV时，复制的是活动状态的UV
            uv_layer.active = True
            # 新建uv
            # blender 3.0以下（如2.93）导入abc，uv命名是"uv"，而不是"UVMap"
            # 所以除非刻意进行额外操作，否则出现"UV名称已存在（或者说UV命名冲突，不过实际名称会自动修改并不会冲突）"的问题的可能性很低，这里对此种情况暂不处理。
            # pmx对象最多5个uv，abc对象1个uv（3.0以下导入时），通常情况下，不会超过8个的上限，如超过，这里对此种情况暂不处理。
            new_uv = target_mesh.uv_layers.new(name=uv_layer.name)
            if new_uv is None:
                # 目标物体uv数量达到上限，给予提示
                operator.report(type={'WARNING'},
                                message=f'传递材质时未能成功复制UV，请检查。目标物体：{target.name}，目标物体UV数量：{len(target.data.uv_layers)}。'
                                        f'源物体UV名称：{uv_layer.name}')
                continue
            target_mesh.uv_layers[uv_layer.name].active = True

            deselect_all_objects()
            # 选中并激活target对象
            select_and_activate(target)
            # 选中并激活source对象
            select_and_activate(source)
            # 复制UV贴图
            bpy.ops.object.join_uvs()
            # 关联材质
            bpy.ops.object.make_links_data(type='MATERIAL')

        # 恢复uv的激活状态
        source_mesh.uv_layers[source_uv_active_index].active = True
        source_mesh.uv_layers[source_uv_render_index].active_render = True
        target_current_uv_count = len(target_mesh.uv_layers)
        # 目标物体原始UV数量为0，且全部复制成功
        if target_original_uv_count == 0 and target_current_uv_count == source_original_uv_count:
            target_mesh.uv_layers[source_uv_active_index].active = True
            target_mesh.uv_layers[source_uv_render_index].active_render = True
        # 目标物体原始UV数量不为0，且全部复制成功
        elif target_original_uv_count != 0 and target_current_uv_count == (
                source_original_uv_count + target_original_uv_count):
            target_mesh.uv_layers[source_uv_active_index + target_original_uv_count].active = True
            target_mesh.uv_layers[source_uv_render_index + target_original_uv_count].active_render = True
        else:
            # 要么不复制，要么全部复制成功，其它情况，这里暂不考虑
            pass
    deselect_all_objects()


def gen_skin_uv(operator, mapping, skin_uv_name):
    """为每个网格对象赋予顶点色，新建uv并使这些uv孤岛比例平均化"""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode='OBJECT')

    # 记录各物体原始的活动的uv及用于渲染的uv
    obj_active_uv_map = {}
    obj_render_uv_map = {}
    for _, target in mapping.items():
        for index, uv_layer in enumerate(target.data.uv_layers):
            if uv_layer.active:
                obj_active_uv_map[target.name] = index
            if uv_layer.active_render:
                obj_render_uv_map[target.name] = index

    # 待执行孤岛比例平均化的对象列表
    candidate_objs = []
    for _, target in mapping.items():
        deselect_all_objects()
        # 进入顶点绘制模式再返回物体模式
        select_and_activate(target)
        bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        bpy.ops.object.mode_set(mode='OBJECT')
        # 新建并激活uv
        target_mesh = target.data
        new_uv = target_mesh.uv_layers.new(name=skin_uv_name)
        if new_uv:
            new_uv.active = True
            new_uv.active_render = True
            # 只有成功创建UV的物体才会被添加进列表，否则后续操作会破坏其原始UV的布局
            candidate_objs.append(target)
        else:
            operator.report(type={'WARNING'},
                            message=f'未能成功创建皮肤UV，请检查。物体：{target.name}，当前UV数量：{len(target.data.uv_layers)}')

    # 孤岛比例平均化
    deselect_all_objects()
    for candidate_obj in candidate_objs:
        select_and_activate(candidate_obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    # 恢复各物体原始的活动的uv及用于渲染的uv，未成功创建UV的物体无需恢复
    for candidate_obj in candidate_objs:
        candidate_mesh = candidate_obj.data
        active_uv_index = obj_active_uv_map[candidate_obj.name]
        render_uv_index = obj_render_uv_map[candidate_obj.name]
        candidate_mesh.uv_layers[active_uv_index].active = True
        candidate_mesh.uv_layers[render_uv_index].active_render = True


def link_vertices_group(mapping):
    """关联source指定顶点组之后的顶点组到target上面（正序）
    todo 更稳妥的方式是溜一遍pose bone，去除pose bone和mmd标识顶点组之后的内容为要关联的内容"""
    for source, target in mapping.items():
        source_vgs = source.vertex_groups
        mmd_vertex_order_flag = False
        for source_vg in source_vgs:
            if source_vg.name == 'mmd_vertex_order':
                mmd_vertex_order_flag = True
                continue
            if mmd_vertex_order_flag:
                target.vertex_groups.new(name=source_vg.name)


def link_vertices_weight(mapping):
    """关联pmx顶点组权重到abc上面"""
    for source, target in mapping.items():
        deselect_all_objects()
        source_vgs = source.vertex_groups
        for source_vg in reversed(source_vgs):
            if source_vg.name == 'mmd_vertex_order':
                break
            # 激活target对象的顶点组
            select_and_activate(source)
            bpy.ops.object.vertex_group_set_active(group=source_vg.name)
            # 获取target对象的顶点组中的顶点、权重信息
            verts_and_weights = get_vertices_and_weights(source, source_vg)
            select_and_activate(target)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            mesh = target.data
            bm = bmesh.from_edit_mesh(mesh)

            vert_group_map = {}  # 用于存储顶点和对应的顶点组信息
            bpy.ops.mesh.select_mode(type="VERT")
            for poly in bm.faces:
                for vert in poly.verts:
                    vert_world_pos = target.matrix_world @ vert.co
                    vert_key = str(vert_world_pos)
                    if vert_key in verts_and_weights:
                        vert.select = True
                        vert_group_name, weight = verts_and_weights[vert_key]
                        vert_group_map[vert.index] = (vert_group_name, weight)
            bmesh.update_edit_mesh(mesh)
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            for vert_index, (vert_group_name, weight) in vert_group_map.items():
                vg = target.vertex_groups.get(vert_group_name)
                if not vg:
                    vg = target.vertex_groups.new(name=vert_group_name)
                vg.add([vert_index], weight, 'REPLACE')


def get_vertices_and_weights(obj, vertex_group):
    """获取顶点组中的顶点及其权重map"""
    verts_and_weights = {}
    mesh = obj.data
    vertex_group_index = obj.vertex_groups.find(vertex_group.name)
    if vertex_group_index != -1:
        for vert in mesh.vertices:
            for group_element in vert.groups:
                if group_element.group == vertex_group_index:
                    verts_and_weights[str(obj.matrix_world @ vert.co)] = (vertex_group.name, group_element.weight)
                    break
    return verts_and_weights


def truncate(value, precision):
    """对值÷精度后的结果进行截断，返回整数部分"""
    return math.floor(value / precision)


def link_multi_slot_materials(operator, mapping):
    """关联pmx材质到abc上面（多材质槽情况下）"""
    # 坐标精度，不建议让用户修改这个值
    precision = 0.0001
    for source, target in mapping.items():
        # 没有active_object直接mode_set会报异常
        if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode='OBJECT')
        deselect_all_objects()
        select_and_activate(source)

        # 通过面的质心坐标（局部）来确定源和目标的映射关系，以此来关联材质
        # 模型可能会存在重合面，导致质心位置相同
        # 但是pmx模型的肌和体，要么分属不同的网格对象，要么属于同一网格对象的不同面
        # 不论是哪种情况，重合面都不会对最终的结果产生影响（如有其它普遍且未考虑进来的情况再说）

        # 获取源物体网格数据
        source_mesh = source.data
        # 源物体质心与面的map
        source_center_poly_map = {}
        # 源物体面与对应材质的map
        source_poly_material_map = {}
        for source_poly in source_mesh.polygons:
            source_poly_material_map[source_poly.index] = source_poly.material_index

            # 将质心坐标（局部）进行精度误差处理，得到的结果保存在map中。
            # 如果不进行精度误差处理，直接将poly.center作为key，坐标值只会保留小数点后4位。（以四舍五入的方式）
            # 首先想到的是增加精度，获取更后面的值，直到完整获取整个数值以避免四舍五入，但是这样会产生精度丢失的问题
            # 实际的值非常不可控，所以才要四舍五入吧，但问题的原因不是四舍五入，而是存在误差
            # 事实上，保留小数点后四位已经足够了，但个别面的质心坐标值依然存在误差。
            # 这里对坐标值 / precision后的结果进行截断，保留整数，误差为±1。
            for i in range(-1, 2):
                for j in range(-1, 2):
                    for k in range(-1, 2):
                        key = (
                            truncate(source_poly.center.x, precision) + i * 1,
                            truncate(source_poly.center.y, precision) + j * 1,
                            truncate(source_poly.center.z, precision) + k * 1)
                        source_center_poly_map[key] = source_poly.index

        deselect_all_objects()
        select_and_activate(target)
        # 获取目标物体网格数据
        target_mesh = target.data
        match_count = 0
        for target_poly in target_mesh.polygons:
            # target_poly的质心坐标要乘上0.08，但是质心坐标不会随着缩放比例的变化而变化
            key = (
                truncate(target_poly.center.x * 0.08, precision),
                truncate(target_poly.center.y * 0.08, precision),
                truncate(target_poly.center.z * 0.08, precision))
            if key in source_center_poly_map:
                match_count += 1
                source_poly = source_center_poly_map[key]
                material_index = source_poly_material_map[source_poly]
                target_poly.material_index = material_index
        if match_count != len(source_mesh.polygons):
            # 如果出现特殊情况给予提示
            operator.report(type={'WARNING'},
                            message=f'未能完整传递多材质，请检查。'
                                    f'源物体：{source.name}，面数：{len(source_mesh.polygons)}。'
                                    f'目标物体：{target.name}，面数：{len(source_mesh.polygons)}，匹配成功面数：{match_count}')


def link_modifiers(mapping):
    """复制pmx修改器到abc上面（同时保留网格序列缓存修改器，删除骨架修改器）"""
    for source, target in mapping.items():
        deselect_all_objects()
        # 备份abc的修改器（不进行这一步的话abc的修改器会丢失）
        # 创建一个临时网格对象（立方体）
        bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        temp_mesh_object = bpy.context.active_object
        select_and_activate(temp_mesh_object)
        select_and_activate(target)
        # 将abc的修改器关联到临时网格对象上面
        bpy.ops.object.make_links_data(type='MODIFIERS')

        # 复制pmx修改器到abc上面
        deselect_all_objects()
        select_and_activate(target)
        select_and_activate(source)
        bpy.ops.object.make_links_data(type='MODIFIERS')

        # 将临时网格对象的修改器名称、类型、属性复制到abc的新建修改器上面
        deselect_all_objects()
        select_and_activate(temp_mesh_object)
        # todo 更具体一些的修改器比较合适
        mSrc = None
        for modifier in temp_mesh_object.modifiers:
            mSrc = modifier
            break
        select_and_activate(target)
        mDst = target.modifiers.new(mSrc.name, mSrc.type)
        properties = [p.identifier for p in mSrc.bl_rna.properties
                      if not p.is_readonly]
        for prop in properties:
            setattr(mDst, prop, getattr(mSrc, prop))

        # 如果网格对象缓存修改器不在第一位，则将其移动到第一位
        while target.modifiers.find(mDst.name) != 0:
            bpy.ops.object.modifier_move_up(modifier=mDst.name)
        # 删除骨架修改器
        for armature_modifier in modifiers_by_type(target, 'ARMATURE'):
            target.modifiers.remove(armature_modifier)

        # 删除临时网格对象
        deselect_all_objects()
        select_and_activate(temp_mesh_object)
        bpy.ops.object.delete()


if __name__ == "__main__":
    pass
