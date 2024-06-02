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
        suffix = props.suffix
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

        if batch:
            if not is_plugin_enabled("mmd_tools"):
                self.report(type={'ERROR'}, message=f'未开启mmd_tools插件！')
                return False
            # 仅简单校验下后缀是否合法
            if any(char in suffix for char in INVALID_CHARS):
                self.report(type={'ERROR'}, message=f'名称后缀不合法！')
                return False
            directory = props.directory
            # 获取目录的全限定路径 这里用blender提供的方法获取，而不是os.path.abspath。没有必要将相对路径转为绝对路径，因为哪种路径是由用户决定的
            # https://blender.stackexchange.com/questions/217574/how-do-i-display-the-absolute-file-or-directory-path-in-the-ui
            # 如果用户随意填写，可能会解析成当前blender文件的同级路径，但不影响什么
            abs_path = bpy.path.abspath(directory)
            if not os.path.exists(abs_path):
                self.report(type={'ERROR'}, message=f'模型目录不存在！')
                return False
            # 获取目录所在盘符的根路径
            drive, tail = os.path.splitdrive(abs_path)
            drive_root = os.path.join(drive, os.sep)
            # 校验目录是否是盘符根目录
            if abs_path == drive_root:
                self.report(type={'ERROR'}, message=f'模型目录为盘符根目录，请更换为其它目录！')
                return False
        else:
            active_object = bpy.context.active_object
            if not active_object:
                self.report(type={'ERROR'}, message=f'请选择MMD模型')
                return False
            pmx_root = find_ancestor(active_object)
            if pmx_root.mmd_type != "ROOT":
                self.report(type={'ERROR'}, message=f'请选择MMD模型')
                return False
            armature = find_pmx_armature(pmx_root)
            if not armature:
                self.report(type={'ERROR'}, message=f'请选择MMD模型')
                return False
        return True

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_change_tex_loc
        if not self.check_props(props):
            return
        new_folder = props.new_folder
        batch = props.batch
        directory = props.directory
        abs_path = bpy.path.abspath(directory)
        threshold = props.threshold
        suffix = props.suffix
        remove_empty = props.remove_empty

        if batch:
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
                # 修改纹理和球体纹理路径（sph）
                change_texture_filepaths(filepath, new_folder)
                # 修改卡通纹理路径（toon）
                change_toon_texture_filepaths(filepath, new_folder)
                # 移动pmx目录下所有图像文件到指定目录中
                move_tex(filepath, new_folder)
                # 循环内删除空文件夹，不含递归，将删除空文件夹的操作范围限定在pmx目录中
                if remove_empty:
                    delete_empty_folders(os.path.dirname(filepath))
                select_and_activate(pmx_root)
                export_pmx(new_filepath)
                clean_scene()
                print(
                    f"文件 \"{file_base_name}\" 处理完成，进度{index + 1}/{file_count}，耗时{time.time() - curr_time}秒，总耗时: {time.time() - start_time} 秒")
            # 删除空文件夹

            print(f"目录\"{abs_path}\" 处理完成，总耗时: {time.time() - start_time} 秒")


def change_texture_filepaths(pmx_file, new_folder):
    pmx_path = os.path.dirname(pmx_file)
    tex_folder = os.path.join(pmx_path, new_folder)
    for img in bpy.data.images:
        directory, filename = os.path.split(img.filepath)
        new_filepath = os.path.join(tex_folder, filename)
        img.filepath = new_filepath


def change_toon_texture_filepaths(pmx_file, new_folder):
    pmx_path = os.path.dirname(pmx_file)
    tex_folder = os.path.join(pmx_path, new_folder)
    for material in bpy.data.materials:
        # 如果为空则不修改
        if not material.mmd_material.toon_texture:
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
