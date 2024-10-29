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

        count = len(bpy.data.objects)
        if count > 3:  # 灯光、相机、立方体
            self.report(type={'ERROR'}, message=f'检测到场景中物体数量大于3，请在默认常规场景中执行！')
            return False
        if not new_folder:
            self.report(type={'ERROR'}, message=f'请填写贴图文件夹名称')
            return False
        if any(char in new_folder for char in INVALID_CHARS):
            self.report(type={'ERROR'}, message=f'贴图文件夹名称不合法！')
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
    new_folder = props.new_folder
    new_folder = new_folder.strip()
    remove_empty = props.remove_empty
    # 修改纹理和球体纹理路径（sph）
    change_texture_filepaths(filepath, new_folder)
    # 修改卡通纹理路径（toon）
    change_toon_texture_filepaths(filepath, new_folder)
    # 移动pmx目录下所有图像文件到指定目录中
    move_tex(filepath, new_folder)
    # 循环内删除空文件夹，不含递归，将删除空文件夹的操作范围限定在pmx目录中
    if remove_empty:
        delete_empty_folders(os.path.dirname(filepath))


def change_texture_filepaths(pmx_file, new_folder):
    pmx_path = os.path.dirname(pmx_file)
    tex_folder = os.path.join(pmx_path, new_folder)
    for img in bpy.data.images:
        ext = os.path.splitext(img.filepath)[1]
        if ext.lower() == ".exr":  # 如果世界环境变紫，可能会对使用者造成困惑
            continue
        directory, filename = os.path.split(img.filepath)
        new_filepath = os.path.join(tex_folder, filename)
        img.filepath = new_filepath


def change_toon_texture_filepaths(pmx_file, new_folder):
    pmx_path = os.path.dirname(pmx_file)
    tex_folder = os.path.join(pmx_path, new_folder)
    for material in bpy.data.materials:
        # 如果路径为空则不修改（如果是共用的卡通纹理，则其无路径，也不会被修改）
        toon_texture = material.mmd_material.toon_texture
        if toon_texture is not None and toon_texture.strip() != '':
            directory, filename = os.path.split(material.mmd_material.toon_texture)
            new_filepath = os.path.join(tex_folder, filename)
            material.mmd_material.toon_texture = new_filepath


def move_tex(pmx_file, new_folder):
    # pmx文件所在目录
    pmx_path = os.path.dirname(pmx_file)
    # 创建存储图片的文件夹
    tex_folder = os.path.join(pmx_path, new_folder)
    if not os.path.exists(tex_folder):
        os.makedirs(tex_folder)

    # 图片文件的扩展名列表
    image_extensions = set(IMG_TYPE_EXT_MAP.values())

    # 递归遍历文件夹中的所有文件
    for root, dirs, files in os.walk(pmx_path):
        for file in files:
            # 检查文件扩展名是否是图片格式，不区分大小写
            if os.path.splitext(file)[1].lower() in image_extensions:
                # 获取图片的绝对路径
                src_path = os.path.join(root, file)
                # 目标路径
                dest_path = os.path.join(tex_folder, file)
                # 如果不存在，则移动过去，如果存在，则让用户自己处理（文件可能是只读的；文件虽然同名但内容不同），稳妥一些
                if not os.path.exists(dest_path):
                    shutil.move(src_path, dest_path)


def delete_empty_folders(folder_path):
    # 遍历文件夹中的所有文件和子文件夹
    for root, dirs, files in os.walk(folder_path, topdown=False):
        for file in files:
            # 如果存在Thumbs.db文件（缩略图缓存），删除它
            if file.lower() == "thumbs.db":
                thumbs_db_path = os.path.join(root, file)
                os.remove(thumbs_db_path)

        for d in dirs:
            dir_path = os.path.join(root, d)
            # 检查文件夹是否为空
            if not os.listdir(dir_path):
                # 删除空文件夹
                os.rmdir(dir_path)
