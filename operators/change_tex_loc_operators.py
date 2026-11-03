import filecmp
import os.path
import re
import shutil
import bpy

from ..constants import IMG_TYPE_EXT_MAP

from ..utils import (
    find_pmx_armature,
    find_pmx_objects,
    force_writable,
    get_mmd_tools_version,
)


def _norm_path(path):
    return os.path.normcase(os.path.abspath(path))


def _image_path(image):
    if not image or not image.filepath:
        return None
    return _norm_path(bpy.path.abspath(image.filepath))


def _keep_keywords(props):
    value = getattr(props, "keep_names", "") or ""
    return [part.strip().lower() for part in re.split(r"[,，]", value) if part.strip()]


def _same_file(path_a, path_b):
    try:
        return filecmp.cmp(path_a, path_b, shallow=False)
    except OSError:
        return False


def _unique_path(folder, filename):
    """按文件名末尾数字递增生成不冲突的新文件名；没有数字时从 2 开始"""
    stem, ext = os.path.splitext(filename)
    match = re.search(r"(\d+)$", stem)
    if match:
        prefix = stem[:match.start()]
        number = int(match.group(1)) + 1
        width = len(match.group(1))
    else:
        prefix = stem
        number = 2
        width = 1

    while True:
        candidate = f"{prefix}{str(number).zfill(width)}{ext}"
        path = os.path.join(folder, candidate)
        if not os.path.exists(path):
            return path
        number += 1


def collect_referenced_image_paths(pmx_root):
    """收集模型材质实际引用的图片绝对路径"""
    referenced = set()
    armature = find_pmx_armature(pmx_root)
    if not armature:
        return referenced

    for obj in find_pmx_objects(armature):
        for slot in obj.material_slots:
            material = slot.material
            if not material or not material.node_tree:
                continue
            for node in material.node_tree.nodes:
                if node.type != 'TEX_IMAGE' or not node.image:
                    continue
                # 纹理贴图/球形纹理贴图/卡通纹理
                path = _image_path(node.image)
                if path:
                    referenced.add(path)

            # 卡通纹理（双保险）
            mmd_material = getattr(material, "mmd_material", None)
            toon = mmd_material.toon_texture if mmd_material else ""
            if toon and toon.strip():
                referenced.add(_norm_path(bpy.path.abspath(toon)))
    return referenced


def do_change_tex_loc(pmx_root, props, filepath):
    """修改贴图路径"""
    # 先收集引用信息并移动文件，再按最终路径更新材质引用
    referenced_paths = collect_referenced_image_paths(pmx_root)
    path_map = move_textures(filepath, props, referenced_paths)
    change_texture_paths(pmx_root, filepath, props, path_map)
    delete_empty_folders(os.path.dirname(filepath), props)


def change_texture_paths(pmx_root, pmx_file, props, path_map):
    """按移动/改名结果更新图片路径与 mmd_tools 的相对路径"""
    pmx_path = os.path.dirname(pmx_file)
    use_rel_path = get_mmd_tools_version() >= (4, 5, 6)

    def lookup(path):
        if not path:
            return None
        return path_map.get(_norm_path(bpy.path.abspath(path)))

    armature = find_pmx_armature(pmx_root)
    if not armature:
        return

    for obj in find_pmx_objects(armature):
        for slot in obj.material_slots:
            material = slot.material
            if not material:
                continue

            node_tree = material.node_tree
            if not node_tree:
                continue

            mmd_material = getattr(material, "mmd_material", None)
            for node in node_tree.nodes:
                if node.type != 'TEX_IMAGE' or not node.image:
                    continue

                image = node.image
                new_path = lookup(image.filepath)
                if new_path:
                    image.filepath = new_path

                if node.name in ('mmd_base_tex', 'mmd_sphere_tex') and new_path and use_rel_path:
                    rel_path = os.path.relpath(new_path, pmx_path)
                    if node.name == 'mmd_base_tex':
                        mmd_material.texture_rel_path = rel_path
                    else:
                        mmd_material.sphere_texture_rel_path = rel_path

            toon = mmd_material.toon_texture if mmd_material else ""
            if toon and toon.strip():
                new_path = lookup(toon)
                if new_path:
                    mmd_material.toon_texture = new_path
                    if use_rel_path:
                        mmd_material.toon_texture_rel_path = os.path.relpath(new_path, pmx_path)


def move_textures(pmx_file, props, referenced_paths=None):
    """移动 pmx 目录下的图片，按引用关系处理同名冲突，返回源路径到最终路径的映射"""
    new_folder = props.new_folder.strip()
    pmx_path = os.path.dirname(pmx_file)
    tex_folder = os.path.join(pmx_path, new_folder)
    os.makedirs(tex_folder, exist_ok=True)

    image_extensions = set(IMG_TYPE_EXT_MAP.values())
    keep_keywords = _keep_keywords(props)
    strategy = getattr(props, "texture_conflict_strategy", "AUTO")
    referenced = referenced_paths or set()
    path_map = {}
    dest_referenced = {}

    # 收集源文件
    sources = []
    for root, dirs, files in os.walk(pmx_path):
        # 不扫描目标文件夹及其子目录
        if _norm_path(root) == _norm_path(tex_folder):
            dirs[:] = []
            continue

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in image_extensions:
                continue
            if keep_keywords and any(keyword in file.lower() for keyword in keep_keywords):
                continue

            src_path = os.path.join(root, file)
            src_norm = _norm_path(src_path)
            sources.append((src_path, src_norm, src_norm in referenced))

    # 引用文件优先处理，未引用文件让出同名
    sources.sort(key=lambda item: (not item[2], os.path.normcase(item[0])))

    # 移动到新贴图文件夹
    for src_path, src_norm, src_referenced in sources:
        filename = os.path.basename(src_path)
        dest_path = os.path.join(tex_folder, filename)
        dest_norm = _norm_path(dest_path)

        # 如果目标路径存在且类型为文件夹（说明文件名冲突，且为与源文件同名的文件夹），则跳过或更名贴图
        if os.path.exists(dest_path) and not os.path.isfile(dest_path):
            if strategy == 'SKIP':
                continue
            new_path = _unique_path(tex_folder, filename)
            shutil.move(src_path, new_path)
            if src_referenced:
                path_map[src_norm] = new_path
                dest_referenced[_norm_path(new_path)] = True
            continue

        # 如果目标路径存在且为文件（说明文件名冲突）
        if os.path.isfile(dest_path):
            dest_is_referenced = dest_referenced.get(dest_norm, dest_norm in referenced)

            # 如果文件内容一致则删除源文件，引用指向目标文件
            if _same_file(src_path, dest_path):
                if src_referenced:
                    path_map[src_norm] = dest_path
                    dest_referenced[dest_norm] = True
                os.remove(src_path)
                continue

            # 如果不一致且策略为跳过，则跳过处理
            if strategy == 'SKIP':
                continue

            # 如果源贴图与目标路径重名贴图均被引用，则更名源贴图
            if src_referenced and dest_is_referenced:
                new_path = _unique_path(tex_folder, filename)
                shutil.move(src_path, new_path)
                path_map[src_norm] = new_path
                dest_referenced[_norm_path(new_path)] = True
            elif src_referenced:  # 如果目标路径重名贴图未被引用，则先更名它，再将源贴图移动过来
                moved_dest = _unique_path(tex_folder, filename)
                shutil.move(dest_path, moved_dest)
                dest_referenced.pop(dest_norm, None)
                shutil.move(src_path, dest_path)
                path_map[src_norm] = dest_path
                dest_referenced[dest_norm] = True
            else:  # 如果两重名贴图均未被引用，则更名源贴图
                new_path = _unique_path(tex_folder, filename)
                shutil.move(src_path, new_path)
                dest_referenced[_norm_path(new_path)] = False
            continue

        # 如果未发生名称冲突，则直接移动
        shutil.move(src_path, dest_path)
        dest_referenced[dest_norm] = src_referenced
        if src_referenced:
            path_map[src_norm] = dest_path

    return path_map


def delete_empty_folders(folder_path, props):
    """删除空文件夹，范围限定在pmx目录中"""

    remove_empty = props.remove_empty
    if not remove_empty:
        return

    for root, dirs, files in os.walk(folder_path, topdown=False):
        for file in files:
            # 如果存在Thumbs.db文件（缩略图缓存），删除它
            if file.lower() == "thumbs.db":
                thumbs_db_path = os.path.join(root, file)
                try:
                    os.remove(thumbs_db_path)
                except PermissionError:
                    force_writable(thumbs_db_path)
                    try:
                        os.remove(thumbs_db_path)
                    except OSError as e:
                        print(bpy.app.translations.pgettext_iface(
                            f"Failed to delete file, file: {thumbs_db_path}, error: {e}"
                        ))

        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if os.listdir(dir_path):
                    continue
            except PermissionError as e:
                print(bpy.app.translations.pgettext_iface(
                    f"Failed to list folder, folder: {dir_path}, error: {e}"
                ))
                continue
            try:
                os.rmdir(dir_path)
            except PermissionError:
                force_writable(dir_path)
                try:
                    os.rmdir(dir_path)
                except OSError as e:
                    print(bpy.app.translations.pgettext_iface(
                        f"Failed to delete folder, folder: {dir_path}, error: {e}"
                    ))
