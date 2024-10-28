import bmesh

from ..utils import *


class TransferPresetOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.transfer_preset"  # 引用时的唯一标识符
    bl_label = "传递"  # 显示名称（F3搜索界面，不过貌似需要注册，和panel中显示的内容区别开）
    bl_description = "将源模型的材质传递到目标模型上"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        main(self, context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成


def process_locator(operator, mapping, face_locator, auto_face_location, face_object, face_vg):
    """处理定位头部的物体，将其由骨架转移到脸部顶点组上面（顶点父级）
       abc描边宽度一般为pmx描边宽度的12.5倍，但是描边宽度实现方式不同（如几何节点、实体化），这里暂不处理
    """
    # 手动吸管输入
    locator = face_locator
    vg_name = locator.parent_bone

    face_obj = None
    # 备选三点父级位置（source）
    source_face_vert_location = {}
    if auto_face_location is False:
        for source, target in mapping.items():
            if source.name == face_object.name:
                face_obj = target
                break
        if face_obj is None:
            raise Exception(f"在pmx模型中找不到名称为{face_object.name}的物体。")

        group_names = {v.index: v.name for v in face_object.vertex_groups}
        bm = bmesh.new()
        bm.from_mesh(face_object.data)
        # 获取顶点的变形权重层
        dvert_lay = bm.verts.layers.deform.active
        count = 0
        for vert in bm.verts:
            dvert = vert[dvert_lay]
            for group_index, weight in dvert.items():
                group_name = group_names[group_index]
                if group_name == face_vg and weight == 1.0:
                    count += 1
                    # 备选三点父级位置
                    for i in range(-1, 2):
                        for j in range(-1, 2):
                            for k in range(-1, 2):
                                key = (
                                    truncate(vert.co.x) + i * 1,
                                    truncate(vert.co.y) + j * 1,
                                    truncate(vert.co.z) + k * 1)
                                if key not in source_face_vert_location:
                                    source_face_vert_location[key] = 1
                                else:
                                    source_face_vert_location[key] = source_face_vert_location[key] + 1
        if count < 3:
            raise Exception(f"在{face_object.name}中未找到属于顶点组{face_vg}且权重为1的至少三个非重合顶点。")

    else:
        # 面部物体flag
        face_flag = False
        # 获取source中，属于头部顶点组且权重为1的顶点。
        # 在这些顶点中，默认通过“局部z最小的那个顶点所对应的物体”为面部，面部中，“含顶点数最多”的松散块作为待选区域，待选区域中的（无重合点的）三个边缘顶点（min_x, max_x, min_z）作为三点父级
        # 这么做的目的是尽量避免眼睛，眉毛，口腔等部位因形态键造成的位置不稳定
        # 不过这样定位面部并不准确，但是这些顶点属于头部顶点组且权重为1，且面部定位器位于三点父级的质心，可正确提供面部旋转信息（预设大多只需要旋转信息而非位置），所以就算定位到帽子等部位也没关系。
        # 可以额外提供一个顶点组参数作为面部待选区域，该参数由用户指定，用于准确定位面部

        # 在所有源物体中局部z值最小的顶点
        face_min_z = float('inf')
        # 拥有局部z值最小的顶点的源物体所对应的目标物体
        face_min_z_obj = None
        for source, target in mapping.items():
            current_min_z = float('inf')
            current_min_z_obj = None
            # 符合条件的顶点数量
            count = 0
            # 符合条件的顶点位置 -> 出现次数，次数大于1表明存在重合点
            vert_location = {}
            # 顶点组索引 -> 顶点组名称
            group_names = {v.index: v.name for v in source.vertex_groups}

            bm = bmesh.new()
            bm.from_mesh(source.data)
            # 获取顶点的变形权重层
            dvert_lay = bm.verts.layers.deform.active
            for vert in bm.verts:
                dvert = vert[dvert_lay]
                for group_index, weight in dvert.items():
                    group_name = group_names[group_index]
                    if group_name == vg_name and weight == 1.0:
                        count += 1
                        if vert.co.z < current_min_z:
                            current_min_z = vert.co.z
                            current_min_z_obj = target
                        # 备选三点父级位置
                        for i in range(-1, 2):
                            for j in range(-1, 2):
                                for k in range(-1, 2):
                                    key = (
                                        truncate(vert.co.x) + i * 1,
                                        truncate(vert.co.y) + j * 1,
                                        truncate(vert.co.z) + k * 1)
                                    if key not in vert_location:
                                        vert_location[key] = 1
                                    else:
                                        vert_location[key] = vert_location[key] + 1
            if count >= 3:  # 3点父级
                if current_min_z < face_min_z:
                    face_flag = True
                    source_face_vert_location = vert_location
                    face_min_z = current_min_z
                    face_min_z_obj = current_min_z_obj
            bm.free()

        if face_flag:
            face_obj = face_min_z_obj
        else:
            raise Exception(f"在PMX模型中未找到属于顶点组{vg_name}且权重为1的至少三个非重合顶点。")

    select_and_activate(face_obj)
    bpy.ops.object.mode_set(mode='EDIT')
    # 取消所有选中的面、边和顶点
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    bm = bmesh.new()
    bm.from_mesh(face_obj.data)
    # 根据备选三点父级位置（source）获取备选三点父级位置（target）
    # 这个过程会去除重合点对最终结果的影响（如焊接修改器）
    target_face_vert_location = []
    for vert in bm.verts:
        key = (
            truncate(vert.co.x * 0.08, ),
            truncate(vert.co.y * 0.08),
            truncate(vert.co.z * 0.08))
        if key in source_face_vert_location:
            v_count = source_face_vert_location[key]
            if v_count > 1:
                continue
            target_face_vert_location.append(vert)

    # 面部松散块
    islands = [island for island in get_islands(bm, verts=target_face_vert_location)["islands"]]
    # 面部待选区域  随机松散块测试 face = random.choice(islands) if islands else None
    face_area = max(islands, key=len) if islands else None

    # 三点父级对应顶点
    min_z_vertex = min(face_area, key=lambda v: v.co.z)
    face_area.remove(min_z_vertex)
    min_x_vertex = min(face_area, key=lambda v: v.co.x)
    face_area.remove(min_x_vertex)
    max_x_vertex = max(face_area, key=lambda v: v.co.x)
    face_area.remove(max_x_vertex)

    min_z_vertex.select = True
    min_x_vertex.select = True
    max_x_vertex.select = True
    parents = [min_z_vertex, min_x_vertex, max_x_vertex]
    parent_indexes = [v.index for v in parents]

    # 清除面部定位器之前的父级（保持变换）
    world_loc = locator.matrix_world.to_translation()
    locator.parent = None
    locator.matrix_world.translation = world_loc
    target_collection = face_obj.users_collection[0]
    # 将面部定位器移动到abc所在集合
    if target_collection:
        move_to_target_collection_recursive(locator, target_collection)

    # 将面部定位器移动到三点父级质心（全局坐标）
    avg_position = Vector(sum((face_obj.matrix_world @ v.co for v in parents), Vector())) / len(parents)
    locator.location = avg_position

    # 设置三点父级
    bm.to_mesh(face_obj.data)
    bm.free()
    select_and_activate(face_obj)
    bpy.ops.object.mode_set(mode='EDIT')
    show_object(locator)
    locator.select_set(True)
    bpy.ops.object.vertex_parent_set()
    bpy.ops.object.mode_set(mode='OBJECT')

    # 将三点父级对应顶点放入顶点组中（顺序在bm.to_mesh(face_obj.data)后面，否则添加顶点失败）
    vertex_group = face_obj.vertex_groups.new(name="FACE_VERTEX_3")
    vertex_group.add(parent_indexes, 1.0, 'REPLACE')

    set_visibility(locator, (False, True, False, True))


def check_transfer_preset_props(operator, props):
    direction = props.direction
    if direction == 'PMX2ABC':
        source_pmx2abc = props.source_pmx2abc
        if source_pmx2abc is None:
            operator.report(type={'ERROR'}, message=f'请输入源物体！')
            return False
        pmx_root = find_pmx_root_with_child(source_pmx2abc)
        if pmx_root is None:
            operator.report(type={'ERROR'}, message=f'没有找到pmx对象！')
            return False
        pmx_armature = find_pmx_armature(pmx_root)
        if pmx_armature is None:
            operator.report(type={'ERROR'}, message=f'在{pmx_root.name}中没有找到pmx骨架！')
            return False
        pmx_objects = find_pmx_objects(pmx_armature)
        if len(pmx_objects) == 0:
            operator.report(type={'ERROR'}, message=f'在{pmx_root.name}中没有找到网格对象！')
            return False
        abc_objects = find_abc_objects()
        if len(abc_objects) == 0:
            operator.report(type={'ERROR'}, message=f'没有找到abc文件对应的网格对象！')
            return False

        toon_shading_flag = props.toon_shading_flag
        face_locator = props.face_locator
        auto_face_location = props.auto_face_location
        face_object = props.face_object
        face_vg = props.face_vg
        # 排除面部定位器对操作流程的影响
        if toon_shading_flag:
            if face_locator is None:
                operator.report(type={'ERROR'}, message=f'请输入面部定位器对象！')
                return False
            # 先仅考虑骨骼父级的情况
            if face_locator.parent_type != 'BONE':
                operator.report(type={'ERROR'},
                                message=f'面部定位器的父级类型不受支持！支持类型：骨骼（BONE），当前类型：{face_locator.parent_type}。')
                return False
            vg_name = face_locator.parent_bone
            if vg_name is None or vg_name == '':
                operator.report(type={'ERROR'}, message=f'面部定位器未绑定到父级骨骼！')
                return False

        if auto_face_location is False:
            if face_object is None:
                operator.report(type={'ERROR'}, message=f'请输入面部对象！')
                return False
            if face_vg is None or face_vg == '':
                operator.report(type={'ERROR'}, message=f'请输入面部顶点组！')
                return False
    elif direction == 'PMX2PMX':
        if props.source is None:
            operator.report(type={'ERROR'}, message=f'请输入源物体！')
            return False
        if props.target is None:
            operator.report(type={'ERROR'}, message=f'请输入目标物体！')
            return False
        source_root = find_pmx_root_with_child(props.source)
        target_root = find_pmx_root_with_child(props.target)
        if source_root is None:
            operator.report(type={'ERROR'}, message=f'源物体不属于PMX模型！')
            return False
        if target_root is None:
            operator.report(type={'ERROR'}, message=f'目标物体不属于PMX模型！')
            return False
        if source_root == target_root:
            operator.report(type={'ERROR'}, message=f'源物体与目标物体（祖先）相同！')
            return False
    elif direction == 'ABC2ABC':
        abc_filepath = props.abc_filepath
        if not abc_filepath:
            operator.report(type={'ERROR'}, message=f'请输入缓存文件地址！')
            return False
        if not os.path.exists(abc_filepath):
            operator.report(type={'ERROR'}, message=f'缓存文件地址不存在！')
            return False
        if "abc" not in os.path.splitext(abc_filepath)[1]:
            operator.report(type={'ERROR'}, message=f'请输入abc缓存文件地址！')
            return False

    return True


def get_mesh_stats(obj):
    # Ensure the object is a mesh
    if obj.type != 'MESH':
        raise TypeError(f"Object {obj.name} is not a mesh")

    # todo 待进一步探明配对时需要排除哪些影响
    # mesh = obj.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get())
    mesh = obj.data

    vert_count = len(mesh.vertices)
    edge_count = len(mesh.edges)
    face_count = len(mesh.polygons)
    loop_count = len(mesh.loops)

    return vert_count, edge_count, face_count, loop_count


def matching(sources, targets, direction):
    """尽可能的对物体配对
        4w面  循环80w次  耗时0.7秒
        13w面 循环230w次 耗时2.3秒 20w面应该是常用模型的较大值了
        50w面 循环800w次 耗时10秒
    """
    start_time = time.time()
    source_targets_map = {}
    for source in sources:
        for target in targets:
            source_stats = get_mesh_stats(source)
            target_stats = get_mesh_stats(target)
            if source_stats != target_stats:
                continue

            vertices = {}
            for vert in source.data.vertices:
                for i in range(-1, 2):
                    for j in range(-1, 2):
                        for k in range(-1, 2):
                            key = (
                                truncate(vert.co.x) + i * 1,
                                truncate(vert.co.y) + j * 1,
                                truncate(vert.co.z) + k * 1)
                            if key not in vertices:
                                vertices[key] = 1
                            else:
                                vertices[key] = vertices[key] + 1

            match_count = 0
            for vert in target.data.vertices:
                key = gen_key(vert, direction[-3:])
                if key in vertices:
                    match_count += 1
            if match_count / len(target.data.vertices) > 0.95:
                # target是个列表，如果大于1，则还要按照名称来匹配
                if source_targets_map.get(source, None):
                    source_targets_map[source].append(target)
                else:
                    source_targets_map[source] = [target]

    # 遍历source_target_maps，如果key存在多个target（如发+、衣+等内容和发、衣校验的结果是一模一样的），则对这些内容进行二次校验
    # 如果key和value的名称相同，才进行配对，放入source_target_map（PMX2PMX的情况下）
    # 即使这样二次校验了，也只是尽可能的去配对，无法完全配对上
    source_target_map = {}
    for source, target_list in source_targets_map.items():
        if direction == "PMX2ABC":
            source_target_map[source] = target_list[0]
        else:  # PMX2PMX
            if len(target_list) > 1:
                for target in target_list:
                    source_match = PMX_NAME_PATTERN.match(source.name)
                    target_match = PMX_NAME_PATTERN.match(target.name)
                    source_name_normal = source_match.group('name') if source_match else source.name
                    target_name_normal = target_match.group('name') if target_match else target.name
                    if source_name_normal == target_name_normal:
                        source_target_map[source] = target
                if not source_target_map.get(source, None):
                    source_target_map[source] = target_list[0]
            elif target_list:
                source_target_map[source] = target_list[0]
    print(f"配对完成，用时: {time.time() - start_time} 秒")
    return source_target_map


def gen_key(vert, object_type):
    if object_type == "PMX":
        return (
            truncate(vert.co.x),
            truncate(vert.co.y),
            truncate(vert.co.z))
    elif object_type == "ABC":
        return (
            truncate(vert.co.x * 0.08),
            truncate(vert.co.y * 0.08),
            truncate(vert.co.z * 0.08))


def link_normal(mapping, direction):
    """
    传递源物体的自定义拆边法向信息到目标物体身上。
    该操作的目的是通过传递自定义拆边法向，配合abc烘焙时不导出法向信息，以此来减少abc文件的体积与烘焙时间。
    传入的mapping是配对完成后的内容，拓扑一致，所以映射方式为拓扑

    源物体的锐边信息需要同步吗？不需要，如果源物体有锐边，推荐重新导出pmx进行预设的构建。
    拆边法向的常见场景是通过合并顶点重新计算法向，修复面与面之间的折痕，但是这样会更改拓扑结构，所以插件不支持这个操作。需要用户在检查模型阶段完成修复操作，或手动添加数据传递修改器
    将修复完成后的pmx模型重新导入后，该模型已经具备了修复后的法向，所以PMX->PMX的情况下无需传递法向

    # 更新：在blender3.x以上的环境下，我们无法自由选择读取（缓存的）什么数据。所以暂时不考虑法向的传递
    更新：虽然可能需要二次导出abc文件（第一次mmd中无法向烘焙，第二次在其它3D软件中导入导出abc文件以适配blender3.x以上的缓存修改器），但依然可能会有abc文件过大的情况，或者保存abc文件的需求。
    """
    if direction == "PMX2PMX":
        return

    # 记录物体修改器显示情况，然后关闭修改器的显示，防止对后续传递造成影响（如焊接等修改器会使source target拓扑不一致）
    # 物体 -> 物体修改器是否显示
    obj_mod_show_map = {}
    for source, target in mapping.items():
        obj_mod_show_map[source.name] = [mod.show_viewport for mod in source.modifiers]
        for mod in source.modifiers:
            mod.show_viewport = False

    for source, target in mapping.items():
        deselect_all_objects()
        select_and_activate(target)

        # 为target创建DataTransfer修改器，源为source，混合模式为替换，混合系数为1，传递内容为面拐数据中的自定义法向，映射方式为最近的面插值
        modifier = target.modifiers.new(name="custom_normal_transfer", type='DATA_TRANSFER')
        modifier.object = source
        modifier.mix_mode = 'REPLACE'
        modifier.mix_factor = 1.0

        # 将DataTransfer修改器移动到第一位
        bpy.ops.object.modifier_move_to_index(modifier=modifier.name, index=0)

        # 如果“TOPOLOGY的设置”在“修改器移动到第一位”之前，则会提示“源网格与目标网格面拐数量不一致，此类情形无法使用 '拓扑' 映射”，但最终依然能够正确传递
        # 为了避免出现令人困惑的输出，将“TOPOLOGY的设置”放在“修改器移动到第一位”之后
        modifier.use_loop_data = True
        modifier.data_types_loops = {'CUSTOM_NORMAL'}
        modifier.loop_mapping = 'TOPOLOGY'

        # 执行生成数据层，然后应用掉该修改器
        bpy.ops.object.datalayout_transfer(modifier=modifier.name)
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        # 获取target网格序列缓存修改器，取消面的读取
        cache_modifiers = modifiers_by_type(target, "MESH_SEQUENCE_CACHE")
        for cache_modifier in cache_modifiers:
            cache_modifier.read_data = {'VERT', 'UV', 'COLOR'}

    # 恢复物体修改器显示情况
    for source, target in mapping.items():
        source_mod_show_list = obj_mod_show_map.get(source.name)
        for index, mod in enumerate(source.modifiers):
            mod.show_viewport = source_mod_show_list[index]


def get_obj_with_cache_modifier(selected=True):
    if selected:
        objs = bpy.context.selected_objects
    else:
        objs = bpy.data.objects
    cache_objs = []
    for obj in objs:
        if obj.type != 'MESH':
            continue
        if not any(mod.type == 'MESH_SEQUENCE_CACHE' for mod in obj.modifiers):
            continue
        cache_objs.append(obj)
    return cache_objs


def import_abc_file(filepath):
    """导入abc文件"""
    bpy.ops.wm.alembic_import(filepath=filepath)
    return bpy.context.selected_objects


def match_caches(source_caches, target_caches):
    """遍历abc文件和场景列表，配对顶点数一致的物体"""
    for source in source_caches:
        if source.type != 'MESH':
            continue
        source_verts = len(source.data.vertices)
        for target in target_caches:
            target_verts = len(target.data.vertices)
            if source_verts != target_verts:
                continue

            source_mods = modifiers_by_type(source, 'MESH_SEQUENCE_CACHE')
            target_mods = modifiers_by_type(target, 'MESH_SEQUENCE_CACHE')
            source_mod = source_mods[0] if source_mods else None
            target_mod = target_mods[0] if target_mods else None
            if source_mod is None or target_mod is None:
                continue

            # 传递MeshSequenceCache参数
            target_mod.cache_file = source_mod.cache_file
            target_mod.object_path = source_mod.object_path
            target_mod.read_data = source_mod.read_data

    for source in reversed(source_caches):
        bpy.data.objects.remove(source, do_unlink=True)


def reset_cache_param(abc_filepath, selected_only, operator):
    """
    重新设置缓存修改器参数，可能出现匹配不上的情况，这可能是多次修改等操作导致的顶点数不一致的问题（一般情况下相差几个顶点吧，暂不做额外处理）

    # 网格对象：
    # 如果物体使用的缓存文件不同，则根据缓存文件分组
    # 如果使用的缓存文件相同，则根据xform_0_material_0 分组
    # 缓存对象：
    # 则根据xform_0_material_0分组
    """

    # 记录选择状态
    active_object = bpy.context.active_object
    selected_objects = [obj for obj in bpy.context.selected_objects]

    if selected_only:
        target_objs = bpy.context.selected_objects
    else:
        target_objs = bpy.data.objects

    # 目标角色 -> 角色信息 map
    target_character_map, obj_info_map, target_obj_flag_map, non_compliant_list = get_character_map(target_objs)

    # 导入abc文件
    source_objs = import_abc_file(abc_filepath)
    source_character_map, _, _, _ = get_character_map(source_objs)

    source_target_map = {}
    # 源角色与目标角色的网格number，网格数一致即可，网格number可（因未选中）缺省，可（因网格复制）冗余
    for source_character, source_infos in source_character_map.items():
        for target_character, target_infos in target_character_map.items():
            # 单个目标角色只能被使用一次，如果有多个相同源角色，则应复制多份目标角色
            if target_character in source_target_map.values():
                continue

            if match_info(source_infos, target_infos):
                # 记录映射关系
                source_target_map[source_character] = target_character
                # 关联缓存
                link_cache(source_infos, target_infos, target_obj_flag_map)
                break

    # 对未配对但和已配对对象拥有相同父级的对象进行优化
    # 如果执行后仍有未匹配的物体，那么可能是因为
    #   顶点数不一致导致整体配对失败
    #   Ctrl C/V 导致的缓存名称不匹配而配对失败（应该用Shift + D）
    for target_name, flag in target_obj_flag_map.items():
        if flag:
            continue
        target_info = obj_info_map[target_name]
        target_infos = [target_info]
        target_obj = bpy.data.objects.get(target_name)
        if target_obj.parent:
            source2_objs = target_obj.parent.children
            source2_infos = []
            for source2_obj in source2_objs:
                if target_info == source2_obj:
                    continue
                source2_infos.append(obj_info_map[source2_obj.name])
            # 自己和自己配对（由于之前已经配对过一次，所以这里配对使用的是旧number顺序）
            if match_info(source2_infos, target_infos):
                link_cache(source2_infos, target_infos, target_obj_flag_map)

    for source_obj in source_objs:
        bpy.data.objects.remove(source_obj, do_unlink=True)

    if selected_only:
        deselect_all_objects()
        for obj in selected_objects:
            select_and_activate(obj)
        if active_object:
            select_and_activate(active_object)

    # 输出异常信息
    if all(target_obj_flag_map.values()) and not non_compliant_list:
        pass
    else:
        msg = ''
        if non_compliant_list:
            msg = msg + f'以下物体缓存信息无效：\n{non_compliant_list}\n'
        false_keys = [key for key, value in target_obj_flag_map.items() if not value]
        if false_keys:
            msg = msg + f'以下物体配对失败，请检查网格顶点数或缓存文件名称：\n{false_keys}'
        operator.report({'WARNING'}, msg)
        operator.report({'WARNING'}, f'存在未成功配对对象，点击查看报告↑↑↑')


def match_info(source_infos, target_infos):
    """在number一致的情况下校验顶点数是否一致，以判断是否为同一角色"""
    for source_info in source_infos:
        for target_info in target_infos:
            source_number = source_info[5]  # 网格顺序number
            source_v_number = source_info[1]  # 顶点数

            target_number = target_info[5]
            target_v_number = target_info[1]

            if source_number == target_number:
                if source_v_number != target_v_number:
                    return False
    return True


def link_cache(source_infos, target_infos, target_obj_flag_map):
    for source_info in source_infos:
        for target_info in target_infos:
            source_number = source_info[5]  # 网格顺序number
            target_number = target_info[5]

            if source_number != target_number:
                continue

            source_obj = bpy.data.objects.get(source_info[0])
            target_obj = bpy.data.objects.get(target_info[0])

            target_obj_flag_map[target_info[0]] = True

            source_mod = source_obj.modifiers.get(source_info[2])
            target_mod = target_obj.modifiers.get(target_info[2])

            # 仅修改cache_file.filepath，不修改cache_file，这样替换单一角色动作的时候，其它角色不会受到影响
            target_mod.cache_file.filepath = source_mod.cache_file.filepath
            target_mod.object_path = source_mod.object_path


def get_character_map(objs):
    # 角色 -> 角色信息 map
    character_map = {}
    # 网格对象 -> 网格对象信息
    obj_info_map = {}
    # 目标网格 ->是否关联完毕 map
    obj_flag_map = {}
    # 不合规列表
    non_compliant_list = []
    for obj in objs:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type != 'MESH_SEQUENCE_CACHE':
                continue
            cache_file = mod.cache_file
            if not cache_file:
                non_compliant_list.append(obj.name)
                continue

            cache_file_name = mod.cache_file.name
            object_path = mod.object_path

            pattern = r'/xform_(\d+)_material_(\d+)/mesh_(\d+)_material_(\d+)'
            match = re.match(pattern, object_path)
            if not match:
                non_compliant_list.append(obj.name)
                continue
            numbers = match.groups()
            character_number = numbers[0]  # 代表角色类别的部分
            obj_number = numbers[1]  # 代表网格对象顺序的部分

            obj_flag_map[obj.name] = False

            info = [obj.name, len(obj.data.vertices), mod.name, cache_file_name, character_number, obj_number]
            obj_info_map[obj.name] = info

            key = f'CACHE_{cache_file_name}_NUMBER_{character_number}'  # 根据缓存名称和物体路径来决定角色
            character_map.setdefault(key, []).append(info)
    return character_map, obj_info_map, obj_flag_map, non_compliant_list


def main(operator, context):
    # pmx -> abc 操作频率较高，仅用名称配对即可
    # pmx -> pmx 在换头类角色上材质/网格顺序内容变动的情况下 能够很好地适应。
    # 后者频率较低，使用强校验（顶点数量、位置要一致），但要尽可能配对更多的物体，如提供一个容忍度，大于这个数值的顶点数一致即可，以解决可能存在的未知问题
    # 三渲二仅支持pmx -> abc
    scene = context.scene

    # 参数校验
    props = scene.mmd_kafei_tools_transfer_preset
    direction = props.direction
    if check_transfer_preset_props(operator, props) is False:
        return
    toon_shading_flag = props.toon_shading_flag
    face_locator = props.face_locator

    source_root = None
    source_armature = None
    source_objects = None
    target_root = None
    target_armature = None
    target_objects = None
    source_target_map = {}

    if direction in ['PMX2ABC', 'PMX2PMX']:
        if direction == 'PMX2ABC':
            source_pmx2abc = props.source_pmx2abc
            source_root = find_pmx_root_with_child(source_pmx2abc)
            source_armature = find_pmx_armature(source_root)
            source_objects = find_pmx_objects(source_armature)
            # 排除MESH类型面部定位器对后续流程的影响
            if toon_shading_flag and face_locator.type == 'MESH':
                source_objects.remove(face_locator)
            target_objects = find_abc_objects()
            sort_pmx_objects(source_objects)
            sort_abc_objects(target_objects)
            if len(source_objects) == len(target_objects):
                source_target_map = dict(zip(source_objects, target_objects))
            else:
                source_target_map = matching(source_objects, target_objects, direction)
        elif direction == 'PMX2PMX':
            # 通过名称可以进行快速的配对，但是，如果pmx网格内容/顺序修改了，无法进行 abc -> pmx 的反向配对
            # 通过顶点数量进行配对，可能会出现顶点数相同但网格内容不同的情况，如左目右目（但几率非常低）
            # 通过顶点数进行初步判断，再通过顶点局部位置是否相同（含误差）进行二次判断（相较其他方法慢一些），可以排除无关物体带来的影响，可以尽可能的双向配对
            # unit_test_compare可以对两个MESH进行比较，但是结果是String类型的描述，而且描述比较模糊无法获取到完整的信息
            # 不再提供是否进行强校验的参数，PMX2ABC默认名称配对，PMX2PMX默认强校验
            source_root = find_pmx_root_with_child(props.source)
            source_armature = find_pmx_armature(source_root)
            source_objects = find_pmx_objects(source_armature)
            target_root = find_pmx_root_with_child(props.target)
            target_armature = find_pmx_armature(target_root)
            target_objects = find_pmx_objects(target_armature)
            source_target_map = matching(source_objects, target_objects, direction)

        # 源模型和目标模型如果没有完全匹配，仍可以继续执行，但如果完全不匹配，则停止继续执行
        if len(source_target_map) == 0:
            if toon_shading_flag:
                raise RuntimeError(
                    f"模型配对失败。配对成功数：0，源模型物体数量：{len(source_objects)}（不含面部定位器），目标模型物体数量：{len(target_objects)}，请检查")
            else:
                raise RuntimeError(
                    f"模型配对失败。配对成功数：0，源模型物体数量：{len(source_objects)}，目标模型物体数量：{len(target_objects)}，请检查")

        # 考虑到可能会对pmx的网格物体进行隐藏（如多套衣服、耳朵、尾巴、皮肤冗余处等），处理时需要将这些物体取消隐藏使其处于可选中的状态，处理完成后恢复
        # 记录源物体和目标物体的可见性
        display_list = source_objects + target_objects
        display_list.append(source_root)
        display_list.append(source_armature)
        if direction == 'PMX2PMX':
            display_list.append(target_root)
            display_list.append(target_armature)
        visibility_map = show_objects(display_list)

        uv_flag = props.uv_flag
        if uv_flag:
            # 关联源物体UV到目标物体上面
            link_uv(operator, source_target_map, direction)

        material_flag = props.material_flag
        if material_flag:
            # 关联源物体材质到目标物体上面
            link_material(source_target_map)
            # 关联源物体材质到目标物体上面（多材质槽情况下）
            link_multi_slot_materials(operator, source_target_map, direction)

        # 关联源物体顶点组及顶点权重到目标物体上面（正序）
        vgs_flag = props.vgs_flag
        if vgs_flag:
            link_vertices_group(source_armature, target_armature, source_target_map, direction)
            link_vertices_weight(source_armature, target_armature, source_target_map, direction)

        # 复制pmx修改器到abc上面（同时保留网格序列缓存修改器，删除骨架修改器）
        modifiers_flag = props.modifiers_flag
        if modifiers_flag:
            link_modifiers(source_target_map, direction)

        normal_flag = props.normal_flag
        if normal_flag:
            link_normal(source_target_map, direction)

        face_object = props.face_object
        face_vg = props.face_vg
        auto_face_location = props.auto_face_location
        # 三渲二面部定位器处理
        if toon_shading_flag and direction == 'PMX2ABC':
            process_locator(operator, source_target_map, face_locator, auto_face_location, face_object, face_vg)

        # 为abc模型创建父级物体，创建父级可以更好地操作与管理导入的abc模型
        if direction == 'PMX2ABC':
            create_abc_parent(source_root, source_target_map)

        # 恢复原有可见性
        for obj, visibility in visibility_map.items():
            set_visibility(obj, visibility)
    elif direction in ['ABC2ABC']:
        abc_filepath = props.abc_filepath
        selected_only = props.selected_only
        reset_cache_param(abc_filepath, selected_only, operator)


def create_abc_parent(source_root, source_target_map):
    create_flag = True
    for obj in source_target_map.values():
        if obj.parent:
            create_flag = False
            break
    if create_flag:
        # 创建abc父级空物体
        if 'pmx' in source_root.name.lower():
            abc_root = bpy.data.objects.new(case_insensitive_replace("pmx", "abc", source_root.name), None)
        else:
            abc_root = bpy.data.objects.new(source_root.name + " abc", None)

        # 需要将parent移动到child所在集合
        # 在使用时出现过child在集合a而parent新建在集合b的情况（因为b处于激活的状态），这样会对用户产生困扰
        # 由于一般情况下child不会分散在各个集合，所以任选其一作为参考即可
        for target in source_target_map.values():
            if len(target.users_collection) > 0:
                target.users_collection[0].objects.link(abc_root)
                break

        # 设置父级
        for target in source_target_map.values():
            target.parent = abc_root


def show_objects(display_list):
    visibility_map = {}
    for obj in display_list:
        visibility_map[obj] = (obj.hide_select, obj.hide_get(), obj.hide_viewport, obj.hide_render)
        show_object(obj)
    return visibility_map


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


def link_uv(operator, source_target_map, direction):
    """关联源物体UV到目标物体上面"""
    # 用物体的顶点数等数据是否相等来校验两个物体是否是一样的进而传递UV等内容，并不准确。
    # （比如将物体拆边后，虽然顶点数边数不一致，但依然能够传递UV），但这里不考虑这些内容

    # 移除之前生成的uv对后续重复执行造成的影响
    target_uvs_to_remove = {}
    for source, target in source_target_map.items():
        target_uvs_to_remove[target] = []
        source_uv_names = [uv.name for uv in source.data.uv_layers]
        for index, uv_layer in enumerate(target.data.uv_layers):
            if uv_layer.name in source_uv_names:
                target_uvs_to_remove[target].append(index)
    for target, uvs_to_remove in target_uvs_to_remove.items():
        # 逆序删除收集到的UV图层 uv_layers.remove顺序删除会有并发修改异常
        for index in sorted(uvs_to_remove, reverse=True):
            target.data.uv_layers.remove(target.data.uv_layers[index])

    for source, target in source_target_map.items():
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
        source_uv_render_index = next(
            (index for index, uv_layer in enumerate(source_mesh.uv_layers) if uv_layer.active_render), 0)
        source_original_uv_count = len(source_mesh.uv_layers)
        # 记录目标物体原始uv数量
        target_original_uv_count = len(target_mesh.uv_layers)

        # 删除PMX2PMX情况下目标物体的UV，否则UV数量可能会达到上限
        if direction == "PMX2PMX":
            for layer in reversed(target.data.uv_layers):
                target.data.uv_layers.remove(layer)

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
            select_and_activate(target)
            select_and_activate(source)
            # 复制UV贴图
            bpy.ops.object.join_uvs()

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


def link_material(source_target_map):
    """关联source材质到target上面"""
    for source, target in source_target_map.items():
        deselect_all_objects()
        select_and_activate(target)
        select_and_activate(source)
        # 关联材质
        bpy.ops.object.make_links_data(type='MATERIAL')
    deselect_all_objects()


def link_vertices_group(source_armature, target_armature, mapping, direction):
    """将pmx物体自定义的顶点组传递到abc的对应物体上（正序）"""
    # 获取pmx物体默认的顶点组
    default_vgs = get_default_vgs(source_armature)
    if direction == "PMX2PMX":
        default_vgs.update(get_default_vgs(target_armature))

    # 需要保证源物体和目标物体自定义顶点组完全一致后续才不会出错
    # 但考虑到一般不会对target添加自定义顶点组，所以这里暂时不处理
    # 移除之前添加的自定义顶点组对重复执行的影响
    target_vgs_to_remove = {}
    for source, target in mapping.items():
        target_vgs_to_remove[target] = []
        target_vgs = target.vertex_groups
        for target_vg in target_vgs:
            if target_vg.name not in default_vgs:
                target_vgs_to_remove[target].append(target_vg)

    for target, vgs_to_remove in target_vgs_to_remove.items():
        for vg_to_remove in vgs_to_remove:
            target.vertex_groups.remove(vg_to_remove)

    # 传递顶点组
    for source, target in mapping.items():
        source_vgs = source.vertex_groups
        for source_vg in source_vgs:
            if source_vg.name not in default_vgs:
                target.vertex_groups.new(name=source_vg.name)


def get_default_vgs(armature):
    if armature is None:
        return []
    default_vgs = set()
    pbs = armature.pose.bones
    for pb in pbs:
        default_vgs.add(pb.name)
    default_vgs.add('mmd_edge_scale')
    default_vgs.add('mmd_vertex_order')
    default_vgs.add("FACE_VERTEX_3")
    return default_vgs


def link_vertices_weight(source_armature, target_armature, mapping, direction):
    """将pmx物体自定义的顶点组权重传递到abc的对应物体上"""
    # 获取pmx物体默认的顶点组
    default_vgs = get_default_vgs(source_armature)
    if direction == "PMX2ABC":
        default_vgs.update(get_default_vgs(target_armature))

    # 传递顶点组权重
    # 预先获取所有顶点组信息，仅遍历一次全部target顶点 / 每有一个顶点组，遍历一次全部target顶点
    for source, target in mapping.items():
        deselect_all_objects()
        source_vgs = source.vertex_groups
        vg_name_infos = {}
        for source_vg in source_vgs:
            if source_vg.name in default_vgs:
                continue
            # 激活source对象当前顶点组
            select_and_activate(source)
            bpy.ops.object.vertex_group_set_active(group=source_vg.name)
            # 获取source对象当前顶点组中的顶点、权重信息
            vertices_and_weights = get_vertices_and_weights(source, source_vg)
            if len(vertices_and_weights) == 0:
                continue
            vg_name_infos[source_vg.name] = vertices_and_weights
        # 获取target顶点
        # 如果坐标值 in vertices_and_weights，则设置相应权重
        for vert in target.data.vertices:
            for vg_name, vg_info in vg_name_infos.items():
                target_vg = target.vertex_groups[vg_name]
                key = gen_key(vert, direction[-3:])
                if key in vg_info:
                    weight = vg_info[key]
                    target_vg.add([vert.index], weight, 'REPLACE')


def get_vertices_and_weights(obj, vertex_group):
    """获取顶点组中的顶点及其权重map"""
    vertices_and_weights = {}
    mesh = obj.data
    vertex_group_index = obj.vertex_groups.find(vertex_group.name)
    if vertex_group_index != -1:
        for vert in mesh.vertices:
            for group_element in vert.groups:
                if group_element.group == vertex_group_index:
                    for i in range(-1, 2):
                        for j in range(-1, 2):
                            for k in range(-1, 2):
                                key = (
                                    truncate(vert.co.x) + i * 1,
                                    truncate(vert.co.y) + j * 1,
                                    truncate(vert.co.z) + k * 1)
                                vertices_and_weights[key] = group_element.weight
    return vertices_and_weights


def truncate(value):
    """对值÷精度后的结果进行截断，返回整数部分"""
    return math.floor(value / PRECISION)


def link_multi_slot_materials(operator, mapping, direction):
    """关联源物体材质到目标物体上面（多材质槽情况下）"""
    for source, target in mapping.items():
        # 没有active_object直接mode_set会报异常
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
            # 这里对坐标值 / PRECISION后的结果进行截断，保留整数，误差为±1。
            for i in range(-1, 2):
                for j in range(-1, 2):
                    for k in range(-1, 2):
                        key = (
                            truncate(source_poly.center.x) + i * 1,
                            truncate(source_poly.center.y) + j * 1,
                            truncate(source_poly.center.z) + k * 1)
                        source_center_poly_map[key] = source_poly.index

        deselect_all_objects()
        select_and_activate(target)
        # 获取目标物体网格数据
        target_mesh = target.data
        match_count = 0
        for target_poly in target_mesh.polygons:
            # target_poly的质心坐标要乘上0.08，但是质心坐标不会随着缩放比例的变化而变化
            key = None
            if direction[-3:] == 'ABC':
                key = (
                    truncate(target_poly.center.x * 0.08),
                    truncate(target_poly.center.y * 0.08),
                    truncate(target_poly.center.z * 0.08))
            elif direction[-3:] == 'PMX':
                key = (
                    truncate(target_poly.center.x),
                    truncate(target_poly.center.y),
                    truncate(target_poly.center.z))
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


def link_modifiers(mapping, direction):
    """复制pmx修改器到abc上面（同时保留网格序列缓存修改器，删除骨架修改器）"""
    for source, target in mapping.items():
        deselect_all_objects()
        # 备份目标物体的修改器（不进行这一步的话目标物体的修改器会丢失）
        # 创建一个临时网格对象（立方体）
        bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        temp_mesh_object = bpy.context.active_object
        select_and_activate(temp_mesh_object)
        select_and_activate(target)
        # 将目标物体修改器关联到临时网格对象上面
        bpy.ops.object.make_links_data(type='MODIFIERS')

        # 复制源物体修改器到目标物体上面
        deselect_all_objects()
        select_and_activate(target)
        select_and_activate(source)
        bpy.ops.object.make_links_data(type='MODIFIERS')

        # 增强健壮性 无法移动至一个需要原始数据的修改器之上
        for i in range(len(target.modifiers) - 1, -1, -1):
            modifier = target.modifiers[i]
            if modifier.type in ['SOFT_BODY', 'MULTIRES']:
                target.modifiers.remove(modifier)

        # 删除骨架修改器
        for armature_modifier in modifiers_by_type(target, 'ARMATURE'):
            target.modifiers.remove(armature_modifier)

        # 将临时网格对象的修改器名称、类型、属性复制到目标物体的新建修改器上面
        # 因为默认顶点组并没有关联到target中，所以可能存在target修改器属性值为红的情况，但这里暂不处理（可能性较低）
        deselect_all_objects()
        select_and_activate(temp_mesh_object)
        for index, modifier in enumerate(temp_mesh_object.modifiers):
            if direction[-3:] == 'ABC' and modifier.type != 'MESH_SEQUENCE_CACHE':
                continue
            if direction[-3:] == 'PMX' and modifier.type != 'ARMATURE':
                continue
            select_and_activate(target)
            m_dst = target.modifiers.new(modifier.name, modifier.type)
            properties = [p.identifier for p in modifier.bl_rna.properties
                          if not p.is_readonly]
            for prop in properties:
                setattr(m_dst, prop, getattr(modifier, prop))

            while target.modifiers.find(modifier.name) != index:
                bpy.ops.object.modifier_move_up(modifier=modifier.name)

        # 如果修改器涉及到source对象的引用，则将其修改为target的引用
        for target_modifier in target.modifiers:
            properties = [p.identifier for p in target_modifier.bl_rna.properties
                          if not p.is_readonly]
            for prop in properties:
                value = getattr(target_modifier, prop)
                if isinstance(value, bpy.types.Object):
                    target_ref = mapping.get(value, None)
                    if target_ref:
                        setattr(target_modifier, prop, target_ref)

        # 删除临时网格对象
        deselect_all_objects()
        select_and_activate(temp_mesh_object)
        bpy.ops.object.delete()


if __name__ == "__main__":
    pass
