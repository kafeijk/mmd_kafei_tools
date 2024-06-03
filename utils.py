import os
import time
from enum import Enum

import bpy
import re

ABC_NAME_PATTERN = re.compile(r'xform_(\d+)_material_(\d+)')
PMX_NAME_PATTERN = re.compile(r'(?P<prefix>[0-9A-Z]{3}_)(?P<name>.*?)(?P<suffix>\.\d{3})?$')
# 最大重试次数
MAX_RETRIES = 5
# 导入pmx生成的txt文件pattern
TXT_INFO_PATTERN = re.compile(r'(.*)(_e(\.\d{3})?)$')
# 临时集合名称
TMP_COLLECTION_NAME = "KAFEI临时集合"
# 默认精度
PRECISION = 0.0001
# 文件类型与扩展名的map，value相同可能会造成一些问题但几率太低这里不考虑
IMG_TYPE_EXT_MAP = {
    "BMP": ".bmp",
    "IRIS": ".rgb",
    "PNG": ".png",
    "JPEG": ".jpg",
    "JPEG2000": ".jp2",
    "TARGA": ".tga",
    "TARGA_RAW": ".tga",
    "CINEON": ".cin",
    "DPX": ".dpx",
    "OPEN_EXR_MULTILAYER": ".exr",
    "OPEN_EXR": ".exr",
    "HDR": ".hdr",
    "TIFF": ".tif",
    "WEBP": ".webp"
}

PMX_MIXAMO_BONES = ['全ての親', 'センター',
                    '左足ＩＫ', '左つま先ＩＫ', '右足ＩＫ', '右つま先ＩＫ',
                    '上半身', '上半身3', '上半身2', '首', '頭', '左目', '右目',
                    '左肩', '左腕', '左腕捩', '左ひじ', '左手捩', '左手首',
                    '右肩', '右腕', '右腕捩', '右ひじ', '右手捩', '右手首',
                    '左親指０', '左親指１', '左親指２', '左人指１', '左人指２', '左人指３', '左中指１', '左中指２', '左中指３',
                    '左薬指１', '左薬指２', '左薬指３', '左小指１', '左小指２', '左小指３',
                    '右親指０', '右親指１', '右親指２', '右人指１', '右人指２', '右人指３', '右中指１', '右中指２', '右中指３',
                    '右薬指１', '右薬指２', '右薬指３', '右小指１', '右小指２', '右小指３',
                    '下半身',
                    # 足骨 -> 足D骨
                    '左足D', '左ひざD', '左足首D', '左足先EX', '右足D', '右ひざD', '右足首D', '右足先EX']
# 文件名非法字符
INVALID_CHARS = '<>:"/\\|?*'


def find_pmx_root():
    """寻找pmx对应空物体"""
    return next((obj for obj in bpy.context.scene.objects if obj.mmd_type == 'ROOT'), None)


def find_pmx_root_with_child(child):
    """根据child寻找pmx对应空物体"""
    if child is None:
        return None
    while child.parent:
        child = child.parent
    if child.mmd_type != 'ROOT':
        return None
    return child


def find_pmx_armature(pmx_root):
    return next((child for child in pmx_root.children if child.type == 'ARMATURE'), None)


def find_pmx_objects(pmx_armature):
    return list((child for child in pmx_armature.children if child.type == 'MESH'))


def find_abc_objects():
    """获取场景中的abc对象"""
    abc_objects = [obj for obj in bpy.context.scene.objects if ABC_NAME_PATTERN.match(obj.name)]
    return abc_objects


def sort_pmx_objects(objects):
    objects.sort(key=lambda obj: obj.name)


def sort_abc_objects(objects):
    objects.sort(key=lambda obj: int(ABC_NAME_PATTERN.match(obj.name).group(2)))


def select_and_activate(obj):
    """选中并激活物体"""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def deselect_all_objects():
    """对场景中的选中对象和活动对象取消选择"""
    if bpy.context.active_object is None:
        return
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None


def show_object(obj):
    """显示物体。在视图取消禁用选择，在视图中取消隐藏，在视图中取消禁用，在渲染中取消禁用"""
    set_visibility(obj, False, False, False, False)


def hide_object(obj):
    """显示物体。在视图取消禁用选择，在视图中取消隐藏，在视图中取消禁用，在渲染中取消禁用"""
    set_visibility(obj, True, True, True, True)


def set_visibility(obj, hide_select_flag, hide_set_flag, hide_viewport_flag, hide_render_flag):
    """设置Blender物体的可见性相关属性"""
    # 如果不在当前视图层，则跳过，如"在视图层中排除该集合"的情况下
    view_layer = bpy.context.view_layer
    # 成员资格测试（Python 会调用对象的 __eq__ 方法。）
    if obj.name not in view_layer.objects:
        return
    # 是否可选
    obj.hide_select = hide_select_flag
    # 是否在视图中隐藏
    obj.hide_set(hide_set_flag)
    # 是否在视图中禁用
    obj.hide_viewport = hide_viewport_flag
    # 是否在渲染中禁用
    obj.hide_render = hide_render_flag


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


def get_collection(collection_name):
    """获取指定名称集合，没有则新建，然后激活"""
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
    else:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[collection_name]
    return collection


def recursive_search(directory, suffix, threshold):
    """寻找指定路径下各个子目录中，时间最新且未进行处理的那个模型 todo 之后看看能不能更通用些"""
    file_list = []
    pmx_count = 0
    skip_count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.pmx'):
                pmx_count += 1
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)  # 获取文件大小（字节）
                if file_size < threshold * 1024:
                    skip_count += 1
                    continue
                other_files = [f for f in os.listdir(root) if f.endswith('.pmx')]
                if len(other_files) > 1:
                    most_recent_file = max(other_files, key=lambda x: os.path.getmtime(os.path.join(root, x)))
                    if most_recent_file != file:
                        skip_count += 1
                        continue
                    elif suffix in os.path.splitext(most_recent_file)[0]:
                        print(f"{os.path.splitext(most_recent_file)[0]}已经预处理完毕")
                        skip_count += 1
                        continue
                file_list.append(file_path)
    print(f"实际待处理数量：{len(file_list)}。文件总数：{pmx_count}，跳过数量：{skip_count}")
    return file_list


def recursive_search_by_img(directory, suffix, ext, threshold):
    """寻找指定路径下各个子目录中，时间最新且未进行处理的那个模型"""
    file_list = []
    pmx_count = 0
    skip_count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.pmx'):
                pmx_count += 1
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)  # 获取文件大小（字节）
                if file_size < threshold * 1024:
                    skip_count += 1
                    continue
                # 获取 file 的名称（去掉扩展名）
                file_name = os.path.splitext(file)[0]
                # 构建图像名称
                image_name = file_name + suffix + ext
                # 构建图像路径
                image_path = os.path.join(root, image_name)
                # 如果图像在 pmx 目录中存在，则跳过，否则添加 pmx 文件路径到列表
                if os.path.exists(image_path):
                    skip_count += 1
                    continue
                file_list.append(os.path.join(root, file))
    print(f"实际待处理数量：{len(file_list)}。文件总数：{pmx_count}，跳过数量：{skip_count}")
    return file_list


def import_pmx(filepath):
    """导入pmx文件"""
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            bpy.ops.mmd_tools.import_model('EXEC_DEFAULT',
                                           filepath=filepath,
                                           scale=0.08,
                                           clean_model=True,
                                           remove_doubles=False,
                                           fix_IK_links=False,
                                           apply_bone_fixed_axis=False,
                                           rename_bones=True,
                                           use_underscore=False,
                                           dictionary="DISABLED",
                                           use_mipmap=True,
                                           sph_blend_factor=1,
                                           spa_blend_factor=1
                                           )
            print(f"导入成功，文件:{filepath}，attempt:{attempt + 1}")
            return True
        except Exception as e:
            print(f"导入失败，即将重试，文件:{filepath}，{e}")
            attempt += 1
            clean_scene()
            time.sleep(1)  # 等待一秒后重试
    else:
        raise Exception(f'持续导入异常，请检查。文件路径:{filepath}')


def export_pmx(filepath):
    """导出pmx文件"""
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            bpy.ops.mmd_tools.export_pmx('EXEC_DEFAULT',
                                         filepath=filepath,
                                         scale=12.5,
                                         copy_textures=False,
                                         sort_materials=False,
                                         disable_specular=False,
                                         visible_meshes_only=False,
                                         overwrite_bone_morphs_from_pose_library=False,
                                         translate_in_presets=False,
                                         sort_vertices='NONE',
                                         log_level='DEBUG',
                                         save_log=False
                                         )
            print(f"导出成功，文件:{filepath}，attempt:{attempt + 1}")
            return True
        except Exception as e:
            print(f"导出失败，即将重试，文件:{filepath}，{e}")
            attempt += 1
            time.sleep(1)  # 等待一秒后重试
    else:
        raise Exception(f'持续导出异常，请检查。文件路径:{filepath}')


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


def find_ancestor(obj):
    ancestor = obj
    while ancestor.parent is not None:
        ancestor = ancestor.parent
    return ancestor


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


def is_plugin_enabled(plugin_name):
    for addon in bpy.context.preferences.addons:
        if addon.module == plugin_name:
            return True
    return False


def batch_process(func, props, f_flag=False):
    batch = props.batch
    directory = batch.directory
    abs_path = bpy.path.abspath(directory)
    threshold = batch.threshold
    suffix = batch.suffix
    get_collection(TMP_COLLECTION_NAME)
    start_time = time.time()
    file_list = recursive_search(abs_path, suffix, threshold)
    file_count = len(file_list)
    for index, filepath in enumerate(file_list):
        file_base_name = os.path.basename(filepath)
        ext = os.path.splitext(filepath)[1]
        new_filepath = os.path.splitext(filepath)[0] + suffix + ext
        curr_time = time.time()
        import_pmx(filepath)
        pmx_root = bpy.context.active_object
        if f_flag:
            func(pmx_root, props, filepath)
        else:
            func(pmx_root, props)
        export_pmx(new_filepath)
        clean_scene()
        print(
            f"文件 \"{file_base_name}\" 处理完成，进度{index + 1}/{file_count}，耗时{time.time() - curr_time}秒，总耗时: {time.time() - start_time} 秒")
    print(f"目录\"{abs_path}\" 处理完成，总耗时: {time.time() - start_time} 秒")


def show_batch_props(box, batch):
    batch_row = box.row()
    batch_row.prop(batch, "flag")
    batch_flag = batch.flag
    if not batch_flag:
        return
    batch_box = box.box()
    directory_row = batch_box.row()
    directory_row.prop(batch, "directory")
    threshold_row = batch_box.row()
    threshold_row.prop(batch, "threshold")
    suffix_row = batch_box.row()
    suffix_row.prop(batch, "suffix")
    return batch_box


def check_batch_props(operator, batch):
    suffix = batch.suffix
    directory = batch.directory

    if not is_plugin_enabled("mmd_tools"):
        operator.report(type={'ERROR'}, message=f'未开启mmd_tools插件！')
        return False

    # 获取目录的全限定路径 这里用blender提供的方法获取，而不是os.path.abspath。没有必要将相对路径转为绝对路径，因为哪种路径是由用户决定的
    # https://blender.stackexchange.com/questions/217574/how-do-i-display-the-absolute-file-or-directory-path-in-the-ui
    # 如果用户随意填写，可能会解析成当前blender文件的同级路径，但不影响什么
    abs_path = bpy.path.abspath(directory)
    if not os.path.exists(abs_path):
        operator.report(type={'ERROR'}, message=f'模型目录不存在！')
        return False
    # 获取目录所在盘符的根路径
    drive, tail = os.path.splitdrive(abs_path)
    drive_root = os.path.join(drive, os.sep)
    # 校验目录是否是盘符根目录
    if abs_path == drive_root:
        operator.report(type={'ERROR'}, message=f'模型目录为盘符根目录，请更换为其它目录！')
        return False

    # 仅简单校验下后缀是否合法
    if any(char in suffix for char in INVALID_CHARS):
        operator.report(type={'ERROR'}, message=f'名称后缀不合法！')
        return False
    return True


def restore_selection(selected_objects, active_object):
    """ 恢复选中状态"""
    for selected_object in selected_objects:
        select_and_activate(selected_object)
    # 如果物体是隐藏的，选择了它，selected_objects无法获取到隐藏物体，active_object可以获取到隐藏物体
    # 如果先选择隐藏物体，再多选其它非隐藏物体，selected_objects无法获取到隐藏物体，active_object是None
    # 如果先选择非隐藏物体，再多选其它隐藏物体，selected_objects无法获取到隐藏物体，active_object是最先选择的非隐藏物体
    if active_object:
        select_and_activate(active_object)
