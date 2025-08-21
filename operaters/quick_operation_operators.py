from ..utils import *
from ..mmd_utils import *


class MergeVerticesOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.merge_vertices"
    bl_label = "合并顶点"
    bl_description = "按距离合并顶点，合并间距0.00001，并重设法向。支持一次选择多个网格对象并分别处理。在物体模式，作用范围为选择的物体；在编辑模式，作用范围为选择的顶点"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.merge_vertices(context)
        return {'FINISHED'}

    def merge_vertices(self, context):
        scene = context.scene

        objs = bpy.context.selected_objects
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=f'Select at least one object!')
            return
        active_object = bpy.context.active_object
        if active_object is None:
            self.report(type={'ERROR'}, message=f'Activate the object!')
            return

        # 记录当前模式

        total_vertices = self.get_total_vertices(objs)
        print(f"total_vertices:{total_vertices}")

        if bpy.context.active_object and bpy.context.active_object.mode == "EDIT":
            bpy.ops.mesh.remove_doubles(threshold=1e-05)
        else:
            deselect_all_objects()
            for obj in objs:
                if obj.type != "MESH":
                    continue
                deselect_all_objects()
                show_object(obj)
                select_and_activate(obj)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(type="VERT")
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles(threshold=1e-05)
                bpy.ops.mesh.normals_tools(mode='RESET')
                bpy.ops.mesh.select_all(action='DESELECT')
                bpy.ops.object.mode_set(mode='OBJECT')

        total_vertices_after = self.get_total_vertices(objs)
        print(f"total_vertices_after:{total_vertices_after}")
        self.report(type={'INFO'}, message=f'移除了 {total_vertices - total_vertices_after} 个顶点')

    def get_total_vertices(self, objs):
        """强制刷新后计算总顶点数，仅考虑网格自身数据，不考虑修改器的影响"""

        mode = bpy.context.active_object.mode
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
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.rename()
        return {'FINISHED'}

    def rename(self):
        objs = bpy.context.selected_objects
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=f'Select at least one object!')
            return

        for obj in objs:
            # 跳过多材质
            material_count = len([m for m in obj.data.materials if m is not None])
            if material_count != 1:
                continue

            # 获取对象实际名称。名称.xxx 形式的，视为重名，暂不处理
            obj_name = obj.name
            match = PMX_NAME_PATTERN.match(obj_name)
            if match:
                obj_name = match.group('name')

            # 设置材质名称
            mat = obj.data.materials[0]
            if mat.name != obj_name:
                mat.name = obj_name
            if is_mmd_tools_enabled():
                mat.mmd_material.name_j = obj_name


class SetObjNameByMatNameOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.set_obj_name_by_mat_name"
    bl_label = "材质名称 → 网格名称"
    bl_description = "根据材质名称设置实际网格名称。支持一次选择多个网格对象并分别处理。"
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.rename()
        return {'FINISHED'}

    def rename(self):
        objs = bpy.context.selected_objects
        if len(objs) == 0:
            self.report(type={'ERROR'}, message=f'Select at least one object!')
            return

        for obj in objs:
            # 跳过多材质
            material_count = len([m for m in obj.data.materials if m is not None])
            if material_count != 1:
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


def hash_face(face_verts):
    """将面顶点位置生成哈希（不考虑顺序）"""
    rounded = tuple(sorted(round_vec(v) for v in face_verts))
    return hash(rounded)


def get_faces(obj):
    """获取对象的所有面的集合"""
    mesh = obj.data
    faces = set()
    if not mesh or not mesh.polygons:
        return faces

    for poly in mesh.polygons:
        face_verts = [mesh.vertices[i].co for i in poly.vertices]
        face_hash = hash_face(face_verts)
        faces.add(face_hash)

    return faces


class DetectOverlappingFacesOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.detect_overlapping_faces"
    bl_label = "检测网格面重合度"
    bl_description = "检测网格面之间的重合度"
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.detect_overlapping_faces()
        return {'FINISHED'}

    def check_props(self):
        active_object = bpy.context.active_object
        if not active_object:
            self.report(type={'ERROR'}, message=f'Select MMD model!')
            return False
        pmx_root = find_pmx_root_with_child(active_object)
        if not pmx_root:
            self.report(type={'ERROR'}, message=f'Select MMD model!')
            return False
        armature = find_pmx_armature(pmx_root)
        if not armature:
            self.report(type={'ERROR'}, message=f'Armature not found!')
            return False
        return True

    def detect_overlapping_faces(self):
        if self.check_props() is False:
            return

        active_object = bpy.context.active_object
        root = find_pmx_root_with_child(active_object)
        rig = find_pmx_armature(root)
        objs = find_pmx_objects(rig)

        faces_map = {}
        for obj in objs:
            faces = get_faces(obj)
            faces_map[obj] = faces

        msgs = []
        obj_list = list(faces_map.keys())
        for i in range(len(obj_list)):
            for j in range(i + 1, len(obj_list)):
                obj_a = obj_list[i]
                obj_b = obj_list[j]
                faces_a = faces_map[obj_a]
                faces_b = faces_map[obj_b]

                intersection = faces_a & faces_b
                if not intersection:
                    continue

                ratio_a = len(intersection) / len(faces_a)
                ratio_b = len(intersection) / len(faces_b)

                msg = f"{obj_a.name} 与 {obj_b.name} 重合面数: {len(intersection)} (占比 A: {ratio_a:.2%}, B: {ratio_b:.2%})"
                print(msg)
                msgs.append(msg)

        if msgs:
            combined_msg = "\n".join(msgs)
            self.report(type={'INFO'}, message=combined_msg)
            self.report(type={'INFO'}, message="检测完成，点击查看报告↑↑↑")
        else:
            self.report(type={'INFO'}, message="未发现网格面之间重合")


class CleanSceneOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.clean_scene"
    bl_label = "清空场景"
    bl_description = "清除场景中的所有对象和集合，递归清理未使用的数据块并刷新场景，然后新建默认集合"
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.clean_scene()
        return {'FINISHED'}

    def clean_scene(self):
        # 移除所有对象
        for obj in reversed(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        # 移除所有集合
        for coll in list(bpy.data.collections):
            bpy.data.collections.remove(coll)

        # 递归清理未使用的数据块
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        # 刷新场景  预防导入模型时刚体掉一地，但该情况出现的原因暂不明确，故通过更改当前帧来刷新场景的方式有待后续确认
        frame_current = bpy.context.scene.frame_current
        bpy.context.scene.frame_current = bpy.context.scene.frame_current + 1
        bpy.context.scene.frame_current = frame_current

        # 新建默认集合
        get_collection("Collection")
