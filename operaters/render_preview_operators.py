import mathutils

from ..utils import *


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
        search_strategy = batch.search_strategy
        conflict_strategy = batch.conflict_strategy

        force_center = props.force_center
        output_format = bpy.context.scene.render.image_settings.file_format
        if batch_flag:
            # 自动弹出控制台查看进度，貌似实现不了，让用户自主开启（windows外的系统不一定能自主开启）
            # 因为脚本执行时间很长，所以进度条也没什么用，就算有进度条也会被卡顿的转圈圈代替

            # 批量渲染
            start_time = time.time()
            file_list = recursive_search_img(abs_path, suffix, threshold, search_strategy, conflict_strategy,
                                             IMG_TYPE_EXT_MAP[output_format])
            file_count = len(file_list)
            for index, filepath in enumerate(file_list):
                # 获取临时集合
                get_collection(TMP_COLLECTION_NAME)
                file_base_name = os.path.basename(filepath)
                new_filepath = os.path.splitext(filepath)[0] + suffix + IMG_TYPE_EXT_MAP[output_format]
                curr_time = time.time()
                import_pmx(filepath)
                pmx_root = bpy.context.active_object
                pmx_armature = find_pmx_armature(pmx_root)
                convert_materials(pmx_armature, force_center)

                # 相机对准角色
                show_object(pmx_root)
                hide_object(pmx_armature)
                select_and_activate(pmx_root)
                camera_to_view_selected(props)

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
                msg = bpy.app.translations.pgettext_iface(
                    "\"{}\" rendering completed, progress {}/{} (elapsed {} seconds, total {} seconds)"
                ).format(
                    file_base_name, index + 1, file_count,
                    f"{time.time() - curr_time:.2f}", f"{time.time() - start_time:.2f}"
                )
                print(msg)

            msg = bpy.app.translations.pgettext_iface("Directory \"{}\" rendering completed (total {} seconds)").format(
                abs_path, f"{time.time() - start_time:.2f}",
            )
            print(msg)
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
                self.report(type={'ERROR'}, message=f'Unsupported output format! Use image format instead.')
                return False
        else:
            objs = bpy.context.selected_objects
            if len(objs) == 0:
                # 什么都不选择的话，以当前视角输出
                pass
        return True


def convert_materials(pmx_armature, force_center):
    pmx_objects = find_pmx_objects(pmx_armature)
    if not pmx_objects:
        return

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
                if bpy.app.version < (4, 0, 0):
                    specular_node = node.inputs['Specular']
                else:
                    specular_node = node.inputs['Specular IOR Level']
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
        if len(pmx_objects[0].material_slots) > 1:
            deselect_all_objects()
            select_and_activate(pmx_objects[0])
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


def camera_to_view_selected(props, camera=None):
    if not camera:
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
    restore_selection(objs, active_object)


def gen_preview_camera(props):
    # 在“预览相机”集合中生成一个相机
    # 检查是否已有名为“预览相机”的相机对象
    # 即使场景中存在其它相机，也不把这个相机进行返回，因为不清楚这个相机的用途
    camera_name = bpy.app.translations.pgettext_iface("预览相机")
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
    collection_name = bpy.app.translations.pgettext_iface("预览相机")
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
