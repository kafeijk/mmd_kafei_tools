from .render_preview_operators import camera_to_view_selected
from ..utils import *


class RenderSettingsOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.render_settings"
    bl_label = "执行"
    bl_description = "执行渲染设置"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_render_settings
        engine = props.engine
        # 设置渲染参数。关于着色方式 - 渲染，初始加载可能会耗费时间，因此暂不添加
        if engine == "EEVEE":
            blender_version = bpy.app.version
            if blender_version < (4, 2, 0):
                set_eevee()
            else:
                set_eevee_next()
        elif engine == "CYCLES":
            set_cycles()
        else:
            pass

        # 查看变换
        if bpy.context.scene.display_settings.display_device == 'sRGB':
            bpy.context.scene.view_settings.view_transform = 'Filmic'

        # 着色方式 渲染
        try:
            bpy.context.space_data.shading.type = 'RENDERED'
        except:
            pass


class WorldSettingsOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.world_settings"
    bl_label = "执行"
    bl_description = "设置世界环境"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_world_settings
        world_name = props.world_name
        set_env(self, world_name)


def get_folder(blender_install_dir, folder_name):
    for root, dirs, files in os.walk(blender_install_dir):
        for dir_name in dirs:
            if folder_name in dir_name:
                return os.path.join(root, dir_name)


def set_env(operator, world_name):
    # 确保新的世界使用节点
    if world_name == "DEFAULT":
        world_name = "World"
        world = bpy.data.worlds.new(world_name)
        if world.name != world_name:
            world.name = world_name
        world.use_nodes = True
        world_nodes = world.node_tree
        for node in world_nodes.nodes:
            if node.bl_idname == "ShaderNodeBackground":
                node.inputs[0].default_value = (0, 0, 0, 1)
                node.inputs[1].default_value = 0
        # 设置世界环境
        bpy.context.scene.world = world
        return
    else:
        world_name = world_name.capitalize()
        world = bpy.data.worlds.new(world_name)
        if world.name != world_name:
            world.name = world_name
        world.use_nodes = True
        world_nodes = world.node_tree
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
        # 获取环境纹理路径（递归寻找，防止因blender安装版本/绿色版本文件目录结构差异带来的找不到文件的问题）
        env_folder = get_folder(blender_install_dir, "world")
        env_texture_path = os.path.join(env_folder, f'{world_name}.exr')

        if not os.path.exists(env_texture_path):
            operator.report(type={'WARNING'}, message=bpy.app.translations.pgettext_iface(
                "HDRI Map not found. Add manually. Path: {}").format(env_texture_path))
        else:
            image = bpy.data.images.load(env_texture_path, check_existing=True)
            env_tex_node.image = image

            if bpy.context.scene.display_settings.display_device == 'ACES':
                image.colorspace_settings.name = 'Utility - Linear - sRGB'
            else:
                blender_version = bpy.app.version
                if blender_version < (4, 0, 0):
                    safe_set(image.colorspace_settings, "name", "Linear")  # 2.x 3.x 默认
                else:
                    safe_set(image.colorspace_settings, "name", "Linear Rec.709")  # 4.x 默认

        # 依次按顺序相连接
        world_nodes.links.new(tex_coord_node.outputs['Generated'], mapping_node.inputs['Vector'])
        world_nodes.links.new(mapping_node.outputs['Vector'], env_tex_node.inputs['Vector'])
        world_nodes.links.new(env_tex_node.outputs['Color'], background_node.inputs['Color'])
        world_nodes.links.new(background_node.outputs['Background'], world_output_node.inputs['Surface'])
        # 设置背景强度
        background_node.inputs['Strength'].default_value = 1
        # 设置世界环境
        bpy.context.scene.world = world


def reset(struct):
    """恢复指定结构体默认设置"""
    # setattr(bpy.context.scene.eevee, "use_taa_reprojection", True)
    for prop in struct.bl_rna.properties:
        if prop.identifier == "rna_type":
            continue
        try:
            val = getattr(struct, prop.identifier)
        except:
            continue

        if isinstance(val, bpy.types.bpy_struct):
            reset(val)
        else:
            try:
                default = prop.default
                setattr(struct, prop.identifier, default)
                if prop.identifier == "use_bloom":
                    return
            except Exception:
                pass


def safe_set(obj, attr, value):
    """安全设置属性，如果不存在就跳过"""
    try:
        setattr(obj, attr, value)
    except Exception as e:
        print(f"{e}")


def set_eevee():
    # 预设目的：快速渲染视频。非图像渲染，非渲染高质量视频
    scene = bpy.context.scene
    # 恢复 Eevee 默认设置
    reset(bpy.context.scene.eevee)

    # 渲染引擎 - Eevee
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

    # 环境光遮蔽
    bpy.context.scene.eevee.use_gtao = True
    # 辉光
    bpy.context.scene.eevee.use_bloom = True

    # 屏幕空间反射
    bpy.context.scene.eevee.use_ssr = True
    # 折射
    bpy.context.scene.eevee.use_ssr_refraction = True
    # 半精度追踪
    bpy.context.scene.eevee.use_ssr_halfres = False

    # 运动模糊
    bpy.context.scene.eevee.use_motion_blur = False

    # 阴影
    # 矩形尺寸
    bpy.context.scene.eevee.shadow_cube_size = '1024'
    # 级联大小
    bpy.context.scene.eevee.shadow_cascade_size = '1024'
    # 高位深
    bpy.context.scene.eevee.use_shadow_high_bitdepth = True
    # 柔和阴影
    bpy.context.scene.eevee.use_soft_shadows = True


def set_eevee_next():
    scene = bpy.context.scene
    # 恢复 Eevee 默认设置
    reset(bpy.context.scene.eevee)

    safe_set(scene.render, "engine", "BLENDER_EEVEE_NEXT")

    # 时序重投影。该参数默认值即为True，但参数use_bloom（辉光）会影响到该值的设定，所以这里显示设置
    safe_set(scene.eevee, "use_taa_reprojection", True)
    # 阴影
    safe_set(scene.eevee, "use_shadows", True)
    # 光线数量
    safe_set(scene.eevee, "shadow_ray_count", 4)
    # 步数
    safe_set(scene.eevee, "shadow_step_count", 9)

    # 光线追踪
    safe_set(scene.eevee, "use_raytracing", True)
    safe_set(scene.eevee.ray_tracing_options, "screen_trace_quality", 1)
    safe_set(scene.eevee.ray_tracing_options, "use_denoise", True)
    safe_set(scene.eevee.ray_tracing_options, "denoise_spatial", True)
    safe_set(scene.eevee.ray_tracing_options, "denoise_temporal", True)
    safe_set(scene.eevee.ray_tracing_options, "denoise_bilateral", True)

    # 快速GI近似
    safe_set(scene.eevee, "use_fast_gi", False)
    safe_set(scene.eevee, "fast_gi_ray_count", 8)
    safe_set(scene.eevee, "fast_gi_step_count", 12)
    safe_set(scene.eevee, "fast_gi_quality", 1)

    # 合成器GPU
    safe_set(scene.render, "compositor_device", 'GPU')
    safe_set(scene.render, "compositor_precision", 'FULL')
    safe_set(scene.render, "compositor_denoise_device", 'GPU')

    # 性能 - 内存
    safe_set(scene.eevee, "shadow_pool_size", '1024')
    safe_set(scene.eevee, "gi_irradiance_pool_size", '1024')


def set_cycles():
    scene = bpy.context.scene
    cycles = scene.cycles
    render = scene.render

    # cuda快还是optix快？ optix更快些，但是，如果没有optix或在条件影响下cuda更快，则选择cuda
    # 参考链接：https://irendering.net/is-cuda-or-optix-faster-in-blender-cycles/

    # 渲染设备选自己的GPU。 不要选CPU；不要二者都选

    # 渲染引擎 - Cycles
    bpy.context.scene.render.engine = 'CYCLES'
    # 恢复 Cycles 默认设置
    reset(bpy.context.scene.cycles)

    # 设备 - GPU计算
    safe_set(cycles, "device", 'GPU')

    # 开放式着色语言(OSL) shading_system
    # 通过自己写脚本来定义着色器，文本编辑器的模板中有示例，不会写可以用网上现成的。
    # 自己使用的工程基本无需开启。而且开启可能会出问题。https://blenderartists.org/t/osl-group-data-size-error-optix/1459981

    # 采样 - 视图
    # 噪波阈值  停止采样的噪点级别，达到阈值，渲染结束（感觉像一个容忍度，达到指定阈值就可以停了） 如果调高，镜面会糊些
    safe_set(cycles, "preview_adaptive_threshold", 1)
    # 最大采样
    safe_set(cycles, "preview_samples", 16)
    # 降噪
    safe_set(cycles, "use_preview_denoising", True)
    # 降噪器 - OpenlmageDenoise CPU降噪  / OPTIX GPU降噪
    safe_set(cycles, "preview_denoiser", 'OPTIX')
    # 通道 - 反照与法向
    safe_set(cycles, "preview_denoising_input_passes", 'RGB_ALBEDO_NORMAL')
    # 预过滤 - 快速
    safe_set(cycles, "preview_denoising_prefilter", 'FAST')
    # 起始采样  用于开始对预览降噪的采样点。采样本身就比较低的话，感觉这个参数的值不太能影响什么
    safe_set(cycles, "preview_denoising_start_sample", 0)

    # 采样 - 渲染
    # 噪波阈值  停止采样的噪点级别，达到阈值，渲染结束（感觉像一个容忍度，达到指定阈值就可以停了） 如果调高，镜面会糊些，但会更快结束渲染
    safe_set(cycles, "adaptive_threshold", 0.001)
    # 最大采样 256基本可保证渲染结果不闪烁
    safe_set(cycles, "samples", 256)
    # 降噪
    safe_set(cycles, "use_denoising", True)
    # 降噪器 - OpenlmageDenoise CPU降噪  / OPTIX GPU降噪
    safe_set(cycles, "denoiser", 'OPTIX')
    # 通道 - 反照与法向
    safe_set(cycles, "denoising_input_passes", 'RGB_ALBEDO_NORMAL')
    # 预过滤
    safe_set(cycles, "denoising_prefilter", 'FAST')

    # 光程 - 快速GI近似
    # 开启否 开启后场景会黑不溜秋的，是否开启取决于实际渲染效果
    safe_set(cycles, "use_fast_gi", False)

    # 使用平铺  不开启平铺比开启平铺更快，但内存占用更高（不确定这里指内存还是显存，应该是显存）
    safe_set(cycles, "use_auto_tile", False)
    # 平铺尺寸
    safe_set(cycles, "tile_size", 256)

    # 持久数据
    safe_set(render, "use_persistent_data", True)
    # 像素大小：调大可加速视图渲染，但会增加马赛克
    safe_set(render, "preview_pixel_size", 'AUTO')


class ResolutionSettingsOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.resolution_settings"
    bl_label = "设置视频分辨率"
    bl_description = "设置视频分辨率"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        scene = context.scene
        output = scene.mmd_kafei_tools_output_settings

        # 分辨率对应字典
        res_dict = {
            "360P": (640, 360),
            "480P": (854, 480),
            "540P": (960, 540),
            "720P": (1280, 720),
            "1080P": (1920, 1080),
            "2K": (2560, 1440),
            "4K": (3840, 2160),
            "8K": (7680, 4320),
            "720_4_3": (960, 720),
            "1080_4_3": (1440, 1080),
            "1440_4_3": (1920, 1440),
            "2160_4_3": (2880, 2160)
        }

        width, height = res_dict.get(output.resolution, (1920, 1080))
        scene.render.resolution_x = width
        scene.render.resolution_y = height

        return {'FINISHED'}


class SwapResolutionOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.swap_resolution"
    bl_label = "交换分辨率"
    bl_description = "交换分辨率 X 和 Y"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        scene = context.scene
        rd = scene.render

        # 交换 X 和 Y 分辨率
        rd.resolution_x, rd.resolution_y = rd.resolution_y, rd.resolution_x

        return {'FINISHED'}


def set_cons(obj, target, subtarget=None):
    deselect_all_objects()
    select_and_activate(obj)

    # 移除原先约束
    for constraint in reversed(obj.constraints):
        obj.constraints.remove(constraint)

    # 新建子级约束
    cons = obj.constraints.new('CHILD_OF')

    # 只考虑位置
    cons.use_rotation_x = False
    cons.use_rotation_y = False
    cons.use_rotation_z = False
    cons.use_scale_x = False
    cons.use_scale_y = False
    cons.use_scale_z = False

    # 目标设置
    cons.target = target
    if subtarget:
        cons.subtarget = subtarget

    bpy.ops.constraint.childof_clear_inverse(constraint=cons.name, owner='OBJECT')

    deselect_all_objects()


def get_obj_by_attr_value(attr_name, value):
    for obj in bpy.data.objects:
        if attr_name in obj.keys():  # keys() 返回对象的所有自定义属性名
            if value == obj.get(attr_name):
                return obj
    return None


class LightSettingsOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.light_settings"
    bl_label = "设置"
    bl_description = "设置三点打光"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.gen_light(context)
        return {'FINISHED'}

    def gen_light(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_light_settings

        if self.check_props(props) is False:
            return
        active_object = bpy.context.active_object

        light_coll = get_collection("3 Points Lighting")

        preset = props.preset
        preset_flag = props.preset_flag
        colors = {
            # 主光 - 辅光 - 背光
            # 规则：辅光亮度/饱和度偏低，背光亮度/饱和度偏高
            "DEFAULT": ("#FFD1BC", "#DAEAFF", "#BCDAFF"),
            "RED_BLUE": ("#FF5959", "#BCC4FF", "#5979FF"),
            "BLUE_PURPLE": ("#5979FF", "#E1BCFF", "#C459FF"),
        }

        main_light_color, fill_light_color, back_light_color = colors.get(preset, colors["DEFAULT"])

        # 创建灯光
        # 主光
        main_light = get_obj_by_attr_value("Tri-Lighting", "MainLight")
        if not main_light:
            main_light = bpy.data.objects.new("MainLight", bpy.data.lights.new("MainLightData", type='AREA'))
            main_light.data.size = 1
            main_light.data.energy = 150
            main_light.data.volume_factor = 0
            main_light["Tri-Lighting"] = "MainLight"
            main_light.data.color = hex_to_rgb(main_light_color)
        if preset_flag:
            main_light.data.color = hex_to_rgb(main_light_color)

        # 辅光
        fill_light = get_obj_by_attr_value("Tri-Lighting", "FillLight")
        if not fill_light:
            fill_light = bpy.data.objects.new("FillLight", bpy.data.lights.new("FillLightData", type='AREA'))
            fill_light.data.size = 1
            fill_light.data.energy = 150 * 0.2
            fill_light.data.volume_factor = 0
            fill_light["Tri-Lighting"] = "FillLight"
            fill_light.data.color = hex_to_rgb(fill_light_color)
        if preset_flag:
            fill_light.data.color = hex_to_rgb(fill_light_color)

        # 背光
        back_light = get_obj_by_attr_value("Tri-Lighting", "BackLight")
        if not back_light:
            back_light = bpy.data.objects.new("BackLight", bpy.data.lights.new("BackLightData", type='AREA'))
            back_light.data.size = 1
            back_light.data.energy = 250
            back_light.data.volume_factor = 0
            back_light["Tri-Lighting"] = "BackLight"
            back_light.data.color = hex_to_rgb(back_light_color)
        if preset_flag:
            back_light.data.color = hex_to_rgb(back_light_color)

        # 主光、辅光、背光与原点的水平直线距离
        main_distance = props.main_distance
        fill_distance = props.fill_distance
        back_distance = props.back_distance
        # 主光、辅光与Y轴形成的角度
        main_position = props.main_position
        main_y_angle_rad = math.radians(30)
        fill_y_angle_rad = math.radians(60)
        if main_position == "RIGHT":
            main_factor = 1
            fill_factor = -1
        else:
            main_factor = -1
            fill_factor = 1

        # 主光、辅光、背光与Z轴形成的角度
        main_z_angle = 15
        fill_z_angle = 15
        main_z_angle_rad = math.radians(main_z_angle)
        fill_z_angle_rad = math.radians(fill_z_angle)
        back_z_angle_rad = props.back_angle

        # 主光位置旋转设置
        main_light.rotation_euler[0] = math.radians(90 - main_z_angle)
        main_light.rotation_euler[2] = main_y_angle_rad * main_factor
        main_light.location.x = main_distance * math.sin(main_y_angle_rad) * main_factor
        main_light.location.y = -main_distance * math.cos(main_y_angle_rad)
        main_light.location.z = main_distance * math.tan(main_z_angle_rad)

        # 辅光位置旋转设置
        fill_light.rotation_euler[0] = math.radians(90 - fill_z_angle)
        fill_light.rotation_euler[2] = fill_y_angle_rad * fill_factor
        fill_light.location.x = fill_distance * math.sin(fill_y_angle_rad) * fill_factor
        fill_light.location.y = -fill_distance * math.cos(fill_y_angle_rad)
        fill_light.location.z = fill_distance * math.tan(fill_z_angle_rad)

        # 背光位置旋转设置
        back_light.rotation_euler[0] = back_z_angle_rad
        back_light.location.y = - back_distance * math.sin(back_z_angle_rad)
        back_light.location.z = back_distance * math.cos(back_z_angle_rad)

        # 创建空物体
        light_root = get_obj_by_attr_value("Tri-Lighting", "LightRoot")
        if not light_root:
            light_root = bpy.data.objects.new("LightRoot", None)
            light_root["Tri-Lighting"] = "LightRoot"

        # 链接
        for obj in [main_light, fill_light, back_light, light_root]:
            try:
                light_coll.objects.link(obj)
            except RuntimeError:
                pass

        # 设置 light_root 的位置
        target_type = props.target_type
        bone_name = props.bone_name
        vg_name = props.vg_name
        if target_type == "ARMATURE":
            if active_object.type == "ARMATURE":
                armature = active_object
            else:
                ancestor = find_ancestor(active_object)
                armature = find_armature(ancestor)
            set_cons(light_root, armature, subtarget=bone_name)
        elif target_type == "MESH":
            set_cons(light_root, active_object, subtarget=vg_name)

        set_cons(main_light, light_root)
        set_cons(fill_light, light_root)
        set_cons(back_light, light_root)

        deselect_all_objects()
        select_and_activate(active_object)

    def check_props(self, props):
        active_object = bpy.context.active_object
        target_type = props.target_type
        bone_name = props.bone_name
        vg_name = props.vg_name
        if target_type == "ARMATURE":
            if not active_object:
                self.report(type={'ERROR'}, message=f'Select armature object!')
                return False
            if active_object.type == "ARMATURE":
                armature = active_object
            else:
                ancestor = find_ancestor(active_object)
                armature = find_armature(ancestor)
            if not armature:
                self.report(type={'ERROR'}, message=f'Armature not found!')
                return False
            if bone_name not in armature.pose.bones:
                self.report(type={'ERROR'}, message=f'Bone "{bone_name}" not found!')
                return False
            return True
        elif target_type == "MESH":
            if not active_object:
                self.report(type={'ERROR'}, message=f'Select mesh object!')
                return False
            if active_object.type not in ['MESH', 'LATTICE']:
                self.report(type={'ERROR'}, message=f'Select mesh object!')
                return False
            if vg_name not in active_object.vertex_groups:
                self.report(type={'ERROR'}, message=f'Vertex Groups "{vg_name}" not found!')
                return False
            return True


def find_armature(obj):
    """
    递归查找 obj 的子对象，直到找到骨架（ARMATURE）对象。
    返回第一个找到的骨架对象，如果没有找到则返回 None。
    """
    if obj.type == 'ARMATURE' and ".dummy_armature" not in obj.name:
        return obj

    for child in obj.children:
        result = find_armature(child)
        if result:
            return result

    return None


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

        blender_version = bpy.app.version
        if blender_version < (4, 2, 0):
            set_eevee()
        else:
            set_eevee_next()
        # 胶片透明
        bpy.context.scene.render.film_transparent = True
        # 取消辉光
        safe_set(bpy.context.scene.eevee, "use_bloom", False)

        # 输出属性
        # 分辨率
        bpy.context.scene.render.resolution_x = 1440
        bpy.context.scene.render.resolution_y = 1920
        # 帧率
        bpy.context.scene.render.fps = 30
        # 起始帧
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

        # 设置并切换到自定义世界环境
        set_env(self, "SUNSET")

        # 隐藏场景中所有灯光
        lights = [obj for obj in bpy.context.scene.objects if obj.type == 'LIGHT']
        for light in lights:
            set_visibility(light, (False, True, False, True))


class CameraSettingsOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.camera_settings"
    bl_label = "执行"
    bl_description = "生成相机跟随动画"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.gen_camera_animation(context)
        return {'FINISHED'}

    def gen_camera_animation(self, context):
        """
        根据指定骨骼生成相机跟随动画。
        逻辑说明：
        - 相机的Z轴位置对跟随效果较为敏感，因此将XYZ分量拆开单独处理，而不是类似限制距离约束的球体。
        - 对XY分量分别检查，如果骨骼位置的变化超过对应阈值，则更新相机的最新XY位置，Z位置需额外阈值校验。
        - 相机位置 += (当前骨骼位置 - 上一次记录的骨骼位置)
        - 可能会在不同关键帧之间产生较长连续间隙，从而导致相机缓慢移动但角色基本不动的问题，需根据最大不同帧间隔调整
        - 根据顶点组中顶点移动时，顶点如果消失（如受到焊接修改器、遮罩修改器影响），相机动画会受到影响<Vector (0.0000, 0.0000, 0.0000)>，但不会报错，需文档提示用户
        """
        props = bpy.context.scene.mmd_kafei_tools_camera_settings
        preview_props = bpy.context.scene.mmd_kafei_tools_render_preview

        if self.check_props(props) is False:
            return

        active_object = bpy.context.active_object

        # 获取跟随目标
        armature = None
        armature_copied = None
        empty = None
        target_type = props.target_type
        if target_type == "ARMATURE":
            if active_object.type == "ARMATURE":
                armature = active_object
            else:
                ancestor = find_ancestor(active_object)
                armature = find_armature(ancestor)
        else:
            empty = set_empty(props, active_object)

        # 创建跟随相机
        camera = create_follow_camera(props, preview_props)

        # 拷贝骨架并精简骨骼
        if target_type == "ARMATURE":
            bone_name = props.bone_name
            armature_copied = copy_and_prune_armature(armature, bone_name)

        # 记录当前场景
        main_scene = bpy.context.scene

        # 创建并切换到临时场景
        # 添加一个新的空场景，并拷贝当前场景的设置。可排除frame_start、frame_end、fps等设置因新场景初始化带来的影响
        scenes_before = set(bpy.data.scenes)
        bpy.ops.scene.new(type='EMPTY')
        scenes_after = set(bpy.data.scenes)
        tmp_scene = (scenes_after - scenes_before).pop()
        bpy.context.window.scene = tmp_scene
        tmp_scene.name = "TmpScene"

        # 烘焙相机动画
        if target_type == "ARMATURE":
            tmp_scene.collection.objects.link(armature_copied)
            bake_camera_animation(props, camera, armature=armature_copied)
            bpy.data.objects.remove(armature_copied, do_unlink=True)
        else:
            tmp_scene.collection.objects.link(empty)
            bake_camera_animation(props, camera, empty=empty)
            bpy.data.objects.remove(empty, do_unlink=True)

        # 恢复主场景
        bpy.context.window.scene = main_scene
        bpy.data.scenes.remove(tmp_scene)

        # 选中相机控制器 激活相机
        deselect_all_objects()
        select_and_activate(camera.parent)
        bpy.context.scene.camera = camera

    def check_props(self, props):
        active_object = bpy.context.active_object
        target_type = props.target_type
        bone_name = props.bone_name
        vg_name = props.vg_name
        if target_type == "ARMATURE":
            if not active_object:
                self.report(type={'ERROR'}, message=f'Select armature object!')
                return False
            if active_object.type == "ARMATURE":
                armature = active_object
            else:
                ancestor = find_ancestor(active_object)
                armature = find_armature(ancestor)
            if not armature:
                self.report(type={'ERROR'}, message=f'Armature not found!')
                return False
            if bone_name not in armature.pose.bones:
                self.report(type={'ERROR'},
                            message=bpy.app.translations.pgettext_iface("Bone \"{}\" not found!").format(bone_name))
                return False
            return True
        elif target_type == "MESH":
            # 获取选中网格对象
            selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
            if not selected_objects:
                self.report(type={'ERROR'}, message=f'Select mesh object!')
                return False

            # 先校验active_object是否含有指定顶点组，否则在选中对象中查找
            if active_object and active_object.type == "MESH" and vg_name in active_object.vertex_groups:
                mesh_object = active_object
            else:
                mesh_object = next((obj for obj in selected_objects if vg_name in obj.vertex_groups), None)

            if not mesh_object:
                msg = bpy.app.translations.pgettext_iface("Vertex group \"{}\" not found!").format(vg_name)
                self.report({'ERROR'}, message=msg)
                return False

            # 校验顶点组是否至少含有一个顶点
            vg_index = mesh_object.vertex_groups[vg_name].index
            has_vertex = any(v for v in mesh_object.data.vertices if vg_index in [g.group for g in v.groups])
            if not has_vertex:
                msg = bpy.app.translations.pgettext_iface("Object \"{}\" vertex group \"{}\" has no vertices!").format(
                    mesh_object.name, vg_name)
                self.report({'ERROR'}, message=msg)
                return False

            return True


def set_empty(props, active_object):
    # 获取跟随对象
    vg_name = props.vg_name
    selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    if active_object and active_object.type == "MESH" and vg_name in active_object.vertex_groups:
        mesh_object = active_object
    else:
        mesh_object = next((obj for obj in selected_objects if vg_name in obj.vertex_groups), None)

    # 获取跟随顶点
    vg_index = mesh_object.vertex_groups[vg_name].index
    vertex = next(
        (v for v in mesh_object.data.vertices if vg_index in [g.group for g in v.groups]),
        None
    )

    # 创建空物体子级
    empty = bpy.data.objects.new("TmpEmpty", None)
    bpy.context.scene.collection.objects.link(empty)
    empty.parent = mesh_object
    empty.parent_type = 'VERTEX'
    empty.parent_vertices[0] = vertex.index
    return empty


def bake_camera_animation(props, camera, armature=None, empty=None):
    bone_name = props.bone_name
    threshold_x = props.threshold_x
    threshold_y = props.threshold_y
    threshold_z = props.threshold_z
    max_gap = props.max_gap
    savepoint_x = None
    savepoint_y = None
    savepoint_z = None
    # 获取帧范围
    target_type = props.target_type
    if target_type == "ARMATURE":
        frame_start, frame_end = get_armature_keyframe_range(armature)
    else:
        frame_start, frame_end = bpy.context.scene.frame_start, bpy.context.scene.frame_end

    depsgraph = bpy.context.evaluated_depsgraph_get()
    for frame in range(frame_start, frame_end):
        bpy.context.scene.frame_set(frame)

        if target_type == "ARMATURE":
            # 获取指定骨骼实际全局位置
            eval_arm = armature.evaluated_get(depsgraph)
            eval_bone = eval_arm.pose.bones[bone_name]
            global_mat = eval_arm.matrix_world @ eval_bone.matrix
            lo_x, lo_y, lo_z = global_mat.to_translation()

        else:
            # 获取空物体实际全局位置
            eval_obj = empty.evaluated_get(depsgraph)
            lo = eval_obj.matrix_world.translation
            lo_x, lo_y, lo_z = lo.x, lo.y, lo.z

        # 第一帧作为参考帧
        if savepoint_x is None and savepoint_y is None and savepoint_z is None:
            savepoint_x, savepoint_y, savepoint_z = lo_x, lo_y, lo_z
            continue

        # 第二帧起计算差值
        delta_x = lo_x - savepoint_x
        delta_y = lo_y - savepoint_y
        delta_z = lo_z - savepoint_z

        if abs(delta_x) <= threshold_x and abs(delta_y) <= threshold_y and abs(delta_z) <= threshold_z:
            continue

        camera.location[0] += delta_x
        camera.location[1] += delta_y
        if abs(delta_z) > threshold_z:
            camera.location[2] += delta_z

        # 插入关键帧
        camera.keyframe_insert(data_path="location", frame=frame)

        # 更新参考点
        savepoint_x, savepoint_y, savepoint_z = lo_x, lo_y, lo_z

    # 根据 最大不同帧间隔 设置关键帧
    action = camera.animation_data.action if camera.animation_data else None
    fcurves = [fc for fc in action.fcurves if fc.data_path == "location"]

    # fc.array_index X/Y/Z 三个通道索引
    # kp.co.x 帧号
    # kp.co.y 关键帧的数值
    keyframes = {}
    for fc in fcurves:
        keyframes[fc.array_index] = [(kp.co.x, kp.co.y) for kp in fc.keyframe_points]

    # 遍历 X/Y/Z 三个通道的关键帧列表
    all_frame_numbers = []
    for klist in keyframes.values():
        # 遍历该通道里的每个关键帧 (frame, value)
        for k in klist:
            frame_number = k[0]  # 取出帧号
            all_frame_numbers.append(frame_number)
    # 去重并排序
    frames = sorted(set(all_frame_numbers))

    for i in range(len(frames) - 1):
        f1, f2 = int(frames[i]), int(frames[i + 1])
        gap = f2 - f1
        if gap <= max_gap:
            continue

        # 获取帧上的 location 值
        loc1 = Vector((
            fcurves[0].evaluate(f1),
            fcurves[1].evaluate(f1),
            fcurves[2].evaluate(f1),
        ))
        loc2 = Vector((
            fcurves[0].evaluate(f2),
            fcurves[1].evaluate(f2),
            fcurves[2].evaluate(f2),
        ))

        # 差值判断
        if (loc2 - loc1).length < PRECISION:
            continue

        # 目标插入帧
        insert_frame = f2 - max_gap
        # 插入 loc1
        camera.location = loc1
        camera.keyframe_insert(data_path="location", frame=insert_frame)

    bpy.context.scene.frame_set(0)


def copy_and_prune_armature(armature, bone_name):
    armature_copied = copy_obj(armature)
    armature_copied.parent = None
    deselect_all_objects()
    select_and_activate(armature_copied)
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature_copied.data.edit_bones
    # 获取指定骨骼及其父骨骼链
    keep_bones = set()
    bone = edit_bones.get(bone_name)
    while bone:
        keep_bones.add(bone.name)
        bone = bone.parent
    # 遍历所有骨骼，删除不在 keep_bones 中的骨骼
    for bone in list(edit_bones):
        if bone.name not in keep_bones:
            edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode='OBJECT')
    return armature_copied


def create_follow_camera(props, preview_props):
    # 生成相机及所在集合
    camera_name = bpy.app.translations.pgettext_iface("跟随相机")
    camera_data = bpy.data.cameras.new(name=camera_name)
    camera = bpy.data.objects.new(name=camera_name, object_data=camera_data)
    collection_name = bpy.app.translations.pgettext_iface("相机")
    collection = get_collection(collection_name)
    collection.objects.link(camera)

    # 创建相机父级并缩放，以便控制及观察
    empty = bpy.data.objects.new(bpy.app.translations.pgettext_iface("相机控制器"), None)
    empty.scale = [0.1, 0.1, 0.1]
    collection.objects.link(empty)
    active_object = bpy.context.active_object
    selected_objects = bpy.context.selected_objects
    deselect_all_objects()
    select_and_activate(empty)
    bpy.ops.object.transform_apply(scale=True)
    restore_selection(selected_objects, active_object)
    camera.parent = empty
    camera.matrix_parent_inverse = empty.matrix_world.inverted()

    # 设置相机初始位置
    bpy.context.scene.frame_set(0)
    preview_props.scale = 1
    preview_props.rotation_euler_x = props.rotation_euler_x
    preview_props.rotation_euler_y = math.radians(0)
    preview_props.rotation_euler_z = math.radians(0)
    preview_props.align = True
    preview_props.type = 'PERSPECTIVE'
    camera_to_view_selected(preview_props, camera)
    camera.keyframe_insert(data_path="location", frame=0)
    return camera


def get_armature_keyframe_range(armature):
    """ 获取指定 Armature 对象的关键帧范围 """
    if armature.animation_data is None:
        return None, None

    action = armature.animation_data.action
    if action is None:
        return None, None

    # 用于存储所有关键帧帧号
    keyframe_numbers = []

    for fcurve in action.fcurves:
        for keyframe_point in fcurve.keyframe_points:
            frame_number = keyframe_point.co.x  # co.x 帧号
            keyframe_numbers.append(frame_number)

    # 如果找到了关键帧
    if keyframe_numbers:
        min_frame = int(min(keyframe_numbers))
        max_frame = int(max(keyframe_numbers))
        return min_frame, max_frame

    return None, None
