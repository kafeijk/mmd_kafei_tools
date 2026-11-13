import contextlib
import array
import contextvars
import hashlib
import math
import os
import re
import time

import bmesh
import bpy

from mathutils import Vector

from ..constants import (
    DUPLICATE_SUFFIX_PATTERN,
    MAX_ID_NAME_LENGTH,
    PAIRING_TOLERANCE,
    PMX_IMPORT_SCALE,
    PMX_NAME_PATTERN,
    PRECISION,
)

from ..utils import (
    case_insensitive_replace,
    deselect_all_objects,
    find_abc_objects,
    find_ancestor,
    find_pmx_armature,
    find_pmx_objects,
    find_pmx_root_with_child,
    get_islands,
    get_mesh_objs,
    move_to_target_collection_recursive,
    restore_selection,
    select_and_activate,
    set_visibility,
    show_object,
    sort_abc_objects,
    sort_pmx_objects,
    translate,
)


class TransferPresetOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.transfer_preset"  # 引用时的唯一标识符
    bl_label = "传递"  # 显示名称（F3搜索界面，不过貌似需要注册，和panel中显示的内容区别开）
    bl_description = "将源模型的材质等数据传递到目标模型上"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        props = context.scene.mmd_kafei_tools_transfer_preset
        if not self.check_props(props):
            return {'CANCELLED'}
        if not self.transfer_preset(context):
            return {'CANCELLED'}
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def transfer_preset(self, context):
        props = context.scene.mmd_kafei_tools_transfer_preset
        self.start_time = time.time()
        # 配对阶段的异常记录，传递结束时统一提示
        self.pair_issue_list = []

        # ABC2ABC 流程独立
        if props.direction == 'ABC2ABC':
            reset_cache_param(self, props)
            return True

        return self.do_transfer_preset(props)

    def do_transfer_preset(self, props):
        """
        PMX → ABC 、 PMX → PMX 的传递流程：配对 → 面部定位 → 逐项传递 → 结果提示

        PMX → ABC 操作频率较高，仅用名称配对即可；
        PMX → PMX 需要适应换头等网格顺序/内容变动，使用顶点数量与位置校验，并借助内部常量 PAIRING_TOLERANCE 尽量多配对；
        PMX → ABC 的三渲二会把定位器挂到面部顶点，PMX → PMX 的三渲二只把定位器改挂到目标骨架的同名骨骼。
        """
        # 1. 源网格与目标网格配对
        (source_root, source_armature, source_objects, target_root, target_armature, target_objects,
         source_target_map) = self.get_source_target_map(props)

        # 2. 完全无法配对时提前终止，避免后续无意义操作
        if not self.check_source_target_map(source_target_map, source_objects, target_objects, props):
            return False

        # 3. 三渲二面部定位器处理：先确定面部对象，失败则终止
        face_obj, face_area, bm, continue_flag = get_face_area(self, source_target_map, props)
        if not continue_flag:
            if bm:
                bm.free()
            return False

        # 4. 显示相关物体并记录原可见性，流程结束后恢复
        display_list = self.get_display_list(
            props.direction, source_objects, target_objects,
            source_root, source_armature, target_root, target_armature
        )
        direction = props.direction
        visibility_map = show_objects(display_list)

        # 5. 设置面部定位器后，按固定顺序传递各类数据
        process_locator(face_obj, face_area, bm, props)
        self.transfer_all_data(source_root, source_armature, target_armature, source_target_map, props)
        # PMX → PMX 的三渲二只处理面部定位器，改挂到目标骨架的同名骨骼
        transfer_face_locator(source_armature, target_armature, props)

        # 6. 移除目标模型名称中的重名后缀（可选）
        if direction == 'PMX2PMX' and props.remove_suffix_flag:
            remove_duplicate_suffix(source_root, target_root)

        # 7. 恢复原有可见性并输出结果提示
        for obj, visibility in visibility_map.items():
            set_visibility(obj, visibility)
        self.report_transfer_result()
        return True

    @staticmethod
    def get_display_list(direction, source_objects, target_objects,
                         source_root, source_armature, target_root, target_armature):
        """需要临时显示并在结束后恢复可见性的对象列表"""
        objects = source_objects + target_objects + [source_root, source_armature]
        if direction == 'PMX2PMX':
            objects += [target_root, target_armature]
        return objects

    def transfer_all_data(self, source_root, source_armature, target_armature, source_target_map, props):
        """按固定顺序传递各类数据，过程中记录的警告由 report_warnings 统一提示"""
        with collect_warnings() as warning_map:
            # 传递UV
            link_uv(source_target_map, props)
            # 关联材质（含多材质槽的面映射）
            link_materials(source_target_map, props)
            # 传递顶点组及顶点权重（正序）
            link_vertices_group(source_armature, target_armature, source_target_map, props)
            link_vertices_weight(source_armature, target_armature, source_target_map, props)
            # 传递修改器（保留网格序列缓存修改器，删除骨架修改器）
            link_modifiers(source_target_map, props)
            # 传递自定义拆边法向
            link_normal(source_target_map, props)
            # 为ABC模型创建父级对象，方便后续操作与管理
            create_abc_parent(source_root, source_target_map, props)
        report_warnings(self, warning_map)

    def report_transfer_result(self):
        """输出总耗时；存在配对异常（一对多/多对一）时先输出明细，再给出总提示"""
        elapsed = time.time() - self.start_time
        if not self.pair_issue_list:
            self.report({'INFO'},
                        translate("已传递，总耗时 {:.2f} 秒").format(elapsed))
            return

        labels = {
            'one_to_many': translate("一对多"),
            'many_to_one': translate("多对一"),
        }
        notes = {
            'one_to_many': translate("（未传递）"),
            'many_to_one': translate("（以第一个匹配结果为准）"),
        }
        # 多对一按目标归组，源列表以第一个配对成功的源开头，明确最终以谁为准
        many_to_one_groups = {}
        for kind, source_name, target_name, *rest in self.pair_issue_list:
            if kind != 'many_to_one':
                continue
            sources = many_to_one_groups.setdefault(target_name, [rest[0]])
            if source_name not in sources:
                sources.append(source_name)

        lines = [translate("以下内容存在配对异常，请检查配对结果：")]
        for kind, source_name, target_names, *rest in self.pair_issue_list:
            label = labels.get(kind, kind)
            note = notes.get(kind, '')
            if kind == 'many_to_one':
                # 同一个目标只输出一行：源列表 → 目标，第一个匹配的源排在最前
                sources = many_to_one_groups.pop(target_names, None)
                if sources is None:
                    continue
                source_text = ", ".join(f'"{name}"' for name in sources)
                lines.append(f'{label} {source_text} → "{target_names}"{note}')
            else:
                lines.append(f'{label} "{source_name}" → {target_names}{note}')
        self.report({'WARNING'}, "\n".join(lines))
        self.report({'WARNING'}, translate(
            "已传递，总耗时 {:.2f} 秒。存在异常配对，详见↑↑↑").format(elapsed))

    def check_source_target_map(self, source_target_map, source_objects, target_objects, props):
        if not source_target_map:
            msg = translate(
                "模型配对失败。配对成功数：0，源模型物体数量：{}{}，目标模型物体数量：{}，请检查。"
            ).format(
                len(source_objects),
                translate("（不含面部定位器）") if props.toon_shading_flag else "",
                len(target_objects)
            )
            self.report({'ERROR'}, msg)
            return False
        return True

    def get_source_target_map(self, props):
        """构建源模型与目标模型之间的对象映射关系。"""

        def setup_pmx(child):
            """获取根节点、骨架与网格对象"""
            root = find_pmx_root_with_child(child)
            armature = find_pmx_armature(root)
            objects = find_pmx_objects(armature)
            return root, armature, objects

        direction = props.direction
        face_locator = props.face_locator
        toon_shading_flag = props.toon_shading_flag

        target_root = None
        target_armature = None
        if direction == 'PMX2ABC':
            # 源模型
            source_root, source_armature, source_objects = setup_pmx(props.source)
            # 源模型中排除面部定位器
            if toon_shading_flag and face_locator and face_locator in source_objects:
                source_objects.remove(face_locator)
            # 目标模型
            target_objects = find_abc_objects()
            # 排序模型网格对象
            sort_pmx_objects(source_objects)
            sort_abc_objects(target_objects)
            # 构建映射关系
            if len(source_objects) == len(target_objects):
                source_target_map = dict(zip(source_objects, target_objects))
            else:
                source_target_map, self.pair_issue_list = matching(source_objects, target_objects, direction)
        else:
            # PMX2PMX
            source_root, source_armature, source_objects = setup_pmx(props.source)
            target_root, target_armature, target_objects = setup_pmx(props.target)
            # 源模型中排除面部定位器（三渲二时单独改挂到目标骨架）
            if toon_shading_flag and face_locator and face_locator in source_objects:
                source_objects.remove(face_locator)
            source_target_map, self.pair_issue_list = matching(source_objects, target_objects, direction)
        return (source_root, source_armature, source_objects,
                target_root, target_armature, target_objects, source_target_map)

    def check_props(self, props):
        """按传递方向校验参数"""
        checkers = {
            'PMX2ABC': self.check_pmx2abc_props,
            'PMX2PMX': self.check_pmx2pmx_props,
            'ABC2ABC': self.check_abc2abc_props,
        }
        checker = checkers.get(props.direction)
        return checker(props) if checker else True

    def check_fail(self, message, *args):
        """输出校验错误并返回 False，供各方向校验方法直接返回"""
        self.report(type={'ERROR'}, message=translate(message).format(*args))
        return False

    def check_pmx2abc_props(self, props):
        """PMX → ABC：源 PMX 与 ABC 网格均需存在"""
        if props.source is None:
            return self.check_fail("请选择源模型！")
        pmx_root = find_pmx_root_with_child(props.source)
        if pmx_root is None:
            return self.check_fail("源模型不是 PMX 模型！")
        pmx_armature = find_pmx_armature(pmx_root)
        if pmx_armature is None:
            return self.check_fail("在 {} 中未找到骨架！", pmx_root.name)
        if len(find_pmx_objects(pmx_armature)) == 0:
            return self.check_fail("在 {} 中未找到网格！", pmx_root.name)
        if len(find_abc_objects()) == 0:
            return self.check_fail("未找到 ABC 网格！")
        # 三渲二才需要面部定位器与面部物体
        if props.toon_shading_flag:
            return self.check_toon_shading_props(props)
        return True

    def check_face_locator(self, props):
        """面部定位器必须为骨骼父级并绑定到具体骨骼"""
        face_locator = props.face_locator
        if face_locator is None:
            return self.check_fail("请选择面部定位器！")
        # 先仅考虑骨骼父级的情况
        if face_locator.parent_type != 'BONE':
            return self.check_fail(
                "面部定位器的父级类型不受支持！支持类型：骨骼（BONE），当前类型：{}",
                face_locator.parent_type)
        if not face_locator.parent_bone:
            return self.check_fail("面部定位器未绑定到父级骨骼！")
        return True

    def check_toon_shading_props(self, props):
        """三渲二：面部定位器必须有效，手动指定面部时校验面部物体与顶点组"""
        if not self.check_face_locator(props):
            return False
        # 自动识别面部时不需要手动参数
        if props.auto_face_location:
            return True
        face_object = props.face_object
        if face_object is None:
            return self.check_fail("请选择面部物体！")
        if face_object.type != "MESH":
            return self.check_fail("面部物体必须是网格物体！")
        if props.face_vg is None or props.face_vg == '':
            return self.check_fail("请选择面部顶点组！")
        return True

    def check_pmx2pmx_props(self, props):
        """PMX → PMX：源/目标均需为不同且带骨架的 PMX 模型"""
        if props.source is None:
            return self.check_fail("请选择源模型！")
        if props.target is None:
            return self.check_fail("请选择目标模型！")
        source_root = find_pmx_root_with_child(props.source)
        target_root = find_pmx_root_with_child(props.target)
        if source_root is None:
            return self.check_fail("源模型不是 PMX 模型！")
        if target_root is None:
            return self.check_fail("目标模型不是 PMX 模型！")
        if source_root == target_root:
            return self.check_fail("源模型与目标模型不能相同！")
        source_armature = find_pmx_armature(source_root)
        target_armature = find_pmx_armature(target_root)
        if source_armature is None:
            return self.check_fail("在 {} 中未找到骨架！", source_root.name)
        if target_armature is None:
            return self.check_fail("在 {} 中未找到骨架！", target_root.name)
        if props.toon_shading_flag:
            return self.check_pmx2pmx_toon_shading_props(
                props, source_root, source_armature, target_armature)
        return True

    def check_pmx2pmx_toon_shading_props(self, props, source_root, source_armature, target_armature):
        """三渲二：面部定位器需属于源模型，且其父级骨骼同时存在于源与目标骨架"""
        if not self.check_face_locator(props):
            return False
        face_locator = props.face_locator
        if find_pmx_root_with_child(face_locator) != source_root:
            return self.check_fail("面部定位器“{}”不属于源模型！", face_locator.name)
        bone_name = face_locator.parent_bone
        if bone_name not in source_armature.data.bones:
            return self.check_fail("在 {} 中未找到骨骼“{}”！", source_armature.name, bone_name)
        if bone_name not in target_armature.data.bones:
            return self.check_fail("在 {} 中未找到骨骼“{}”！", target_armature.name, bone_name)
        return True

    def check_abc2abc_props(self, props):
        """ABC → ABC：缓存文件必须存在且为 abc 格式"""
        abc_filepath = props.abc_filepath
        if not abc_filepath:
            return self.check_fail("请选择缓存文件！")
        # abspath 对非空字符串必定返回非空，必须显式判断文件是否存在
        if not os.path.exists(bpy.path.abspath(abc_filepath)):
            return self.check_fail("缓存文件不存在！")
        if os.path.splitext(abc_filepath)[1].lower() != ".abc":
            return self.check_fail("请选择 ABC 缓存文件！")
        return True


def transfer_face_locator(source_armature, target_armature, props):
    """PMX → PMX 三渲二：将面部定位器由源骨架改挂到目标骨架的同名骨骼
       以骨架对象为参照记录相对变换，改挂后按目标骨架还原，保证定位器相对骨架的朝向不变
    """
    if props.direction != 'PMX2PMX' or not props.toon_shading_flag:
        return

    locator = props.face_locator
    bone_name = locator.parent_bone
    relative_matrix = source_armature.matrix_world.inverted() @ locator.matrix_world

    locator.parent = target_armature
    locator.parent_type = 'BONE'
    locator.parent_bone = bone_name
    locator.matrix_world = target_armature.matrix_world @ relative_matrix


def process_locator(face_obj, face_area, bm, props):
    """处理定位头部的物体，将其由骨架转移到脸部顶点组上面（顶点父级）
       abc描边宽度一般为pmx描边宽度的12.5倍，但是描边宽度实现方式不同（如几何节点、实体化），这里暂不处理
    """
    direction = props.direction
    toon_shading_flag = props.toon_shading_flag
    if direction != 'PMX2ABC' or not toon_shading_flag:
        return

    force = props.force
    locator = props.face_locator

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

    # 将三点父级对应顶点放入顶点组中（顺序在bm.to_mesh(face_obj.data)后面，否则添加顶点失败）
    vertex_group = face_obj.vertex_groups.new(name="FACE_VERTEX_3")
    vertex_group.add(parent_indexes, 1.0, 'REPLACE')

    # 创建伪面部 防止循环引用 Dependency cycle detected
    dummy_face_obj = None
    if force:
        deselect_all_objects()
        select_and_activate(face_obj)
        bpy.ops.object.duplicate_move()
        dummy_face_obj = bpy.context.active_object
        dummy_face_obj.name = f"Locator Parent"
        # 仅保留网格序列缓存修改器
        for modifier in reversed(dummy_face_obj.modifiers):
            if modifier.type != "MESH_SEQUENCE_CACHE":
                dummy_face_obj.modifiers.remove(modifier)
        dummy_face_obj.parent = face_obj
        dummy_face_obj.matrix_parent_inverse = face_obj.matrix_world.inverted()
        face_obj = dummy_face_obj

    # 设置三点父级
    bm.to_mesh(face_obj.data)
    bm.free()
    deselect_all_objects()
    select_and_activate(face_obj)
    bpy.ops.object.mode_set(mode='EDIT')
    show_object(locator)
    locator.select_set(True)
    bpy.ops.object.vertex_parent_set()
    bpy.ops.object.mode_set(mode='OBJECT')

    if force:
        set_visibility(dummy_face_obj, (False, True, False, True))
    set_visibility(locator, (False, True, False, True))


def get_weight_one_vertex_info(mesh, vertex_group_index):
    """
    获取网格中指定顶点组权重为1的顶点信息。
    返回（顶点数, 顶点位置(27邻域膨胀) -> 出现次数, 最小z值）。
    直接遍历mesh.vertices与其顶点组权重，避免为每个物体构建bmesh并逐层访问变形权重层。
    """
    count = 0
    min_z = float('inf')
    vert_location = {}
    for vert in mesh.vertices:
        for group_element in vert.groups:
            if group_element.group != vertex_group_index or group_element.weight != 1.0:
                continue
            count += 1
            co = vert.co
            if co.z < min_z:
                min_z = co.z
            # 备选三点父级位置
            for i in range(-1, 2):
                for j in range(-1, 2):
                    for k in range(-1, 2):
                        key = (truncate(co.x) + i, truncate(co.y) + j, truncate(co.z) + k)
                        vert_location[key] = vert_location.get(key, 0) + 1
    return count, vert_location, min_z


def get_face_area(operator, mapping, props):
    direction = props.direction
    toon_shading_flag = props.toon_shading_flag
    if direction != 'PMX2ABC' or not toon_shading_flag:
        return None, None, None, True

    face_object = props.face_object
    face_vg = props.face_vg
    auto_face_location = props.auto_face_location
    locator = props.face_locator
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
            msg = translate(
                "在 PMX 模型中未找到名为“{}”的面部物体，或 ABC 模型缺少与之对应的物体，请检查。"
            ).format(face_object.name)
            operator.report(type={'ERROR'}, message=msg)
            return None, None, None, False

        vg_index = face_object.vertex_groups.find(face_vg)
        count, source_face_vert_location, _ = get_weight_one_vertex_info(face_object.data, vg_index)
        if count < 3:
            msg = translate(
                "在面部物体“{}”的顶点组“{}”中，权重为 1 且不重合的顶点少于三个。"
            ).format(face_object.name, face_vg)
            operator.report(type={'ERROR'}, message=msg)
            return None, None, None, False

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
            vg_index = source.vertex_groups.find(vg_name)
            # 没有该顶点组时不可能存在符合条件的顶点，直接跳过，避免全量扫描
            if vg_index == -1:
                continue
            # 物体的包围盒最低点均已不低于当前最优值时，不可能存在更低的头部顶点，跳过整次扫描
            if min(corner[2] for corner in source.bound_box) >= face_min_z:
                continue
            count, vert_location, current_min_z = get_weight_one_vertex_info(source.data, vg_index)
            if count >= 3:  # 3点父级
                if current_min_z < face_min_z:
                    face_flag = True
                    source_face_vert_location = vert_location
                    face_min_z = current_min_z
                    face_min_z_obj = target

        if face_flag:
            face_obj = face_min_z_obj
        else:
            msg = translate(
                "在 PMX 模型的顶点组“{}”中，权重为 1 且不重合的顶点少于三个。"
            ).format(vg_name)
            operator.report(type={'ERROR'}, message=msg)
            return None, None, None, False

    show_object(face_obj)
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
            truncate(vert.co.x * PMX_IMPORT_SCALE, ),
            truncate(vert.co.y * PMX_IMPORT_SCALE),
            truncate(vert.co.z * PMX_IMPORT_SCALE))
        if key in source_face_vert_location:
            v_count = source_face_vert_location[key]
            if v_count > 1:
                continue
            target_face_vert_location.append(vert)
    # 面部松散块
    islands = [island for island in get_islands(bm, verts=target_face_vert_location)["islands"]]
    # 面部待选区域  随机松散块测试 face = random.choice(islands) if islands else None
    face_area = max(islands, key=len) if islands else None
    if face_area is None:
        operator.report(type={'ERROR'},
                        message=translate(
                            "面部物体匹配失败。源模型与目标模型的初始姿态必须完全一致，请检查。"))
        return None, None, None, False

    return face_obj, face_area, bm, True


def matching(sources, targets, direction):
    """
    尽可能地对物体配对，兼容 PMX2ABC。

    返回 (映射表, 配对异常记录)：
        映射表：{源物体: 目标物体}
        异常记录：[(类别, 源名称, 目标名称或列表[, 第一个匹配的源名称]), ...]，
                 类别为 one_to_many / many_to_one；多对一额外记录第一个匹配的源名称，用于提示中排在源列表最前

    配对优先级（名称与 loop 数一致已足够可靠，额外加 5% 邻域抽检防止极端案例，例如左右眼分属不同对象但命名相同）：
    0. 源与目标都只有一个网格：名称可能完全不同（如 000_颜 对 娜维娅_mesh），直接按 PAIRING_TOLERANCE 做 27 邻域全量匹配
    1. 名称一致且 loop 数一致：先对全部候选做 5% 顶点邻域抽样校验
       - 只剩 1 个候选：直接配对
       - 仍有多个候选：用贴图内容筛选（如发与发+、脸与腮红）
         仅当所有面都属于材质槽中的同一个材质时，校验该材质中标签为 Mmd Base Tex 的图像节点
         （图像需与激活的输出节点连通、去重后唯一，比较图像内容而非材质名）
       - 仍多个候选：27 邻域全量匹配
       - 仍多个候选：记录为一对多，不参与预设传递
    2. 名称一致但 loop 数不一致（换头等网格编辑）：27 邻域全量匹配，误差在内部常量 PAIRING_TOLERANCE（0.2）以内算配对成功
       名称不一致：27 邻域精确全量匹配，不套用误差
       多个候选：记录为一对多，不参与预设传递

    配对关系按 source → target 的方向判定：
        一对多（一个源对应多个目标）：异常，不传递。一对多提升到多对多太极端太复杂了，不考虑。
        多对一（多个源对应同一个目标）：以第一个匹配到的结果为准，仅记录提示（匹配条件已足够严格，能同时命中的源本身一致）

    注：名称指对象名称；材质名称、MMD 材质名称可能被编辑替换，因此不参与校验。
    """
    # 目标在入参中的顺序，异常提示中用于稳定展示候选顺序
    target_order = {target: index for index, target in enumerate(targets)}
    # 最终配对结果，格式为 {源物体: 目标物体}
    source_target_map = {}
    # 已被占用的目标集合
    used_targets = set()
    # 目标物体 → 第一个配对成功的源物体，多对一提示中用于标明首个匹配结果
    target_owner = {}
    # 配对异常记录，元素为 (类别, 源名称, 目标名称或列表[, 第一个匹配的源名称])
    pair_issues = []
    # 第一轮没有配对的源物体，按名称情况区分后续使用的匹配方式
    # 名称一致但loop数不一致（换头等网格编辑）：允许误差
    pending_tolerance = []
    # 名称不一致或名称+loop一致但校验未通过：精确匹配
    pending_exact = []

    def assign(source, target):
        """配对；目标已被占用时视为多对一，以第一个匹配到的结果为准，仅记录异常"""
        if target in used_targets:
            pair_issues.append(('many_to_one', source.name, target.name, target_owner[target].name))
            return
        source_target_map[source] = target
        used_targets.add(target)
        target_owner[target] = source

    def assign_by_candidates(source, candidates):
        """候选唯一时配对；多个候选视为一对多异常，不传递"""
        if len(candidates) == 1:
            assign(source, candidates[0])
        elif candidates:
            pair_issues.append(('one_to_many', source.name, join_names(candidates, target_order)))

    # 源与目标都只有一个网格时，名称可能完全不同（如 000_颜 对 娜维娅_mesh），直接按误差全量匹配
    if len(sources) == 1 and len(targets) == 1:
        assign_by_candidates(
            sources[0],
            match_by_vertices(sources[0], targets, direction, tolerance=PAIRING_TOLERANCE))
        return source_target_map, pair_issues

    # 第一轮：名称 + loop数 + 5%顶点邻域抽样，常规模型绝大多数可以在这一轮直接完成配对
    for source in sources:
        source_name = get_normalized_name(source)
        source_loop_count = len(source.data.loops)
        candidates = [
            target for target in targets
            if get_normalized_name(target) == source_name and len(target.data.loops) == source_loop_count
        ]
        # 名称与loop数一致仍可能是位置完全不同的物体（如左右眼分属不同网格），先用5%顶点做邻域抽样校验
        if candidates:
            candidates = [target for target in candidates if verify_vertex_sample(source, target, direction)]
        if len(candidates) == 1:
            assign(source, candidates[0])
            continue
        if candidates:
            # 抽样后仍有多候选时，单材质网格用材质贴图内容区分（如发与发+，面与腮红等等网格完全一致但材质不同的情形）
            candidates = filter_by_material_texture(source, candidates)
            # 如果依然存在多个候选，则全量比对
            if len(candidates) > 1:
                candidates = match_by_vertices(source, candidates, direction)
            if candidates:
                assign_by_candidates(source, candidates)
            else:
                pending_exact.append(source)
            continue
        # 名称一致但loop数不一致时按误差匹配，其余情况按精确匹配
        if any(get_normalized_name(target) == source_name for target in targets):
            pending_tolerance.append(source)
        else:
            # 兼容 PMX2ABC，必定会走全量校验
            pending_exact.append(source)

    # 第二轮：名称一致但loop数不一致（换头等网格编辑），带误差做全量匹配
    for source in pending_tolerance:
        assign_by_candidates(source, match_by_vertices(source, targets, direction, tolerance=PAIRING_TOLERANCE))

    # 第三轮：名称不一致，做精确全量匹配。兼容 PMX2ABC，必定会走全量校验
    for source in pending_exact:
        assign_by_candidates(source, match_by_vertices(source, targets, direction))
    return source_target_map, pair_issues


def join_names(objects, target_order=None):
    """把物体名称拼接成提示文本（名称用双引号包裹）；传入目标顺序时按该顺序排序"""
    if target_order is not None:
        objects = sorted(objects, key=target_order.get)
    return ", ".join(f'"{obj.name}"' for obj in objects)


def get_normalized_name(obj):
    """去掉PMX名称前缀与重名后缀，用于名称一致性比较"""
    match = PMX_NAME_PATTERN.match(obj.name)
    return match.group('name') if match else obj.name


def get_available_name(collection, name):
    """返回集合中可用的名称，已被占用时追加 .001、.002 等后缀"""
    if name not in collection:
        return name
    index = 1
    while f'{name}.{index:03d}' in collection:
        index += 1
    return f'{name}.{index:03d}'


def get_id_collection(id_block):
    """返回 ID 数据块所属的 bpy.data 集合"""
    if isinstance(id_block, bpy.types.Object):
        return bpy.data.objects
    if isinstance(id_block, bpy.types.Mesh):
        return bpy.data.meshes
    if isinstance(id_block, bpy.types.Armature):
        return bpy.data.armatures
    if isinstance(id_block, bpy.types.Material):
        return bpy.data.materials
    return bpy.data.images


def swap_id_names(id_block, other):
    """交换两个 ID 的名称，先改临时名避免 Blender 自动追加后缀"""
    name = id_block.name
    other_name = other.name
    id_block.name = get_available_name(get_id_collection(id_block), 'KAFEI_SWAP_TEMP')
    other.name = name
    id_block.name = other_name


def get_material_images(materials):
    """收集材质节点树中实际使用的贴图"""
    images = set()
    for material in materials:
        if not material.use_nodes or material.node_tree is None:
            continue
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image is not None:
                images.add(node.image)
    return images


def get_model_ids(root):
    """收集模型根下的对象、网格/骨架数据、材质与材质使用的贴图"""
    objects = {root, *root.children_recursive}
    datas = {obj.data for obj in objects if obj.type in {'MESH', 'ARMATURE'} and obj.data}
    materials = set()
    for obj in objects:
        if obj.type == 'MESH':
            materials.update(material for material in obj.data.materials if material is not None)
    return objects, datas, materials, get_material_images(materials)


def remove_suffix_in_group(id_blocks, source_ids, allow_swap, require_extension=False):
    """移除一组 ID 名称中的重名后缀，多轮处理以应对 .001.001 这类嵌套后缀

    基名空闲时直接改名，被源模型占用且允许交换时交换，其余情况静默跳过。
    require_extension 用于贴图：只处理「图像.png.001」这种后缀位于扩展名之后的名称，
    去掉后缀后必须仍带扩展名，否则视为原名称不改。
    """
    for _ in range(8):
        changed = False
        for id_block in sorted(id_blocks, key=lambda item: item.name):
            match = DUPLICATE_SUFFIX_PATTERN.match(id_block.name)
            if match is None:
                continue
            base = match.group('base')
            if require_extension and not os.path.splitext(base)[1]:
                continue
            if len(base.encode('utf-8')) >= MAX_ID_NAME_LENGTH:
                continue
            collection = get_id_collection(id_block)
            if base not in collection:
                id_block.name = base
                changed = True
                continue
            holder = collection[base]
            if holder in id_blocks:
                # 目标模型内部本来就存在同名条目（如逐个网格的 mesh data），按规则跳过
                continue
            if allow_swap and holder in source_ids:
                swap_id_names(id_block, holder)
                changed = True
        if not changed:
            break


def remove_duplicate_suffix(source_root, target_root):
    """
    移除目标模型对象、数据、材质与贴图中的重名后缀

    基名空闲时直接改名；被源模型占用时交换名称；被目标自身占用或第三方数据占用时跳过。
    材质无论是否开启材质传递都会处理目标当前材质槽中的材质；开启传递后目标材质即源材质，
    与源共用数据块，此时按「目标内部同名」跳过，不会改动预设自身名称。
    贴图只处理「图像.png.001」这类后缀位于扩展名之后、且与源模型贴图同名的名称。
    """
    objects, datas, materials, images = get_model_ids(target_root)
    source_objects, source_datas, source_materials, source_images = get_model_ids(source_root)
    remove_suffix_in_group(objects, source_objects, True)
    remove_suffix_in_group(datas, source_datas, True)
    remove_suffix_in_group(materials, source_materials, True)
    remove_suffix_in_group(images, source_images, True, require_extension=True)


def verify_vertex_sample(source, target, direction, ratio=0.05):
    """按比例抽样源顶点，在目标顶点的27邻域中做存在性校验

    名称与loop数一致只能说明命名和面角数量相同，不能排除位置完全不同的极端情况。
    这里抽样5%的源顶点，要求每个抽样点都能在目标的27邻域（±1精度格）中找到对应顶点。
    """
    source_vertices = source.data.vertices
    vertex_count = len(source_vertices)
    if vertex_count == 0 or len(target.data.vertices) == 0:
        return False
    sample_count = max(3, int(vertex_count * ratio))
    if sample_count >= vertex_count:
        sample_indices = range(vertex_count)
    else:
        step = vertex_count / sample_count
        sample_indices = [int(index * step) for index in range(sample_count)]
    # 目标顶点只按精确格记录，抽样点自身负责探测27邻域，避免构建27倍大小的字典
    target_keys = {gen_key(vert, direction[-3:]) for vert in target.data.vertices}
    for index in sample_indices:
        co = source_vertices[index].co
        x = truncate(co.x)
        y = truncate(co.y)
        z = truncate(co.z)
        found = False
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for k in (-1, 0, 1):
                    if (x + i, y + j, z + k) in target_keys:
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if not found:
            return False
    return True


def get_vertex_neighborhood(mesh):
    """构建顶点27邻域位置表，用于顶点位置的全量匹配"""
    vertices = {}
    for vert in mesh.vertices:
        for i in range(-1, 2):
            for j in range(-1, 2):
                for k in range(-1, 2):
                    key = (
                        truncate(vert.co.x) + i,
                        truncate(vert.co.y) + j,
                        truncate(vert.co.z) + k)
                    vertices[key] = vertices.get(key, 0) + 1
    return vertices


def match_by_vertices(source, targets, direction, tolerance=0):
    """27邻域全量匹配：用源顶点的邻域位置表校验目标顶点，返回匹配到的目标物体列表

    tolerance 为「误差」参数（0~1，仅PMX2PMX使用）：
    1. 顶点数相对差 |源-目标| / max(源, 目标) 不得超过 tolerance，否则直接跳过该目标；
    2. 目标顶点命中源27邻域的比例需达到 1 - tolerance，否则视为不匹配。
    tolerance 为 0 时要求顶点数完全一致且全部目标顶点命中。
    """
    source_v_count = len(source.data.vertices)
    if source_v_count == 0:
        return []
    # 源物体的邻域位置表只构建一次，供所有候选目标复用
    source_vertices = get_vertex_neighborhood(source.data)
    matched = []
    for target in targets:
        target_v_count = len(target.data.vertices)
        if target_v_count == 0:
            continue
        # 顶点数不完全一致时，允许的顶点数相对误差由tolerance决定
        if tolerance == 0:
            if source_v_count != target_v_count:
                continue
        elif abs(source_v_count - target_v_count) / max(source_v_count, target_v_count) > tolerance:
            continue
        match_count = 0
        for vert in target.data.vertices:
            if gen_key(vert, direction[-3:]) in source_vertices:
                match_count += 1
        if tolerance == 0:
            if match_count == target_v_count:
                matched.append(target)
        elif match_count / target_v_count >= 1 - tolerance:
            matched.append(target)
    return matched


def get_single_material(obj):
    """返回网格所有面实际使用的唯一材质；面分属多个材质或没有面时返回None"""
    mesh = obj.data
    if not mesh.polygons:
        return None
    material_index = mesh.polygons[0].material_index
    for polygon in mesh.polygons:
        if polygon.material_index != material_index:
            return None
    if material_index >= len(mesh.materials):
        return None
    return mesh.materials[material_index]


def get_image_signature(image, cache):
    """计算图像内容签名（尺寸 + 像素哈希），用于判断贴图内容是否一致"""
    signature = cache.get(image.name)
    if signature is not None:
        return signature
    width, height = image.size
    if width == 0 or height == 0:
        # 图像未加载或文件丢失，无法比较内容
        signature = ('missing', image.name)
    else:
        try:
            buffer = array.array('f', [0.0]) * (width * height * 4)
            image.pixels.foreach_get(buffer)
            signature = (width, height, hashlib.md5(memoryview(buffer)).hexdigest())
        except (RuntimeError, TypeError):
            signature = ('unreadable', image.name)
    cache[image.name] = signature
    return signature


def get_output_connected_nodes(node_tree):
    """返回与激活的输出节点连通的节点集合（沿输入链接反向遍历），不考虑节点组"""
    output_node = None
    for node in node_tree.nodes:
        # is_active_output 仅输出节点具备该属性
        if getattr(node, 'is_active_output', False):
            output_node = node
            break
    if output_node is None:
        return set()
    connected = set()
    stack = [output_node]
    while stack:
        node = stack.pop()
        if node in connected:
            continue
        connected.add(node)
        for socket in node.inputs:
            for link in socket.links:
                stack.append(link.from_node)
    return connected


def get_material_texture_signature(material, cache):
    """
    返回材质中标签为 Mmd Base Tex 的图像内容签名

    仅当图像节点与激活的输出节点连通、且图像去重后唯一时返回签名，否则返回 None。
    """
    if material is None or not material.use_nodes or material.node_tree is None:
        return None
    connected_nodes = get_output_connected_nodes(material.node_tree)
    images = []
    for node in material.node_tree.nodes:
        if node.type != 'TEX_IMAGE' or node.image is None:
            continue
        if node.label != "Mmd Base Tex":
            continue
        # 图像必须与激活的输出节点连通才算被使用
        if node not in connected_nodes:
            continue
        if node.image not in images:
            images.append(node.image)
    # 去重后必须唯一，否则无法用于区分
    if len(images) != 1:
        return None
    signature = get_image_signature(images[0], cache)
    if signature[0] in {'missing', 'unreadable'}:
        return None
    return signature


def filter_by_material_texture(source, candidates):
    """单材质网格按材质贴图内容筛选候选，任一侧无法比较时返回原候选"""
    cache = {}
    source_signature = get_material_texture_signature(get_single_material(source), cache)
    if source_signature is None:
        return candidates
    matched = []
    for candidate in candidates:
        target_signature = get_material_texture_signature(get_single_material(candidate), cache)
        if target_signature == source_signature:
            matched.append(candidate)
    # 贴图都不一致时不做排除，交由顶点位置匹配处理
    return matched or candidates


def gen_key(vert, object_type):
    if object_type == "PMX":
        return (
            truncate(vert.co.x),
            truncate(vert.co.y),
            truncate(vert.co.z))
    elif object_type == "ABC":
        return (
            truncate(vert.co.x * PMX_IMPORT_SCALE),
            truncate(vert.co.y * PMX_IMPORT_SCALE),
            truncate(vert.co.z * PMX_IMPORT_SCALE))


def link_normal(mapping, props):
    """
    传递源物体自定义拆边法向到目标物体上。
    该操作的目的是通过传递自定义拆边法向，配合abc烘焙时不导出法向信息，以此来减少abc文件的体积与烘焙时间。
    传入的mapping是配对完成后的内容，拓扑一致，所以映射方式为拓扑

    源物体的锐边信息需要同步吗？不需要，如果源物体有锐边，推荐重新导出pmx进行预设的构建。
    拆边法向的常见场景是通过合并顶点重新计算法向，修复面与面之间的折痕，但是这样会更改拓扑结构，所以插件不支持这个操作。需要用户在检查模型阶段完成修复操作，或手动添加数据传递修改器
    将修复完成后的pmx模型重新导入后，该模型已经具备了修复后的法向，所以PMX->PMX的情况下无需传递法向

    # 更新：在blender3.x以上的环境下，我们无法自由选择读取（缓存的）什么数据。所以暂时不考虑法向的传递
    更新：虽然可能需要二次导出abc文件（第一次mmd中无法向烘焙，第二次在其它3D软件中导入导出abc文件以适配blender3.x以上的缓存修改器），但依然可能会有abc文件过大的情况，或者保存abc文件的需求。
    """
    normal_flag = props.normal_flag
    if not normal_flag:
        return

    direction = props.direction
    if direction == "PMX2PMX":
        return

    fallback_map = {}
    for source, target in mapping.items():
        # 优先直接写入自定义法向，省去每个对象创建、移动、应用DataTransfer修改器的算子开销
        # 直接写入不可用时（如拓扑不一致、当前版本不支持）退化为修改器方案
        if not copy_custom_normals(source, target):
            fallback_map[source] = target

        # 获取target网格序列缓存修改器，取消面的读取
        for cache_modifier in modifiers_by_type(target, "MESH_SEQUENCE_CACHE"):
            cache_modifier.read_data = {'VERT', 'UV', 'COLOR'}

    if fallback_map:
        link_normal_by_modifier(fallback_map)


def copy_custom_normals(source, target):
    """
    直接写入自定义拆边法向，避免DataTransfer修改器。
    拓扑一致（面拐数量相同）且当前版本支持写入时返回True，否则返回False由调用方退化为修改器方案。
    3.x / 4.0 需先调用calc_normals_split缓存面拐法向；4.1起calc_normals_split已被移除，改用corner_normals直接读取
    3.x / 4.0 的自定义法向是否生效取决于目标自身的自动平滑设置，与原修改器方案保持一致，此处不做修改
    """
    source_mesh = source.data
    target_mesh = target.data
    if len(source_mesh.loops) != len(target_mesh.loops):
        return False

    set_custom_normals = getattr(target_mesh, "normals_split_custom_set", None)
    if set_custom_normals is None:
        return False

    calc_normals_split = getattr(source_mesh, "calc_normals_split", None)
    if calc_normals_split is None:
        normals = [normal.vector.copy() for normal in source_mesh.corner_normals]
    else:
        calc_normals_split()
        normals = [loop.normal.copy() for loop in source_mesh.loops]

    if len(normals) != len(target_mesh.loops):
        return False

    set_custom_normals(normals)
    return True


def link_normal_by_modifier(mapping):
    """退化为DataTransfer修改器方案的实现"""
    # 记录物体修改器显示情况，然后关闭修改器的显示，防止对后续传递造成影响（如焊接等修改器会使source target拓扑不一致）
    # 物体 -> 物体修改器是否显示
    obj_mod_show_map = {}
    for source in mapping:
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

        # 执行生成数据层，然后应用掉该修改器（4.2之前，法向传递时提示开启自动平滑着色，但开启与否不影响插件的最终执行结果，4.2之后无提示）
        bpy.ops.object.datalayout_transfer(modifier=modifier.name)
        bpy.ops.object.modifier_apply(modifier=modifier.name)

    # 恢复物体修改器显示情况
    for source in mapping:
        source_mod_show_list = obj_mod_show_map.get(source.name)
        for index, mod in enumerate(source.modifiers):
            mod.show_viewport = source_mod_show_list[index]


def import_abc_file(filepath):
    """导入abc文件"""
    bpy.ops.wm.alembic_import(filepath=filepath)
    return bpy.context.selected_objects


def reset_cache_param(operator, props):
    """
    重新设置缓存修改器参数，可能出现匹配不上的情况，这可能是多次修改等操作导致的顶点数不一致的问题（一般情况下相差几个顶点吧，暂不做额外处理）

    # 网格对象：
    # 如果物体使用的缓存文件不同，则根据缓存文件分组
    # 如果使用的缓存文件相同，则根据xform_0_material_0 分组
    # 缓存对象：
    # 则根据xform_0_material_0分组
    """

    abc_filepath = bpy.path.abspath(props.abc_filepath)
    selected_only = props.selected_only

    # 记录选择状态
    active_object = bpy.context.active_object
    selected_objects = [obj for obj in bpy.context.selected_objects]

    target_objs = []
    if selected_only:
        selected_objects = bpy.context.selected_objects
        ancestors = {find_ancestor(obj) for obj in selected_objects}
        for ancestor in ancestors:
            mesh_objs = get_mesh_objs(ancestor)
            if mesh_objs:
                target_objs.extend(mesh_objs)
    else:
        target_objs = bpy.context.scene.objects

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
                if source2_obj.name == target_name:
                    continue
                source2_info = obj_info_map.get(source2_obj.name)
                if source2_info is not None:
                    source2_infos.append(source2_info)
            # 自己和自己配对（由于之前已经配对过一次，所以这里配对使用的是旧number顺序）
            if match_info(source2_infos, target_infos):
                link_cache(source2_infos, target_infos, target_obj_flag_map)

    for source_obj in source_objs:
        bpy.data.objects.remove(source_obj, do_unlink=True)

    if selected_only:
        restore_selection(selected_objects, active_object)

    # 输出异常信息
    if all(target_obj_flag_map.values()) and not non_compliant_list:
        pass
    else:
        msg = ''
        if non_compliant_list:
            msg = msg + translate("以下物体缓存信息无效：") + f'\n{non_compliant_list}\n'
        false_keys = [key for key, value in target_obj_flag_map.items() if not value]
        if false_keys:
            msg = msg + translate(
                "以下物体配对失败，请检查网格顶点数或缓存文件名称：") + f'\n{false_keys}'
        operator.report({'WARNING'}, msg)
        operator.report({'WARNING'},
                        translate("存在未成功配对对象，点击查看报告↑↑↑"))


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


def create_abc_parent(source_root, source_target_map, props):
    """为ABC模型创建父级对象，方便后续操作与管理"""
    direction = props.direction
    if direction != 'PMX2ABC':
        return

    targets = list(source_target_map.values())
    # 所有目标已经挂在同一个父级下时无需处理，其余情况（无父级、部分无父级、父级不一致）一律重建
    parents = {target.parent for target in targets}
    if len(parents) == 1 and None not in parents:
        return

    # 创建ABC父级空对象
    source_name = source_root.name
    if 'pmx' in source_name.lower():
        # 替换名称中的"pmx"为"abc"
        abc_name = case_insensitive_replace("pmx", "abc", source_name)
    else:
        # 如果原名称不含"pmx"，则添加" abc"后缀
        abc_name = source_name + " abc"

    abc_root = bpy.data.objects.new(abc_name, None)

    # 将父对象链接到第一个子对象所在的集合中
    collection = next((target.users_collection[0] for target in targets
                       if target.users_collection), None)
    if collection:
        collection.objects.link(abc_root)

    # 设置所有目标对象的父对象为新创建的abc_root
    for target in targets:
        target.parent = abc_root


def show_objects(display_list):
    """记录对象的可见性状态并取消隐藏所有对象"""
    visibility_map = {}
    for obj in display_list:
        visibility_map[obj] = (obj.hide_select, obj.hide_get(), obj.hide_viewport, obj.hide_render)
        show_object(obj)
    return visibility_map


def modifiers_by_type(obj, typename):
    """ 通过类型获取修改器 """
    return [x for x in obj.modifiers if x.type == typename]


def link_uv(source_target_map, props):
    """传递源物体UV到目标物体上"""
    # 用物体的顶点数等数据是否相等来校验两个物体是否是一样的进而传递UV等内容，并不准确。
    # （比如将物体拆边后，虽然顶点数边数不一致，但依然能够传递UV），但这里不考虑这些内容
    if not props.uv_flag:
        return

    # 移除之前生成的UV，避免重复执行时UV层数累加
    for source, target in source_target_map.items():
        remove_same_name_uv_layers(source, target)

    for source, target in source_target_map.items():
        copy_uv_layers(source, target, props.direction)


_warning_map_context = contextvars.ContextVar("transfer_preset_warning_map", default=None)


@contextlib.contextmanager
def collect_warnings():
    """在with范围内收集警告，格式为 {警告类别: [提示文本]}"""
    warning_map = {}
    token = _warning_map_context.set(warning_map)
    try:
        yield warning_map
    finally:
        _warning_map_context.reset(token)


def add_warning(category, record):
    """记录一条警告；未处于collect_warnings范围内时忽略"""
    warning_map = _warning_map_context.get()
    if warning_map is None:
        return
    records = warning_map.setdefault(category, [])
    # 同一配对可能因多个UV层重复记录，这里去重
    if record not in records:
        records.append(record)


# 警告类别 -> 提示标题（中文为msgid，英文在m17n的en_US中翻译），具体记录内容由report_warnings格式化
WARNING_HEADERS = {
    "loop_mismatch": "以下内容拓扑信息不一致，已跳过UV传递：",
    "uv_limit": "以下内容传递UV时达到最大上限，如有异常，请在执行前清除目标物体自身UV：",
    "material_mismatch": "以下内容多材质槽传递不完整，请检查网格拓扑与初始姿态：",
}


def report_warnings(operator, warning_map):
    """把传递过程中收集到的警告按类别汇总提示"""
    for category, records in warning_map.items():
        header = WARNING_HEADERS.get(category, category)
        # 记录格式为（源名称，目标名称，其它信息...），其它信息仅记录不输出
        lines = [translate(header)]
        lines.extend("{} → {}".format(record[0], record[1]) for record in records)
        operator.report(type={'WARNING'}, message="\n".join(lines))


def remove_same_name_uv_layers(source, target):
    """删除目标物体中与源物体同名的UV图层，避免重复执行时UV层数累加"""
    source_uv_names = {uv_layer.name for uv_layer in source.data.uv_layers}
    indexes_to_remove = [index for index, uv_layer in enumerate(target.data.uv_layers)
                         if uv_layer.name in source_uv_names]
    # 逆序删除，顺序删除会因索引变化而漏删
    for index in sorted(indexes_to_remove, reverse=True):
        target.data.uv_layers.remove(target.data.uv_layers[index])


def copy_uv_layers(source, target, direction):
    """按loop顺序把源物体的UV图层复制到目标物体"""
    source_mesh = source.data
    target_mesh = target.data
    if len(source_mesh.uv_layers) == 0:
        return
    # 如果loop值不一致，则跳过本次复制，但这不意味着错误
    # 比如3.x导入abc复制uv出问题，用2.x导入并拷贝到当前工程，执行插件依然可以进行后续逻辑
    if len(source_mesh.loops) != len(target_mesh.loops):
        # 仅记录名称与loop信息，具体提示由report_warnings统一格式化
        add_warning("loop_mismatch",
                    (source.name, target.name, len(source_mesh.loops), len(target_mesh.loops)))
        return

    # 记录源物体活动的UV、用于渲染的UV、原始uv数量，以及目标物体原始uv数量
    source_active_index = source_mesh.uv_layers.active_index
    source_render_index = next(
        (index for index, uv_layer in enumerate(source_mesh.uv_layers) if uv_layer.active_render), 0)
    source_uv_count = len(source_mesh.uv_layers)
    target_uv_count = len(target_mesh.uv_layers)

    # 删除PMX2PMX情况下目标物体的UV，否则UV数量可能会达到上限
    if direction == "PMX2PMX":
        for uv_layer in reversed(target_mesh.uv_layers):
            target_mesh.uv_layers.remove(uv_layer)
        # 已全部删除，后续按「目标原本无 UV」处理，激活层偏移为 0
        target_uv_count = 0

    for uv_layer in source_mesh.uv_layers:
        # 新建uv
        # blender 3.0以下（如2.93）导入abc，uv命名是"uv"，而不是"UVMap"
        # 所以除非刻意进行额外操作，否则出现"UV名称已存在（或者说UV命名冲突，不过实际名称会自动修改并不会冲突）"的问题的可能性很低，这里对此种情况暂不处理。
        # pmx对象最多5个uv，abc对象1个uv（3.0以下导入时），通常情况下，不会超过8个的上限，如超过，这里对此种情况暂不处理。
        new_uv = target_mesh.uv_layers.new(name=uv_layer.name)
        if new_uv is None:
            # 目标物体uv数量达到上限，仅记录名称
            add_warning("uv_limit", (source.name, target.name))
            continue
        # 前面已校验loop数一致，直接按loop顺序拷贝UV坐标
        # uv_layer.data 的长度与 mesh.loops 一致，存储的是面角数据。
        # 只要网格面未发生变化，各面的角数就不会改变。
        # 因此，无论相邻面之间的重合顶点是否合并，面角数据的数量和结构都保持不变。
        uv_data = [0.0] * (len(uv_layer.data) * 2)
        uv_layer.data.foreach_get("uv", uv_data)
        new_uv.data.foreach_set("uv", uv_data)

    # 同步目标物体UV的激活状态：仅在全部复制成功时设置，其它情况暂不考虑
    target_current_uv_count = len(target_mesh.uv_layers)
    if target_uv_count == 0 and target_current_uv_count == source_uv_count:
        index_offset = 0
    elif target_uv_count != 0 and target_current_uv_count == source_uv_count + target_uv_count:
        index_offset = target_uv_count
    else:
        # uv数量达到上限，前面已跳过
        return
    target_mesh.uv_layers[source_active_index + index_offset].active = True
    target_mesh.uv_layers[source_render_index + index_offset].active_render = True


def link_materials(source_target_map, props):
    """关联源物体材质到目标物体上，并按面质心映射多材质槽"""
    if not props.material_flag:
        return

    direction = props.direction
    for source, target in source_target_map.items():
        # 复制材质槽
        target.data.materials.clear()
        for material in source.data.materials:
            target.data.materials.append(material)

        # 单材质槽不需要逐面映射
        if len(source.material_slots) <= 1:
            continue

        # 通过面的质心坐标（局部）来确定源和目标的映射关系，以此来关联材质。
        # 需要说明的是，针对大多数模型，只有单材质槽，因此不会进入后续代码。
        # 只有人为设置源物体为多材质时，才会进入后续代码（部分三渲二的材质槽含描边材质，但描边材质不会赋予到面上）。
        # 因此，虽然面质心可能会受重合面影响，但那只存在于重合面属于同一网格且为不同材质，非正常逻辑。

        # 源物体质心与面的map，源物体面与对应材质的map
        source_center_poly_map = {}
        source_poly_material_map = {}
        for source_poly in source.data.polygons:
            source_poly_material_map[source_poly.index] = source_poly.material_index
            # 将质心坐标（局部）进行精度误差处理，得到的结果保存在map中
            # 坐标值 / PRECISION后截断保留整数，误差为±1，因此额外覆盖一圈邻域
            for i in range(-1, 2):
                for j in range(-1, 2):
                    for k in range(-1, 2):
                        key = (
                            truncate(source_poly.center.x) + i,
                            truncate(source_poly.center.y) + j,
                            truncate(source_poly.center.z) + k)
                        source_center_poly_map[key] = source_poly.index

        match_count = 0
        for target_poly in target.data.polygons:
            # abc模型导入时按PMX_IMPORT_SCALE缩放，质心坐标需要换算回pmx的尺度
            if direction[-3:] == 'ABC':
                key = (
                    truncate(target_poly.center.x * PMX_IMPORT_SCALE),
                    truncate(target_poly.center.y * PMX_IMPORT_SCALE),
                    truncate(target_poly.center.z * PMX_IMPORT_SCALE))
            else:
                key = (
                    truncate(target_poly.center.x),
                    truncate(target_poly.center.y),
                    truncate(target_poly.center.z))
            if key in source_center_poly_map:
                match_count += 1
                source_poly = source_center_poly_map[key]
                target_poly.material_index = source_poly_material_map[source_poly]

        if match_count != len(source.data.polygons):
            add_warning("material_mismatch", (source.name, target.name))


def link_vertices_group(source_armature, target_armature, mapping, props):
    """传递源物体顶点组到目标物体上（正序）"""
    direction = props.direction
    vgs_flag = props.vgs_flag
    if not vgs_flag:
        return

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


def link_vertices_weight(source_armature, target_armature, mapping, props):
    """传递源物体顶点权重到目标物体上（正序）"""
    direction = props.direction
    vgs_flag = props.vgs_flag
    if not vgs_flag:
        return

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


def link_modifiers(mapping, props):
    """传递源物体修改器到目标物体上（保留网格序列缓存修改器，删除骨架修改器）"""
    direction = props.direction
    modifiers_flag = props.modifiers_flag
    if not modifiers_flag:
        return

    # 软体/多重分辨率修改器要求原始数据，无法重建；骨架修改器会让目标错误绑定到源骨架，均不复制
    skip_types = {'SOFT_BODY', 'MULTIRES', 'ARMATURE'}
    # ABC 保留网格序列缓存，PMX 保留骨架
    keep_type = 'MESH_SEQUENCE_CACHE' if direction[-3:] == 'ABC' else 'ARMATURE'
    # 可写属性列表按修改器类型缓存，避免每个对象重复遍历RNA
    property_cache = {}

    def get_writable_properties(modifier_type, modifier):
        identifiers = property_cache.get(modifier_type)
        if identifiers is None:
            identifiers = [p.identifier for p in modifier.bl_rna.properties if not p.is_readonly]
            property_cache[modifier_type] = identifiers
        return identifiers

    def snapshot(modifier):
        """在清空修改器之前把名称、类型与可写属性值全部读出，避免清空后引用失效"""
        modifier_type = modifier.type
        try:
            modifier_name = modifier.name
        except UnicodeDecodeError:
            # 历史数据的修改器名称可能不是UTF-8，读取会报错，退化为按类型命名
            modifier_name = modifier_type
        values = {}
        for prop in get_writable_properties(modifier_type, modifier):
            if prop == "name":
                continue
            values[prop] = getattr(modifier, prop)
        return modifier_name, modifier_type, values

    for source, target in mapping.items():
        # 记录目标自身需要保留的修改器及其原索引
        target_own_entries = [(index, snapshot(modifier)) for index, modifier in enumerate(target.modifiers)
                              if modifier.type == keep_type]
        # 先按源修改器顺序排列，再把目标自身的修改器插回原索引位置，与原「逐个上移」的结果一致
        entries = [snapshot(modifier) for modifier in source.modifiers if modifier.type not in skip_types]
        for index, entry in sorted(target_own_entries, key=lambda item: item[0]):
            entries.insert(min(index, len(entries)), entry)

        target.modifiers.clear()

        for modifier_name, modifier_type, values in entries:
            new_modifier = target.modifiers.new(modifier_name, modifier_type)
            for prop, value in values.items():
                # 如果修改器涉及到source对象的引用，则将其修改为target的引用
                if isinstance(value, bpy.types.Object):
                    value = mapping.get(value, value)
                setattr(new_modifier, prop, value)


if __name__ == "__main__":
    pass
