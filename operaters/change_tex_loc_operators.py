import os.path
import shutil

from ..utils import *


class ChangeTexLocOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.change_tex_loc"
    bl_label = "修改"
    bl_description = "修改贴图路径"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self, props):
        batch = props.batch
        new_folder = props.new_folder

        if not new_folder:
            self.report(type={'ERROR'}, message=f'Texture folder name required!')
            return False
        if any(char in new_folder for char in INVALID_CHARS):
            self.report(type={'ERROR'}, message=f'Invalid texture folder name!')
            return False

        if not check_batch_props(self, batch):
            return False
        return True

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_change_tex_loc
        if not self.check_props(props):
            return
        batch_process(do_change_tex_loc, props, f_flag=True)


def do_change_tex_loc(pmx_root, props, filepath):
    change_texture_paths(pmx_root, filepath, props)
    move_textures(filepath, props)
    delete_empty_folders(os.path.dirname(filepath), props)


def change_texture_paths(pmx_root, pmx_file, props):
    """修改纹理路径、球体纹理路径（sph）、卡通纹理路径（toon）"""
    new_folder = props.new_folder.strip()
    tex_folder = os.path.join(os.path.dirname(pmx_file), new_folder)

    # mmd_tools v4.5.6新增相对路径参数 https://github.com/MMD-Blender/blender_mmd_tools/releases/tag/v4.5.6
    use_rel_path = get_mmd_tools_version() >= (4, 5, 6)

    armature = find_pmx_armature(pmx_root)
    objs = find_pmx_objects(armature)

    for obj in objs:
        for slot in obj.material_slots:
            material = slot.material
            if not material:
                continue

            mmd_material = material.mmd_material


            # ======================
            # 先处理 base + sph texture，防止处理toon texture时continue退出循环
            # ======================

            node_tree = material.node_tree
            if not node_tree:
                continue

            for node in node_tree.nodes:
                if node.type != 'TEX_IMAGE':
                    continue
                if node.name not in ('mmd_base_tex', 'mmd_sphere_tex'):
                    continue
                image = node.image
                if not image:
                    continue

                filename = os.path.basename(image.filepath)
                image.filepath = os.path.join(tex_folder, filename)

                if not use_rel_path:
                    continue

                rel_path = os.path.join(new_folder, filename)
                if node.name == 'mmd_base_tex':
                    mmd_material.texture_rel_path = rel_path
                else:
                    mmd_material.sphere_texture_rel_path = rel_path

            # ======================
            # toon texture
            # ======================

            toon = mmd_material.toon_texture
            if toon is None or toon.strip() == "":
                continue

            filename = os.path.basename(toon)
            mmd_material.toon_texture = os.path.join(tex_folder, filename)
            if not use_rel_path:
                continue

            mmd_material.toon_texture_rel_path = os.path.join(
                new_folder,
                filename
            )



def change_texture_filepaths(pmx_root, pmx_file, new_folder):
    pmx_path = os.path.dirname(pmx_file)
    tex_folder = os.path.join(pmx_path, new_folder)

    armature = find_pmx_armature(pmx_root)
    objs = find_pmx_objects(armature)

    for obj in objs:
        for slot in obj.material_slots:
            material = slot.material
            if not material:  # 有材质槽但无材质
                continue

            node_tree = material.node_tree
            if not node_tree:  # 有材质但无节点树
                continue

            nodes = node_tree.nodes
            if not nodes:  # 有节点树但无节点
                continue

            for node in nodes:
                if node.type != 'TEX_IMAGE':
                    continue
                if node.name not in ['mmd_base_tex', 'mmd_sphere_tex']:
                    continue
                # 获取纹理图像的路径
                image = node.image
                if not image:
                    continue
                directory, filename = os.path.split(image.filepath)
                new_filepath = os.path.join(tex_folder, filename)
                image.filepath = new_filepath

                mmd_tools_version = get_mmd_tools_version()
                if mmd_tools_version >= (4, 5, 6):
                    if node.name == 'mmd_base_tex':
                        material.mmd_material.texture_rel_path = os.path.join(new_folder, filename)
                    else:
                        material.mmd_material.sphere_texture_rel_path = os.path.join(new_folder, filename)


def change_toon_texture_filepaths(pmx_root, pmx_file, new_folder):
    tex_folder = os.path.join(os.path.dirname(pmx_file), new_folder)
    mmd_tools_version = get_mmd_tools_version() >= (4, 5, 6)

    armature = find_pmx_armature(pmx_root)
    objs = find_pmx_objects(armature)

    for obj in objs:
        for slot in obj.material_slots:
            material = slot.material
            if not material:
                continue

            mmd_material = material.mmd_material
            toon_texture = mmd_material.toon_texture

            if not toon_texture or not toon_texture.strip():
                continue

            filename = os.path.basename(toon_texture)
            new_filepath = os.path.join(tex_folder, filename)
            mmd_material.toon_texture = new_filepath

            if mmd_tools_version:
                mmd_material.toon_texture_rel_path = os.path.join(new_folder, filename)


def move_textures(pmx_file, props):
    """移动pmx目录下所有图像文件到指定目录中"""
    new_folder = props.new_folder.strip()

    pmx_path = os.path.dirname(pmx_file)
    tex_folder = os.path.join(pmx_path, new_folder)
    os.makedirs(tex_folder, exist_ok=True)

    image_extensions = set(IMG_TYPE_EXT_MAP.values())

    for root, dirs, files in os.walk(pmx_path):
        # 不扫描目标文件夹（避免自己移动自己）
        if os.path.abspath(root) == os.path.abspath(tex_folder):
            continue

        for file in files:

            ext = os.path.splitext(file)[1].lower()
            if ext not in image_extensions:
                continue

            src_path = os.path.join(root, file)
            dest_path = os.path.join(tex_folder, file)

            # 已存在直接跳过（更安全）
            if os.path.exists(dest_path):
                continue

            shutil.move(src_path, dest_path)


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
                os.remove(thumbs_db_path)

        for d in dirs:
            dir_path = os.path.join(root, d)
            if os.listdir(dir_path):
                continue
            os.rmdir(dir_path)
