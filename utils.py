import math
import os
import re
import stat
import time

import bpy
import addon_utils
from mathutils import Vector
import bpy_extras.anim_utils as anim_utils

from .constants import (
    ABC_NAME_PATTERN,
    CONVERT_NAME_TO_L_REGEXP,
    CONVERT_NAME_TO_R_REGEXP,
    INVALID_CHARS,
    MAX_RETRIES,
    PMX_EXPORT_SCALE,
    PMX_IMPORT_SCALE,
    TMP_COLLECTION_NAME,
    TXT_INFO_PATTERN,
)


def find_pmx_root():
    """寻找pmx对应空物体"""
    return next((obj for obj in bpy.context.scene.objects if obj.mmd_type == 'ROOT'), None)


def find_pmx_root_with_child(child):
    """根据child寻找pmx对应空物体"""
    if not child:
        return None

    parent = child
    while parent:
        if parent.mmd_type == 'ROOT':
            return parent
        parent = parent.parent

    return None


def find_pmx_armature(pmx_root):
    return next((child for child in pmx_root.children if child.type == 'ARMATURE'), None)


def find_pmx_objects(pmx_armature):
    return list((child for child in pmx_armature.children if child.type == 'MESH' and child.mmd_type == 'NONE'))


def find_abc_objects():
    """获取场景中的abc对象"""
    abc_objects = [obj for obj in bpy.context.scene.objects if ABC_NAME_PATTERN.match(obj.name)]
    return abc_objects


def find_rigid_body_parent(root):
    """寻找刚体对象"""
    return next(filter(lambda o: o.type == 'EMPTY' and o.mmd_type == 'RIGID_GRP_OBJ', root.children), None)


def find_joint_parent(root):
    return next(filter(lambda o: o.type == 'EMPTY' and o.mmd_type == 'JOINT_GRP_OBJ', root.children), None)


def sort_pmx_objects(objects):
    objects.sort(key=lambda obj: obj.name)


def sort_abc_objects(objects):
    objects.sort(key=lambda obj: int(ABC_NAME_PATTERN.match(obj.name).group(2)))


def select_and_activate(obj):
    """选中并激活物体"""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    except RuntimeError:  # RuntimeError: 错误: 物体 'xxx' 不在视图层 'ViewLayer'中, 所以无法选中!
        pass


def deselect_all_objects():
    """对场景中的选中对象和活动对象取消选择"""
    if bpy.context.active_object is None:
        bpy.ops.object.select_all(action='DESELECT')
        return
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None


def restore_selection(selected_objects, active_object):
    """ 恢复选中状态"""
    deselect_all_objects()
    for obj in selected_objects:
        try:  # 防止 StructRNA of type Object has been removed
            select_and_activate(obj)
        except ReferenceError:  # 物体已被删除，跳过
            continue
    if active_object:
        try:  # 防止 StructRNA of type Object has been removed
            # 可能会出现激活但没选中的情况
            bpy.context.view_layer.objects.active = active_object
        except ReferenceError:  # 物体已被删除，跳过
            pass


def record_visibility(obj):
    """记录物体的可见性"""
    return obj.hide_select, obj.hide_get(), obj.hide_viewport, obj.hide_render


def show_object(obj):
    """显示物体。在视图取消禁用选择，在视图中取消隐藏，在视图中取消禁用，在渲染中取消禁用"""
    set_visibility(obj, (False, False, False, False))


def hide_object(obj):
    """显示物体。在视图取消禁用选择，在视图中取消隐藏，在视图中取消禁用，在渲染中取消禁用"""
    set_visibility(obj, (True, True, True, True))


def set_visibility(obj, visibility):
    """设置Blender物体的可见性相关属性"""
    # 如果不在当前视图层，则跳过，如"在视图层中排除该集合"的情况下
    view_layer = bpy.context.view_layer
    # 成员资格测试（Python 会调用对象的 __eq__ 方法。）
    if obj.name not in view_layer.objects:
        return
    # 是否可选
    obj.hide_select = visibility[0]
    # 是否在视图中隐藏
    obj.hide_set(visibility[1])
    # 是否在视图中禁用
    obj.hide_viewport = visibility[2]
    # 是否在渲染中禁用
    obj.hide_render = visibility[3]


def view3d_context():
    """返回 bpy.context.temp_override 所需的 area/region。
    优先使用当前 area（UI 下行为不变）；后台运行时当前上下文没有 area/region，
    这里从 screen 中取 VIEW_3D 的 WINDOW 区域；找不到 3D 视图时为 None。

    areas   https://docs.blender.org/manual/en/latest/interface/window_system/areas.html
    regions https://docs.blender.org/manual/en/latest/interface/window_system/regions.html
    """
    area = bpy.context.area if bpy.context.area and bpy.context.area.type == 'VIEW_3D' else None
    if area is None and bpy.context.screen:
        area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
    # https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items
    region = next((r for r in area.regions if r.type == 'WINDOW'), None) if area else None
    return {"area": area, "region": region}


def center_view_camera():
    """相机视角下重新对准相机；非相机视角或后台运行时忽略"""
    if bpy.app.background:
        return
    view3d = view3d_context()
    area = view3d["area"]
    if area is None:
        return
    region_3d = getattr(area.spaces.active, "region_3d", None)
    # https://docs.blender.org/api/current/bpy.types.RegionView3D.html#bpy.types.RegionView3D.view_perspective
    if region_3d is None or region_3d.view_perspective != 'CAMERA':
        return
    with bpy.context.temp_override(**view3d):
        try:
            bpy.ops.view3d.view_center_camera()
        except RuntimeError:
            # 上下文不满足（如无活动视口）时忽略
            pass


def get_physical_bone(root):
    """获取受物理影响的骨骼"""
    rigidbody_parent = find_rigid_body_parent(root)
    if rigidbody_parent is None:
        return []
    rigid_bodies = rigidbody_parent.children
    # 受刚体物理影响的骨骼名称列表（blender名称）
    bl_names = []
    for rigidbody in rigid_bodies:
        # 存在有刚体但没有关联骨骼的情况
        if rigidbody.mmd_rigid.bone == '':
            continue
        # 0:骨骼 1:物理 2:物理+骨骼
        if rigidbody.mmd_rigid.type not in ('1', '2'):
            continue
        bl_names.append(rigidbody.mmd_rigid.bone)
    return bl_names


def walk_island(vert):
    ''' walk all un-tagged linked verts '''
    vert.tag = True
    yield (vert)
    linked_verts = [e.other_vert(vert) for e in vert.link_edges
                    if not e.other_vert(vert).tag]

    for v in linked_verts:
        if v.tag:
            continue
        yield from walk_island(v)


def get_islands(bm, verts=[]):
    """https://blender.stackexchange.com/questions/75332/how-to-find-the-number-of-loose-parts-with-blenders-python-api"""

    def tag(verts, switch):
        for v in verts:
            v.tag = switch

    tag(bm.verts, True)
    tag(verts, False)
    ret = {"islands": []}
    verts = set(verts)
    while verts:
        v = verts.pop()
        verts.add(v)
        island = set(walk_island(v))
        ret["islands"].append(list(island))
        tag(island, False)  # remove tag = True
        verts -= island
    return ret


def move_to_target_collection_recursive(obj, target_collection):
    """将指定对象及其子级（递归）移动到指定集合"""
    # 将对象从原始集合中移除
    if obj.users_collection:
        for collection in obj.users_collection:
            collection.objects.unlink(obj)
    # 将对象添加到目标集合中
    target_collection.objects.link(obj)
    # 递归处理子对象
    for child in obj.children:
        move_to_target_collection_recursive(child, target_collection)


def find_layer_collection_by_name(layer_collection, collection_name):
    """递归查询集合"""
    # 如果当前集合名称匹配
    if layer_collection.name == collection_name:
        return layer_collection

    # 遍历子集合，递归查找
    for child in layer_collection.children:
        result = find_layer_collection_by_name(child, collection_name)
        if result:
            return result

    # 如果没有找到匹配的集合，返回 None
    return None


def get_collection(collection_name):
    """获取指定名称集合，没有则新建，然后激活"""
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
    else:
        collection = bpy.data.collections.new(collection_name)

    # 新建和原有集合都可能未被link
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)

    layer_collection = find_layer_collection_by_name(bpy.context.view_layer.layer_collection, collection_name)
    bpy.context.view_layer.active_layer_collection = layer_collection
    return collection


def recursive_search(directory, suffix, threshold, search_strategy, conflict_strategy, stats=None):
    """寻找指定路径下各个子目录中，时间最新且未进行处理的那个模型 todo 之后看看能不能更通用些"""
    file_list = []
    pmx_count = 0
    for root, dirs, files in os.walk(directory):
        flag = False

        for file in files:
            if file.lower().endswith(('.pmx', '.pmd')):
                flag = True
                pmx_count += 1
        if flag:
            curr_list = []  # 当前目录下符合条件的文件
            model_files = [f for f in files
                           if f.lower().endswith(('.pmx', '.pmd'))
                           and os.path.getsize(os.path.join(root, f)) > threshold * 1024]  # 排除掉已被排除的文件的影响
            # 当前目录的模型全部小于阈值时直接跳过
            if not model_files:
                continue

            # 如果满足条件的model_files有多个，取最新的还是取全部
            if search_strategy == 'LATEST':
                most_recent_file = max(model_files, key=lambda x: os.path.getmtime(os.path.join(root, x)))
                curr_list.append(most_recent_file)
            elif search_strategy == 'ALL':
                for model_file in model_files:
                    curr_list.append(model_file)
            # 如果含有相同的名称后缀，是排除（不处理）还是放行（覆盖）
            files_to_remove = []
            for file in reversed(curr_list):
                if os.path.splitext(file)[0].endswith(suffix):
                    if conflict_strategy == 'SKIP':
                        files_to_remove.append(file)
                    elif conflict_strategy == 'OVERWRITE':
                        pass

                    # 针对检索模式为“全部”的情况下，原文件和目标文件同时存在时的处理
                    # 无论是SKIP还是OVERWRITE，如果选择了ALL，都应该排除source_file的影响
                    # 如果选择SKIP时，不排除source_file的影响的话，即使跳过了名称冲突的文件，也会因为source_file的存在而被复写
                    # 如果选择OVERWRITE时，应该对冲突的文件进行复写而不是source_file
                    if search_strategy != 'ALL':
                        continue
                    if suffix == '':
                        continue
                    source_file = file.replace(suffix, '')
                    if source_file in curr_list:
                        files_to_remove.append(source_file)
            for file in reversed(files_to_remove):
                curr_list.remove(file)

            for file in curr_list:
                file_list.append(os.path.join(root, file))
    msg = translate("实际待处理数量：{}。文件总数：{}，跳过数量：{}").format(
        len(file_list), pmx_count, pmx_count - len(file_list)
    )
    print(msg)
    if stats is not None:
        stats["total"] = pmx_count
        stats["skipped"] = pmx_count - len(file_list)
    return file_list


def recursive_search_img(directory, suffix, threshold, search_strategy, conflict_strategy, ext, stats=None):
    """寻找指定路径下各个子目录中，时间最新且未进行处理的那个模型"""
    file_list = []
    pmx_count = 0
    for root, dirs, files in os.walk(directory):
        flag = False
        for file in files:
            if file.lower().endswith(('.pmx', '.pmd')):
                flag = True
                pmx_count += 1
        if flag:
            model_files = [f for f in files
                           if f.lower().endswith(('.pmx', '.pmd'))
                           and os.path.getsize(os.path.join(root, f)) > threshold * 1024]  # 排除掉已被排除的文件的影响
            # 当前目录的模型全部小于阈值时直接跳过
            if not model_files:
                continue

            # 如果满足条件的model_files有多个，取最新的还是取全部
            if search_strategy == 'LATEST':
                most_recent_file = max(model_files, key=lambda x: os.path.getmtime(os.path.join(root, x)))
                if is_render(root, most_recent_file, suffix, ext, conflict_strategy):
                    file_list.append(os.path.join(root, most_recent_file))
            elif search_strategy == 'ALL':
                for model_file in model_files:
                    if is_render(root, model_file, suffix, ext, conflict_strategy):
                        file_list.append(os.path.join(root, model_file))
    msg = translate("实际待处理数量：{}。文件总数：{}，跳过数量：{}").format(
        len(file_list), pmx_count, pmx_count - len(file_list))
    print(msg)
    if stats is not None:
        stats["total"] = pmx_count
        stats["skipped"] = pmx_count - len(file_list)
    return file_list


def is_render(root, file, suffix, ext, conflict_strategy):
    # 构建图像名称
    image_name = os.path.splitext(file)[0] + suffix + ext
    # 构建图像路径
    image_path = os.path.join(root, image_name)
    # 如果图像在 pmx 目录中存在，则跳过，否则添加 pmx 文件路径到列表
    if not os.path.exists(image_path):
        return True

    if conflict_strategy == 'SKIP':
        return False
    elif conflict_strategy == 'OVERWRITE':
        return True


def import_pmx(filepath: str) -> bool:
    """导入PMX文件，失败时自动重试"""
    params = {
        'filepath': filepath,
        'scale': PMX_IMPORT_SCALE,
        # 移除未使用的顶点和重复的或无效的面
        'clean_model': True,
        # 其余参数默认。即使ImportHelper存在用户使用过的缓存，参数默认值仍然为其定义时默认值
    }

    for attempt in range(MAX_RETRIES):
        try:
            bpy.ops.mmd_tools.import_model('EXEC_DEFAULT', **params)
            if attempt == 0:
                print(translate("导入成功，文件：{}").format(filepath))
            else:
                print(translate("导入成功，文件：{}，重试次数：{}").format(filepath, attempt))
            return True
        except Exception as e:
            print(translate("导入失败，即将重试，文件：{}，错误：{}").format(filepath, e))
            clean_scene()
            time.sleep(1)

    # 所有重试均失败。或是MMD Tools版本问题，或是pmx模型文件问题，直接抛出异常。
    raise Exception(translate("持续导入异常，请检查。文件路径：{}").format(filepath))


def force_writable(path):
    """清除只读属性，失败时打印提示"""
    try:
        # 只清除只读属性：Windows 上等同于 S_IREAD|S_IEXEC，
        # 但在 POSIX 上不会把权限整体改成 0o700
        os.chmod(path, stat.S_IWRITE)
        return True
    except OSError as e:
        print(translate("修改文件权限失败，路径：{}，错误：{}").format(path, e))
        return False


def export_pmx(filepath: str) -> bool:
    """导出PMX文件，失败时自动重试"""
    params = {
        'filepath': filepath,
        'scale': PMX_EXPORT_SCALE,
    }

    for attempt in range(MAX_RETRIES):
        try:
            bpy.ops.mmd_tools.export_pmx('EXEC_DEFAULT', **params)
            if attempt == 0:
                print(translate("导出成功，文件：{}").format(filepath))
            else:
                print(translate("导出成功，文件：{}，重试次数：{}").format(filepath, attempt))
            return True
        except Exception as e:
            if os.path.exists(filepath) and not os.access(filepath, os.W_OK):
                force_writable(filepath)

            print(translate("导出失败，即将重试，文件：{}，错误：{}").format(filepath, e))
            time.sleep(1)

    # 全部重试失败后抛出异常
    raise Exception(translate("持续导出异常，请检查。文件路径：{}").format(filepath))


def clean_scene():
    # 删除由导入pmx生成的文本（防止找不到脚本）
    text_to_delete_list = []
    for text in bpy.data.texts:
        text_name = text.name
        match = TXT_INFO_PATTERN.match(text_name)
        if match is not None:
            base_text_name = match.group(1)
            if match.group(3) is not None:
                base_text_name = base_text_name + match.group(3)
            base_text = bpy.data.texts.get(base_text_name, None)
            if base_text is not None:
                text_to_delete_list.append(base_text)
                text_to_delete_list.append(text)
    for text_to_delete in text_to_delete_list:
        bpy.data.texts.remove(text_to_delete, do_unlink=True)

    # 删除临时集合内所有物体（pmx文件所在集合）
    if TMP_COLLECTION_NAME in bpy.data.collections:
        collection = bpy.data.collections[TMP_COLLECTION_NAME]
        # 遍历集合中的所有对象
        for obj in list(collection.objects):
            # 从集合中移除对象
            collection.objects.unlink(obj)
            # 从场景中删除对象
            bpy.data.objects.remove(obj, do_unlink=True)
        # 删除临时集合
        bpy.data.collections.remove(collection)

    # 清理递归未使用数据块
    bpy.ops.outliner.orphans_purge(do_recursive=True)


# 需要跟踪孤儿数据的数据块类型，网格需先于形态键清理
TRACKED_DATA_BLOCK_TYPES = ("meshes", "shape_keys")


def snapshot_data_blocks():
    """记录当前已存在的数据块，供后续只清理本次新增的无用户数据"""
    data_pointers = {}

    for name in TRACKED_DATA_BLOCK_TYPES:
        if not hasattr(bpy.data, name):
            continue

        data_blocks = getattr(bpy.data, name)
        pointers = {block.as_pointer() for block in data_blocks}
        data_pointers[name] = pointers

    return data_pointers


def purge_new_orphan_data(snapshot, extra_pointers=None):
    """只删除快照之后新增的数据块，避免误删用户已有数据

    extra_pointers 用于传入执行期间主动删除对象后遗留的数据块指针，
    这些数据块虽然存在于快照中，但也需要一并清理。
    """
    if not snapshot:
        return

    extra_pointers = set(extra_pointers or ())
    shape_key_owners = None

    for name, before in snapshot.items():
        blocks = getattr(bpy.data, name)
        for block in list(blocks):
            pointer = block.as_pointer()
            if pointer in before and pointer not in extra_pointers:
                continue
            # 形态键集合没有 remove()（4.5 等版本），且失去网格后 users 仍可能为 1，
            # 因此按“是否仍被网格/曲线/晶格引用”判断，用 batch_remove 清理
            if name == "shape_keys":
                if shape_key_owners is None:
                    shape_key_owners = set()
                    for owner_type in ("meshes", "curves", "lattices"):
                        if not hasattr(bpy.data, owner_type):
                            continue
                        for owner in getattr(bpy.data, owner_type):
                            shape_keys = getattr(owner, "shape_keys", None)
                            if shape_keys is not None:
                                shape_key_owners.add(shape_keys.as_pointer())
                if pointer in shape_key_owners:
                    continue
                try:
                    bpy.data.batch_remove([block])
                except Exception:
                    pass
                continue
            if block.users != 0:
                continue
            if getattr(block, "use_fake_user", False):
                continue
            try:
                blocks.remove(block)
            except Exception:
                pass


def find_ancestor(obj):
    ancestor = obj
    while ancestor.parent is not None:
        ancestor = ancestor.parent
    return ancestor


def find_armature(obj):
    """
    递归查找 obj 的子对象，直到找到骨架（ARMATURE）对象。
    返回第一个找到的骨架对象，如果没有找到则返回 None。
    """
    if obj is None:
        return None

    if obj.type == 'ARMATURE' and ".dummy_armature" not in obj.name:
        return obj

    # 模型根的直接子级通常就是骨架，先查一层，避免递归遍历大量刚体/关节子树
    for child in obj.children:
        if child.type == 'ARMATURE' and ".dummy_armature" not in child.name:
            return child

    for child in obj.children:
        # MMD Tools 用 mmd_type 标记刚体/关节及其分组空物体；
        # 同时兼容没有 mmd_tools 或标记缺失的场景，直接看物理数据。
        if getattr(child, "mmd_type", "") in ("RIGID_BODY", "JOINT",
                                              "RIGID_GRP_OBJ", "JOINT_GRP_OBJ"):
            continue
        if child.rigid_body is not None or child.rigid_body_constraint is not None:
            continue
        result = find_armature(child)
        if result:
            return result

    return None


def find_children(obj, obj_type=None):
    children = []
    if not obj_type:
        children.append(obj)
    else:
        if obj.type in obj_type:
            children.append(obj)

    for child in obj.children:
        children.extend(find_children(child, obj_type))
    return children


def is_mmd_tools_enabled():
    """
    校验mmd_tools是否开启

    直接看 Object.mmd_type 是否注册即可：它由 mmd_tools 注册，
    注册了就说明插件可用；反注册了（含 addon_utils.disable() 半关闭）就不可用。
    这样不用遍历 addon_utils.modules()，面板每次重绘都不会有额外开销。
    """
    return hasattr(bpy.types.Object, "mmd_type")


def is_mmd_rigid_body(obj):
    """判断对象是否为 mmd_tools 的刚体"""
    return getattr(obj, "mmd_type", None) == 'Rigid body'


def check_batch_props(operator, batch):
    suffix = batch.suffix
    directory = batch.directory

    if not is_mmd_tools_enabled():
        operator.report(type={'ERROR'}, message=translate("未启用MMD Tools插件！"))
        return False

    # 获取目录的全限定路径 这里用blender提供的方法获取，而不是os.path.abspath。没有必要将相对路径转为绝对路径，因为哪种路径是由用户决定的
    # https://blender.stackexchange.com/questions/217574/how-do-i-display-the-absolute-file-or-directory-path-in-the-ui
    # 如果用户随意填写，可能会解析成当前blender文件的同级路径，但不影响什么
    abs_path = bpy.path.abspath(directory)
    if not os.path.exists(abs_path):
        operator.report(type={'ERROR'}, message=translate("模型目录不存在！"))
        return False
    if not os.path.isdir(abs_path):
        operator.report(type={'ERROR'}, message=translate("请确保模型目录为文件夹！"))
        return False
    # 获取目录所在盘符的根路径
    drive, tail = os.path.splitdrive(abs_path)
    drive_root = os.path.join(drive, os.sep)
    # 校验目录是否是盘符根目录
    if abs_path == drive_root:
        operator.report(type={'ERROR'}, message=translate("模型目录为盘符根目录，请更换为其它目录！"))
        return False

    # 仅简单校验下后缀是否合法
    if any(char in suffix for char in INVALID_CHARS):
        operator.report(type={'ERROR'}, message=translate("名称后缀不合法！"))
        return False
    return True


def case_insensitive_replace(pattern, replacement, string):
    """忽略大小写替换"""
    return re.sub(pattern, replacement, string, flags=re.IGNORECASE)


## 日本語で左右を命名されている名前をblender方式のL(R)に変更する
def convertNameToLR(name, use_underscore=False):
    m = CONVERT_NAME_TO_L_REGEXP.match(name)
    delimiter = '_' if use_underscore else '.'
    if m:
        name = m.group(1) + m.group(2) + delimiter + 'L'
    m = CONVERT_NAME_TO_R_REGEXP.match(name)
    if m:
        name = m.group(1) + m.group(2) + delimiter + 'R'
    return name


def get_target_bone(armature, edit_bone):
    # a connected child bone is preferred
    for child in edit_bone.children:
        if (
                child.use_connect
                or bool(child.get('mmd_bone_use_connect'))
                or (
                all(armature.pose.bones[child.name].lock_location)
                and math.isclose(0.0, (child.head - edit_bone.tail).length))
        ):
            return child
    return None


def create_frame(mmd_root, name):
    frames = mmd_root.display_item_frames
    frame, index = ItemOp.add_after(frames, max(1, mmd_root.active_display_item_frame))
    frame.name = name
    mmd_root.active_display_item_frame = index
    return frame


class ItemOp:
    @staticmethod
    def add_after(items, index):
        index_end = len(items)
        index = max(0, min(index_end, index + 1))
        items.add()
        items.move(index_end, index)
        return items[index], index


def do_add_item(frame, item_type, item_name, morph_type=None, order=None):
    items = frame.data
    item, index = ItemOp.add_after(items, frame.active_item)
    item.type = item_type
    item.name = item_name
    if morph_type:
        item.morph_type = morph_type
    frame.active_item = index
    if order is not None:  # order为0时应判断为True
        if order < 0:
            order = len(items) - 1
        items.move(index, order)
        frame.active_item = order
    return item


def add_item(armature, assignee, base, offset):
    pmx_root = find_pmx_root_with_child(armature)
    mmd_root = pmx_root.mmd_root
    found_frame, found_item = find_bone_item(pmx_root, base)

    if found_frame is not None and found_item is not None:
        frames = mmd_root.display_item_frames
        do_add_item(frames[found_frame], 'BONE', assignee, order=found_item + offset)
        return True
    return False


def add_item_after(armature, assignee, base):
    return add_item(armature, assignee, base, offset=1)


def add_item_before(armature, assignee, base):
    return add_item(armature, assignee, base, offset=0)


def find_bone_item(pmx_root, bone_name):
    mmd_root = pmx_root.mmd_root
    for i, frame in enumerate(mmd_root.display_item_frames):
        # 不含 root 和 表情
        if i < 2:
            continue
        for j, item in enumerate(frame.data):
            if bone_name == item.name:
                return i, j
    return None, None


class FnBone(object):
    AUTO_LOCAL_AXIS_ARMS = ('左肩', '左腕', '左ひじ', '左手首', '右腕', '右肩', '右ひじ', '右手首')
    AUTO_LOCAL_AXIS_FINGERS = ('親指', '人指', '中指', '薬指', '小指')
    AUTO_LOCAL_AXIS_SEMI_STANDARD_ARMS = (
        '左腕捩', '左手捩', '左肩P', '左ダミー', '右腕捩', '右手捩', '右肩P', '右ダミー')

    @classmethod
    def update_auto_bone_roll(cls, edit_bone):
        # make a triangle face (p1,p2,p3)
        p1 = edit_bone.head.copy()
        p2 = edit_bone.tail.copy()
        p3 = p2.copy()
        # translate p3 in xz plane
        # the normal vector of the face tracks -Y direction
        xz = Vector((p2.x - p1.x, p2.z - p1.z))
        xz.normalize()
        theta = math.atan2(xz.y, xz.x)
        norm = edit_bone.vector.length
        p3.z += norm * math.cos(theta)
        p3.x -= norm * math.sin(theta)
        # calculate the normal vector of the face
        y = (p2 - p1).normalized()
        z_tmp = (p3 - p1).normalized()
        x = y.cross(z_tmp)  # normal vector
        # z = x.cross(y)
        cls.update_bone_roll(edit_bone, y.xzy, x.xzy)

    @classmethod
    def update_bone_roll(cls, edit_bone, mmd_local_axis_x, mmd_local_axis_z):
        axes = cls.get_axes(mmd_local_axis_x, mmd_local_axis_z)
        idx, val = max([(i, edit_bone.vector.dot(v)) for i, v in enumerate(axes)], key=lambda x: abs(x[1]))
        edit_bone.align_roll(axes[(idx - 1) % 3 if val < 0 else (idx + 1) % 3])

    @staticmethod
    def get_axes(mmd_local_axis_x, mmd_local_axis_z):
        x_axis = Vector(mmd_local_axis_x).normalized().xzy
        z_axis = Vector(mmd_local_axis_z).normalized().xzy
        y_axis = z_axis.cross(x_axis).normalized()
        z_axis = x_axis.cross(y_axis).normalized()  # correction
        return (x_axis, y_axis, z_axis)


matmul = (lambda a, b: a * b) if bpy.app.version < (2, 80, 0) else (lambda a, b: a.__matmul__(b))


def to_pmx_axis(armature, scale, axis, bone_name):
    """todo 调研代码逻辑。不是很懂"""
    world_mat = armature.matrix_world
    pmx_matrix = world_mat * scale
    pmx_matrix_rot = pmx_matrix.to_3x3()
    pose_bone = armature.pose.bones.get(bone_name)
    m = matmul(pose_bone.matrix, pose_bone.bone.matrix_local.inverted()).to_3x3()
    return matmul(matmul(pmx_matrix_rot, m), Vector(axis).xzy).normalized()


def create_tmp_obj(armature, collection):
    # 新建Mesh并删除所有顶点
    bpy.ops.object.mode_set(mode='OBJECT')
    deselect_all_objects()
    bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=True)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='VERT')
    bpy.ops.object.mode_set(mode='OBJECT')
    tmp_obj = bpy.context.active_object
    tmp_obj.name = "tmp_plane"
    # 设置parent为armature
    tmp_obj.parent = armature
    move_to_target_collection_recursive(tmp_obj, collection)
    return tmp_obj


def copy_obj(obj, name=None, collection=None):
    """复制物体（含独立网格数据）；可选设置名称、移动到目标集合"""
    new_mesh = obj.data.copy()
    new_obj = obj.copy()
    new_obj.data = new_mesh
    col = obj.users_collection[0]
    col.objects.link(new_obj)
    if name:
        new_obj.name = name
    if collection:
        move_to_target_collection_recursive(new_obj, collection)
    return new_obj


def int2base(x, base, width=0):
    """
    Method to convert an int to a base
    Source: http://stackoverflow.com/questions/2267362
    """
    import string
    digs = string.digits + string.ascii_uppercase
    assert (2 <= base <= len(digs))
    digits, negative = '', False
    if x <= 0:
        if x == 0:
            return '0' * max(1, width)
        x, negative, width = -x, True, width - 1
    while x:
        digits = digs[x % base] + digits
        x //= base
    digits = '0' * (width - len(digits)) + digits
    if negative:
        digits = '-' + digits
    return digits


def get_addon_version(name):
    for addon in addon_utils.modules():
        if addon.bl_info.get('name') == name:
            return addon.bl_info.get('version', (-1, -1, -1))
    return -1, -1, -1


def srgb_to_linearrgb(c):
    if c < 0:
        return 0
    elif c < 0.04045:
        return c / 12.92
    else:
        return ((c + 0.055) / 1.055) ** 2.4


def hex_to_rgb(hex_string, alpha=None):
    if hex_string.startswith('#'):
        hex_string = hex_string[1:]
    h = int(hex_string, 16)
    r, g, b = (h >> 16) & 0xff, (h >> 8) & 0xff, h & 0xff
    color = [srgb_to_linearrgb(c / 255.0) for c in (r, g, b)]
    return tuple(color + [alpha]) if alpha is not None else tuple(color)


def try_int(s):
    """将可以转化为数字的转化为数字,不可以转化的保留原始类型"""
    return int(s) if s.isdigit() else s


def alphanum_key(s):
    """ 将字符串转换成由字符串和数字块组成的列表 "z23a" -> ["z", 23, "a"]"""
    return [try_int(c) for c in re.split('([0-9]+)', s)]


def get_mesh_objs(ancestor):
    """递归获取ancestor自身及其所有子对象中的mesh对象"""
    mesh_objs = []

    def recursive_search(obj):
        if is_mmd_tools_enabled():
            if obj.mmd_type == 'RIGID_GRP_OBJ':
                return
            if obj.mmd_type == 'JOINT_GRP_OBJ':
                return

        if obj.type == 'MESH':
            mesh_objs.append(obj)
        for child in obj.children:
            # 递归检查子对象
            recursive_search(child)

    # 从ancestor开始递归
    recursive_search(ancestor)
    return mesh_objs


def is_not_dummy_bone(name):
    return not name.startswith("_dummy_") and not name.startswith("_shadow_")


def safe_set(obj, attr, value):
    """安全设置属性，如果不存在就跳过"""
    try:
        setattr(obj, attr, value)
    except Exception as e:
        print(f"{e}")


def get_mmd_tools_version():
    v = get_addon_version("mmd_tools")
    if v > (-1, -1, -1):
        return v
    return get_addon_version("MMD Tools")


def select_pose_bone(pb, status):
    """
    选中/取消选中姿态模式下骨骼

    Pose bones now have a select property that stores their selection state.
    (bpy.data.objects["Armature"].pose.bones[0].select)
    Selection is synced with edit bones when going in and out of Edit Mode.
    https://developer.blender.org/docs/release_notes/5.0/python_api/#animation-rigging

    """
    blender_version = bpy.app.version

    if blender_version < (5, 0, 0):
        pb.bone.select = status
    else:
        pb.select = status


def is_pose_bone_selected(pb):
    """
    获取姿态模式下骨骼的选中状态

    Pose bones now have a select property that stores their selection state.
    (bpy.data.objects["Armature"].pose.bones[0].select)
    Selection is synced with edit bones when going in and out of Edit Mode.
    https://developer.blender.org/docs/release_notes/5.0/python_api/#animation-rigging

    """
    blender_version = bpy.app.version
    if blender_version < (5, 0, 0):
        return pb.bone.select
    else:
        return pb.select


def is_pose_bone_hidden(pb):
    """
    获取姿态模式下骨骼的隐藏状态

    Blender 5.0 起 PoseBone 有独立的 hide 属性，与 Bone.hide 不同步，
    姿态模式下骨骼的隐藏状态应读取 PoseBone.hide。

    """
    blender_version = bpy.app.version
    if blender_version < (5, 0, 0):
        return pb.bone.hide
    else:
        return pb.hide


def get_action_fcurves(obj):
    """
    获取Action下的fcurves

    自Blender 4.4起，Action下新增Slot。
    原先一个自行车有不同部位，如链条，车，车轮，每个部位都有自己的动作，不好管理这些动作。
    现在可以创建一个共用的自行车运动Action，使用Slot来存储链条，车，车轮的动作，可以更好的管理这些动作

    https://developer.blender.org/docs/release_notes/4.4/animation_rigging/
    https://developer.blender.org/docs/release_notes/5.0/python_api/#animation-rigging
    """
    animation_data = obj.animation_data
    if animation_data is None:
        return None

    action = animation_data.action
    if action is None:
        return None

    blender_version = bpy.app.version
    if blender_version < (5, 0, 0):
        return action.fcurves
    else:
        action_slot = animation_data.action_slot
        if action_slot is None:
            return None
        channelbag = anim_utils.action_get_channelbag_for_slot(action, animation_data.action_slot)
        return channelbag.fcurves


# foreach_get / foreach_set 在个别版本上不支持对应属性，
# 这些异常都表示"批量读写不可用"，统一退回逐帧读写。
_FOREACH_ERRORS = (AttributeError, TypeError, ValueError, RuntimeError, NotImplementedError)


def get_fcurve_frames(fcurve):
    """
    读取一条 F-Curve 上所有关键帧的帧号（float），一次 RNA 调用批量取回。

    用 foreach_get 取回全部 co（帧号、值成对排列），比逐关键帧访问 co.x 快得多；
    不支持批量读取时退回逐帧读取。
    """
    keyframe_points = fcurve.keyframe_points
    count = len(keyframe_points)

    if count == 0:
        return []

    try:
        co = [0.0] * (count * 2)
        keyframe_points.foreach_get("co", co)
        return co[0::2]
    except _FOREACH_ERRORS:
        return [kp.co[0] for kp in keyframe_points]


def translate(key: str) -> str:
    """翻译快捷方法"""
    return bpy.app.translations.pgettext_iface(key)


def unlink(collection):
    # 内层取消关联
    for parent_collection in bpy.data.collections:
        if collection.name in parent_collection.children.keys():
            parent_collection.children.unlink(collection)
    # 外层取消关联
    if collection.name in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.unlink(collection)
