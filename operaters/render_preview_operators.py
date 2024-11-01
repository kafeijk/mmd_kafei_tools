import mathutils

from ..utils import *


class LoadRenderPresetOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.load_render_preset"
    bl_label = "加载渲染预设"
    bl_description = "加载渲染预设"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene

        # 渲染属性
        # 渲染引擎
        if bpy.app.version < (4, 0, 0):
            bpy.context.scene.render.engine = 'BLENDER_EEVEE'
            # 运动模糊
            bpy.context.scene.eevee.use_motion_blur = False
        else:
            bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
            bpy.context.scene.render.use_motion_blur = False


        # 采样
        bpy.context.scene.eevee.taa_render_samples = 32
        bpy.context.scene.eevee.taa_samples = 16
        bpy.context.scene.eevee.use_taa_reprojection = True
        # 环境光遮蔽
        bpy.context.scene.eevee.use_gtao = False
        # 辉光
        bpy.context.scene.eevee.use_bloom = False
        # 次表面散射
        bpy.context.scene.eevee.sss_samples = 7
        # 屏幕空间反射 todo 是否关闭待确认
        bpy.context.scene.eevee.use_ssr = False

        # 阴影
        bpy.context.scene.eevee.shadow_cube_size = '1024'
        bpy.context.scene.eevee.shadow_cascade_size = '1024'
        bpy.context.scene.eevee.use_shadow_high_bitdepth = True
        bpy.context.scene.eevee.use_soft_shadows = True
        # 胶片透明
        bpy.context.scene.render.film_transparent = True
        # 色彩管理
        try:
            bpy.context.scene.display_settings.display_device = 'ACES'
            bpy.context.scene.view_settings.view_transform = 'Rec.709'
            bpy.context.scene.view_settings.look = 'None'
            bpy.context.scene.view_settings.exposure = 0
            bpy.context.scene.view_settings.gamma = 1
            bpy.context.scene.sequencer_colorspace_settings.name = 'sRGB'
        except Exception as e:
            print(f"调整色彩管理参数失败")

        # 输出属性
        # 分辨率
        bpy.context.scene.render.resolution_x = 1024
        bpy.context.scene.render.resolution_y = 1024
        # 帧率
        bpy.context.scene.render.fps = 30
        # 帧范围
        bpy.context.scene.frame_start = 1
        # 当前帧
        bpy.context.scene.frame_current = 1
        # 输出
        bpy.context.scene.render.use_file_extension = True
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'
        bpy.context.scene.render.image_settings.color_depth = '8'
        bpy.context.scene.render.image_settings.compression = 15
        bpy.context.scene.render.use_overwrite = True
        bpy.context.scene.render.image_settings.color_management = 'FOLLOW_SCENE'

        # 其他项
        # 显示叠加层
        bpy.context.space_data.overlay.show_overlays = False
        # 着色方式 渲染
        bpy.context.space_data.shading.type = 'RENDERED'
        # 关闭透视模式 https://blender.stackexchange.com/questions/159525/how-to-toggle-xray-in-viewport-with-python
        views3d = [a for a in bpy.context.screen.areas if a.type == 'VIEW_3D']
        for a in views3d:
            shading = a.spaces.active.shading
            shading.show_xray = False
            shading.show_xray_wireframe = False

            # 切换到自定义世界环境
            world_name = "forest"
            target_world = bpy.data.worlds.new(world_name)
            if target_world.name != world_name:
                target_world.name = world_name
            # 确保新的世界使用节点
            target_world.use_nodes = True
            world_nodes = target_world.node_tree
            world_nodes.nodes.clear()
            # 创建 Texture Coordinate 节点
            tex_coord_node = world_nodes.nodes.new(type='ShaderNodeTexCoord')
            tex_coord_node.location = (-700, 0)
            # 创建 Mapping 节点
            mapping_node = world_nodes.nodes.new(type='ShaderNodeMapping')
            mapping_node.location = (-500, 0)
            # 创建天空球纹理节点
            env_tex_node = world_nodes.nodes.new(type='ShaderNodeTexEnvironment')
            env_tex_node.location = (-300, 0)
            # 创建 Background 节点
            background_node = world_nodes.nodes.new(type='ShaderNodeBackground')
            background_node.location = (0, 0)
            # 创建 World Output 节点
            world_output_node = world_nodes.nodes.new(type='ShaderNodeOutputWorld')
            world_output_node.location = (200, 0)

            # 获取 Blender 安装目录
            blender_binary_path = bpy.app.binary_path
            blender_install_dir = os.path.dirname(blender_binary_path)
            # 环境纹理路径
            env_texture_path = os.path.join(blender_install_dir, os.path.basename(blender_install_dir).split(" ")[1],
                                            'datafiles',
                                            'studiolights', 'world', 'forest.exr')

            # 环境纹理是否存在
            env_existed = os.path.exists(env_texture_path)
            # 是否启用aces流
            utility_linear_srgb = False
            if not env_existed:
                self.report(type={'WARNING'}, message=f'未找到环境贴图，请自行添加！参考路径：{env_texture_path}')
            else:
                image = bpy.data.images.load(env_texture_path, check_existing=True)
                env_tex_node.image = image
                try:
                    image.colorspace_settings.name = 'Utility - Linear - sRGB'
                    utility_linear_srgb = True
                except Exception as e:
                    image.colorspace_settings.name = 'sRGB'

            # 依次按顺序相连接
            world_nodes.links.new(tex_coord_node.outputs['Generated'], mapping_node.inputs['Vector'])
            world_nodes.links.new(mapping_node.outputs['Vector'], env_tex_node.inputs['Vector'])
            if os.path.exists(env_texture_path) and utility_linear_srgb:
                world_nodes.links.new(env_tex_node.outputs['Color'], background_node.inputs['Color'])
            world_nodes.links.new(background_node.outputs['Background'], world_output_node.inputs['Surface'])

            # 增加背景强度
            background_node.inputs['Strength'].default_value = 1.5

            # 设置世界环境
            bpy.context.scene.world = target_world

            # 隐藏场景中所有灯光
            lights = [obj for obj in bpy.context.scene.objects if obj.type == 'LIGHT']
            for light in lights:
                set_visibility(light, (False, True, False, True))


class GenPreviewCameraOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.gen_preview_camera"
    bl_label = "预览"
    bl_description = "生成预览相机，仅预览用，渲染时相机参数取决于插件面板设置"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        if not self.check_props():
            return {'FINISHED'}
        scene = context.scene
        props = scene.mmd_kafei_tools_render_preview
        camera_to_view_selected(props)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self):
        objs = bpy.context.selected_objects
        if len(objs) == 0:
            return False
        return True


class RenderPreviewOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.render_preview"
    bl_label = "渲染"
    bl_description = "渲染预览图"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_render_preview
        if not self.check_render_preview_props(props):
            return
        batch = props.batch
        batch_flag = batch.flag
        directory = batch.directory
        abs_path = bpy.path.abspath(directory)
        threshold = batch.threshold
        suffix = batch.suffix

        force_center = props.force_center
        output_format = bpy.context.scene.render.image_settings.file_format
        if batch_flag:
            # 自动弹出控制台查看进度，貌似实现不了，让用户自主开启（windows外的系统不一定能自主开启）
            # 因为脚本执行时间很长，所以进度条也没什么用，就算有进度条也会被卡顿的转圈圈代替

            # 批量渲染
            start_time = time.time()
            # 同一文件夹下出现"角色的多个pmx差分"或者"角色武器放在一起"很常见，所以搜索到的每个符合条件的pmx文件都会被渲染
            file_list = recursive_search_by_img(abs_path, suffix, IMG_TYPE_EXT_MAP[output_format], threshold)
            file_count = len(file_list)
            for index, filepath in enumerate(file_list):
                # 获取临时集合
                get_collection(TMP_COLLECTION_NAME)
                file_base_name = os.path.basename(filepath)
                new_filepath = os.path.splitext(filepath)[0] + suffix + IMG_TYPE_EXT_MAP[output_format]
                curr_time = time.time()
                import_pmx(filepath)
                print(f"\"{file_base_name}\"导入完成")
                pmx_root = bpy.context.active_object
                pmx_armature = find_pmx_armature(pmx_root)
                convert_materials(pmx_armature, force_center)
                print(f"\"{file_base_name}\"材质转换完成")

                # 相机对准角色
                show_object(pmx_root)
                hide_object(pmx_armature)
                select_and_activate(pmx_root)
                camera_to_view_selected(props)
                print(f"\"{file_base_name}\"对准完成")

                # 隐藏可能会对渲染结果造成影响的物体
                hide_object(pmx_root)
                deselect_all_objects()

                # 备份原始输出路径
                original_output_path = bpy.context.scene.render.filepath
                # 渲染
                bpy.context.scene.render.filepath = new_filepath
                render(False)

                # 恢复原始输出路径
                bpy.context.scene.render.filepath = original_output_path

                clean_scene()
                print(
                    f"\"{file_base_name}\" 渲染完成，进度{index + 1}/{file_count}，耗时{time.time() - curr_time}秒，总耗时: {time.time() - start_time} 秒")
            print(f"目录\"{abs_path}\" 渲染完成，总耗时: {time.time() - start_time} 秒")
        else:
            objs = bpy.context.selected_objects
            if len(objs) != 0:
                camera_to_view_selected(props)
            render(True)

    def check_render_preview_props(self, props):
        batch = props.batch
        batch_flag = batch.flag
        if batch_flag:
            if not check_batch_props(self, batch):
                return False
            output_format = bpy.context.scene.render.image_settings.file_format
            if output_format not in IMG_TYPE_EXT_MAP.keys():
                self.report(type={'ERROR'}, message=f'输出文件格式不正确，请更改为图像类型格式！')
                return False
        else:
            objs = bpy.context.selected_objects
            if len(objs) == 0:
                # 什么都不选择的话，以当前视角输出
                pass
        return True


def convert_materials(pmx_armature, force_center):
    pmx_objects = find_pmx_objects(pmx_armature)

    # 材质名称与MMDShaderDev的alpha值的映射
    material_alpha_map = {}
    for obj in pmx_objects:
        if not obj.material_slots:  # 材质槽为空
            continue
        for slot in obj.material_slots:
            material = slot.material
            if not material:  # 有材质槽但无材质
                continue
            material_alpha_map[material.name] = 1  # 默认1

        for material_name, alpha in material_alpha_map.items():
            material = bpy.data.materials.get(material_name)
            node_tree = material.node_tree
            if not node_tree:  # 有材质但无节点树
                continue

            nodes = node_tree.nodes
            if not nodes:  # 有节点树但无节点
                continue
            # 预先存储原始alpha值以供后续修改
            for node in nodes:
                if node.type == 'GROUP' and node.node_tree.name == "MMDShaderDev":
                    mmd_shader_dev = node
                    for input_node in mmd_shader_dev.inputs:
                        if "Alpha" == input_node.name:
                            material_alpha_map[material.name] = input_node.default_value
        # 选中并转换为blender材质
        select_and_activate(obj)
        bpy.ops.mmd_tools.convert_materials()

    # 将当前材质的不透明度恢复为材质转换前的不透明度
    for material_name, alpha in material_alpha_map.items():
        material = bpy.data.materials.get(material_name)
        node_tree = material.node_tree
        nodes = node_tree.nodes
        for node in nodes:
            if node.type == 'BSDF_PRINCIPLED':
                specular_node = node.inputs['Specular']
                specular_node.default_value = 0
                if alpha == 1:
                    continue
                alpha_node = node.inputs['Alpha']
                for link in material.node_tree.links:
                    if link.to_node == node and link.to_socket == alpha_node:
                        material.node_tree.links.remove(link)
                alpha_node.default_value = alpha

    # 如果强制居中，则按材质分开，删除不透明度为0的物体
    if force_center:
        # 按材质分开
        bpy.ops.mmd_tools.separate_by_materials()
        # 重新获取场景中的物体
        pmx_objects = find_pmx_objects(pmx_armature)
        objs_to_remove = set()
        for pmx_object in pmx_objects:
            # 获取对象的材质列表
            materials = pmx_object.data.materials
            # 检查每个材质是否与指定名称匹配
            for material in materials:
                if material and material.name in material_alpha_map and material_alpha_map[material.name] == 0:
                    objs_to_remove.add(pmx_object)
        for obj_to_remove in objs_to_remove:
            bpy.data.objects.remove(obj_to_remove, do_unlink=True)


def camera_to_view_selected(props):
    camera = gen_preview_camera(props)

    # 备份当前选中和激活的对象
    active_object = bpy.context.active_object
    objs = bpy.context.selected_objects

    # 获取选中物体最外层祖先的孩子set
    ancestors = set()
    children = set()
    for obj in objs:
        ancestor = find_ancestor(obj)
        ancestors.add(ancestor)
    for ancestor in ancestors:
        children.update(find_children(ancestor))
    for child in children:
        select_and_activate(child)

    align = props.align
    # 随便选择一个ancestor
    ancestor = next(iter(ancestors))
    if align:
        # 获取 ancestor 的坐标
        ancestor_location = ancestor.location.copy()
        # 将 ancestor 移动到 (0, 0, 0) 原点位置
        ancestor.location = mathutils.Vector((0, 0, 0))
        # 计算坐标差值
        delta = ancestor_location - mathutils.Vector((0, 0, 0))

    # 修改相机参数
    camera.rotation_mode = 'XYZ'

    camera.rotation_euler[0] = props.rotation_euler_x
    if align:
        camera.rotation_euler[1] = math.radians(0)
    else:
        camera.rotation_euler[1] = props.rotation_euler_y
    camera.rotation_euler[2] = props.rotation_euler_z

    if abs(camera.data.passepartout_alpha - 0.5) < 0.0001:
        camera.data.passepartout_alpha = 1

    camera_type = props.type
    if camera_type == "PERSPECTIVE":
        camera.data.type = 'PERSP'
    elif camera_type == "ORTHOGRAPHIC":
        camera.data.type = 'ORTHO'
    else:
        pass
    # 激活该相机
    bpy.context.scene.camera = camera

    if align:
        constraint = camera.constraints.new(type='LIMIT_LOCATION')
        # 设置局部X轴的最小值和最大值
        constraint.use_min_x = True
        constraint.use_max_x = True
        constraint.min_x = 0.0
        constraint.max_x = 0.0
        # 设置约束为局部空间
        constraint.owner_space = 'LOCAL'
        # 将这个约束放到首位
        camera.constraints.move(len(camera.constraints) - 1, 0)

    # 对准选中物体
    bpy.ops.view3d.camera_to_view_selected()
    # 切换下视图（确保view_camera执行后肯定在相应视图）
    bpy.ops.view3d.view_axis(type='FRONT')
    # 视图 - 摄像机 对应快捷键0
    bpy.ops.view3d.view_camera()
    # 摄像机边界框 对应快捷键home
    bpy.ops.view3d.view_center_camera()

    if align:
        # 这里要选中后才能应用
        # 如果存在约束，用户调整相机角度时会受到限制拖拽不动，所以这里应用掉
        select_and_activate(camera)
        constraint = camera.constraints[0]
        bpy.ops.constraint.apply(constraint=constraint.name, owner='OBJECT')

        # 将 ancestor 移动回原来的位置
        ancestor.location = ancestor_location
        camera.location += delta

    # 调整边距
    if camera_type == "PERSPECTIVE":
        # 这里实际上修改的是视野，而非“焦距”
        camera.data.angle = camera.data.angle * props.scale
    elif camera_type == "ORTHOGRAPHIC":
        camera.data.ortho_scale = camera.data.ortho_scale * props.scale
    else:
        pass

    # 恢复默认选中
    deselect_all_objects()
    for obj in objs:
        select_and_activate(obj)
    select_and_activate(active_object)


def gen_preview_camera(props):
    # 在“预览相机”集合中生成一个相机
    # 检查是否已有名为“预览相机”的相机对象
    # 即使场景中存在其它相机，也不把这个相机进行返回，因为不清楚这个相机的用途
    camera_name = "预览相机"
    custom_property_name = 'preview_camera'
    for camera in bpy.data.objects:
        if camera.type == 'CAMERA' and custom_property_name in camera.keys():

            # 恢复相机参数默认值
            camera_type = props.type
            if camera_type == "PERSPECTIVE":
                camera.data.lens_unit = 'MILLIMETERS'
                camera.data.lens = 50
            elif camera_type == "ORTHOGRAPHIC":
                camera.data.ortho_scale = 6
            else:
                pass
            return camera
    # 场景中是否含有名称为“预览相机”的集合，没有则不一定新建（没有相机的情况下才会新建）
    collection_name = "预览相机"
    if collection_name in bpy.data.collections:
        preview_collection = bpy.data.collections[collection_name]
    else:
        preview_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(preview_collection)

    camera_data = bpy.data.cameras.new(name=camera_name)
    camera = bpy.data.objects.new(name=camera_name, object_data=camera_data)
    # omit the setter with a given getter to make it read-only
    bpy.types.Object.preview_camera = bpy.props.BoolProperty(get=lambda obj: obj.get('preview_camera', False))
    camera['preview_camera'] = True

    preview_collection.objects.link(camera)
    return camera


def render(view_show):
    shading_type = bpy.context.space_data.shading.type
    if shading_type == 'RENDERED':
        if view_show:
            bpy.ops.render.render("INVOKE_DEFAULT")
            bpy.ops.render.view_show()
        else:
            bpy.ops.render.render(write_still=True)
    else:
        if view_show:
            bpy.ops.render.opengl("INVOKE_DEFAULT")
            bpy.ops.render.view_show()
        else:
            bpy.ops.render.opengl(write_still=True)
