import bmesh
import bpy

from ..constants import PMX_NAME_PATTERN

from ..utils import (
    deselect_all_objects,
    find_pmx_armature,
    find_pmx_objects,
    find_pmx_root_with_child,
    get_collection,
    is_mmd_tools_enabled,
    restore_selection,
    select_and_activate,
    translate,
)
class MergeVerticesOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.merge_vertices"
    bl_label = "合并顶点"
    bl_description = "按距离合并顶点，合并间距1e-05，并重设法向。支持一次选择多个网格对象并分别处理。在物体模式，作用范围为选择的物体；在编辑模式，作用范围为选择的顶点"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}
        self.merge_vertices(context)
        return {'FINISHED'}

    def check_props(self, context):
        objs = context.selected_objects
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=translate("请至少选择一个对象！"))
            return False
        active_object = context.active_object
        if active_object is None:
            self.report(type={'ERROR'}, message=translate("请激活对象！"))
            return False
        if active_object.type != "MESH":
            self.report(type={'ERROR'}, message=translate("请激活网格对象！"))
            return False
        return True

    def merge_vertices(self, context):
        objs = context.selected_objects
        active_object = context.active_object

        total_vertices = self.get_total_vertices(context, objs)

        if active_object and active_object.mode == "EDIT":
            bpy.ops.mesh.remove_doubles(threshold=1e-05)
            bpy.ops.mesh.normals_tools(mode='RESET')
        else:
            target_objs = [obj for obj in objs if obj.type == "MESH"]
            try:
                if target_objs:
                    deselect_all_objects()
                    for obj in target_objs:
                        select_and_activate(obj)
                    # 多物体编辑模式下一次完成合并与法向处理
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_mode(type="VERT")
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.remove_doubles(threshold=1e-05)
                    bpy.ops.mesh.normals_tools(mode='RESET')
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bpy.ops.object.mode_set(mode='OBJECT')
            finally:
                restore_selection(objs, active_object)

        total_vertices_after = self.get_total_vertices(context, objs)
        self.report(type={'INFO'}, message=translate("移除了 {} 个顶点").format(
            total_vertices - total_vertices_after))

    def get_total_vertices(self, context, objs):
        """强制刷新后计算总顶点数，仅考虑网格自身数据，不考虑修改器的影响"""

        mode = context.active_object.mode
        bpy.ops.object.mode_set(mode='OBJECT')
        total_vertices = 0

        for obj in objs:
            if obj.type == 'MESH':
                mesh = obj.data
                mesh.update()
                total_vertices += len(mesh.vertices)

        if mode:
            bpy.ops.object.mode_set(mode=mode)

        return total_vertices


class DummyOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.dummy"
    bl_label = "Dummy Button"
    bl_options = {'REGISTER'}

    def execute(self, context):
        return {'FINISHED'}


class SetMatNameByObjNameOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.set_mat_name_by_obj_name"
    bl_label = "网格名称 → 材质名称"
    bl_description = "根据网格实际名称设置材质名称。支持一次选择多个网格对象并分别处理"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}
        self.rename(context)
        return {'FINISHED'}

    def check_props(self, context):
        if len(context.selected_objects) == 0:
            self.report(type={'ERROR'}, message=f'Select at least one object!')
            return False
        return True

    def rename(self, context):
        objs = context.selected_objects

        for obj in objs:
            if obj.type != "MESH":
                continue

            # 跳过多材质对象和存在空槽的对象
            materials = obj.data.materials
            if len(materials) != 1 or materials[0] is None:
                continue

            # 获取对象实际名称。名称.xxx 形式的，视为重名，暂不处理
            obj_name = obj.name
            match = PMX_NAME_PATTERN.match(obj_name)
            if match:
                obj_name = match.group('name')

            # 设置材质名称
            mat = obj.data.materials[0]
            # 复制一份，避免影响与其它物体共用的材质
            mat_new = mat.copy()
            obj.data.materials[0] = mat_new
            # 旧材质在本物体上已不再使用，若无用户则删除，避免它占用目标名称导致新材质被命名为 .xxx
            if mat.users == 0:
                bpy.data.materials.remove(mat)
            mat_new.name = obj_name
            if is_mmd_tools_enabled():
                mat_new.mmd_material.name_j = obj_name


class SetObjNameByMatNameOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.set_obj_name_by_mat_name"
    bl_label = "材质名称 → 网格名称"
    bl_description = "根据材质名称设置实际网格名称。支持一次选择多个网格对象并分别处理。"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}
        self.rename(context)
        return {'FINISHED'}

    def check_props(self, context):
        if len(context.selected_objects) == 0:
            self.report(type={'ERROR'}, message=f'Select at least one object!')
            return False
        return True

    def rename(self, context):
        objs = context.selected_objects

        for obj in objs:
            if obj.type != "MESH":
                continue

            # 跳过多材质对象和存在空槽的对象
            materials = obj.data.materials
            if len(materials) != 1 or materials[0] is None:
                continue

            # 获取网格对象名称前缀
            match = PMX_NAME_PATTERN.match(obj.name)
            prefix = ""
            if match:
                prefix = match.group('prefix')

            # 更新网格名称
            mat_name = obj.data.materials[0].name
            if prefix:
                new_name = prefix + mat_name
            else:
                new_name = mat_name

            if obj.name != new_name:
                obj.name = new_name


def round_vec(v):
    """保留三维向量的五位小数"""
    return tuple(round(coord, 5) for coord in v)


def face_key(face_verts):
    """将面顶点位置生成可比较的键（不考虑顺序）"""
    return tuple(sorted(round_vec(v) for v in face_verts))


def get_faces(obj):
    """获取对象的所有面的映射: {face_key: polygon_index}"""
    mesh = obj.data
    faces = {}
    if not mesh or not mesh.polygons:
        return faces

    for poly in mesh.polygons:
        face_verts = [mesh.vertices[i].co for i in poly.vertices]
        key = face_key(face_verts)
        faces[key] = poly.index

    return faces


class DetectOverlappingFacesOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.detect_overlapping_faces"
    bl_label = "检测网格面重合度"
    bl_description = "检测网格面之间的重合度"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not self.check_props(context):
            return {'CANCELLED'}
        self.detect_overlapping_faces(context)
        return {'FINISHED'}

    def check_props(self, context):
        active_object = context.active_object
        if not active_object:
            self.report(type={'ERROR'}, message=translate("请选择MMD模型！"))
            return False
        pmx_root = find_pmx_root_with_child(active_object)
        if not pmx_root:
            self.report(type={'ERROR'}, message=translate("请选择MMD模型！"))
            return False
        armature = find_pmx_armature(pmx_root)
        if not armature:
            self.report(type={'ERROR'}, message=translate("未找到模型骨架！"))
            return False
        return True

    def detect_overlapping_faces(self, context):
        active_object = context.active_object
        root = find_pmx_root_with_child(active_object)
        rig = find_pmx_armature(root)
        objs = find_pmx_objects(rig)

        # 切换对象模式
        deselect_all_objects()

        faces_map = {}
        for obj in objs:
            faces_map[obj] = get_faces(obj)

        msgs = []
        obj_list = list(faces_map.keys())
        for i in range(len(obj_list)):
            for j in range(i + 1, len(obj_list)):
                obj_a = obj_list[i]
                obj_b = obj_list[j]
                faces_a = faces_map[obj_a]
                faces_b = faces_map[obj_b]

                # 求交集
                intersection = set(faces_a.keys()) & set(faces_b.keys())
                if not intersection:
                    continue

                ratio_a = len(intersection) / len(faces_a)
                ratio_b = len(intersection) / len(faces_b)

                msg = translate(
                    "{} 与 {} 重合面数: {} (占比 A: {:.2%}, B: {:.2%})").format(
                    obj_a.name,
                    obj_b.name,
                    len(intersection),
                    ratio_a,
                    ratio_b
                )
                msgs.append(msg)

                # === 选中重合的面 ===
                for obj, faces in [(obj_a, faces_a), (obj_b, faces_b)]:
                    indices = [faces[key] for key in intersection]
                    select_faces_by_index(obj, indices)

        if msgs:
            combined_msg = "\n".join(msgs)
            self.report(type={'INFO'}, message=combined_msg)
            self.report(type={'INFO'},
                        message=translate("检测完成，点击查看报告↑↑↑"))
        else:
            self.report(type={'INFO'},
                        message=translate("未发现网格面之间重合"))


def select_faces_by_index(obj, face_indices):
    """在obj对象中选中指定索引的面（用bmesh）"""
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    # 清空原有选择
    for f in bm.faces:
        f.select = False

    # 选中
    for idx in face_indices:
        if 0 <= idx < len(bm.faces):
            bm.faces[idx].select = True

    bm.to_mesh(mesh)
    bm.free()


class CleanSceneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.clean_scene"
    bl_label = "清空场景"
    bl_description = "清除场景中的所有对象和集合，递归清理未使用的数据块并刷新场景，然后新建默认集合"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.clean_scene(context)
        return {'FINISHED'}

    def clean_scene(self, context):
        """清空全部场景的数据，而非仅当前场景"""
        # bpy.data.objects 是全局数据，包含所有场景的物体，故这里会清空全部场景
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        # bpy.data.collections 同样是全局数据，所有场景的集合都会被移除
        for coll in list(bpy.data.collections):
            bpy.data.collections.remove(coll)

        # 递归清理未使用的数据块
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        # 删除后把当前帧设为第一帧，解决导入模型时刚体散落的问题
        context.scene.frame_current = 1

        # 新建默认集合
        get_collection("Collection")
