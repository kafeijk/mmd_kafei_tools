import bpy

from ..utils import *
from ..mmd_utils import *


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
            env_folder = self.get_folder(blender_install_dir, "world")
            env_texture_path = os.path.join(env_folder, f'{world_name}.exr')

            if not os.path.exists(env_texture_path):
                self.report(type={'WARNING'}, message=bpy.app.translations.pgettext_iface(
                    "HDRI Map not found. Add manually. Path: {}").format(env_texture_path))
            else:
                image = bpy.data.images.load(env_texture_path, check_existing=True)
                env_tex_node.image = image

                if bpy.context.scene.display_settings.display_device == 'ACES':
                    image.colorspace_settings.name = 'Utility - Linear - sRGB'
                else:
                    image.colorspace_settings.name = 'sRGB'

            # 依次按顺序相连接
            world_nodes.links.new(tex_coord_node.outputs['Generated'], mapping_node.inputs['Vector'])
            world_nodes.links.new(mapping_node.outputs['Vector'], env_tex_node.inputs['Vector'])
            world_nodes.links.new(env_tex_node.outputs['Color'], background_node.inputs['Color'])
            world_nodes.links.new(background_node.outputs['Background'], world_output_node.inputs['Surface'])
            # 设置背景强度
            background_node.inputs['Strength'].default_value = 1
            # 设置世界环境
            bpy.context.scene.world = world

    def get_folder(self, blender_install_dir, folder_name):
        for root, dirs, files in os.walk(blender_install_dir):
            for dir_name in dirs:
                if folder_name in dir_name:
                    return os.path.join(root, dir_name)


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
    safe_set(scene.eevee.ray_tracing_options, "denoise_temporal", False)
    safe_set(scene.eevee.ray_tracing_options, "denoise_bilateral", False)

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
    obj.constraints.new('CHILD_OF')

    # 只考虑位置
    bpy.context.object.constraints["Child Of"].use_rotation_x = False
    bpy.context.object.constraints["Child Of"].use_rotation_y = False
    bpy.context.object.constraints["Child Of"].use_rotation_z = False
    bpy.context.object.constraints["Child Of"].use_scale_x = False
    bpy.context.object.constraints["Child Of"].use_scale_y = False
    bpy.context.object.constraints["Child Of"].use_scale_z = False

    # 目标设置
    obj.constraints["Child Of"].target = target
    if subtarget:
        obj.constraints["Child Of"].subtarget = subtarget

    bpy.ops.constraint.childof_clear_inverse(constraint="Child Of", owner='OBJECT')

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

        # 校验是否选中MMD模型
        if self.check_props(props) is False:
            return
        active_object = bpy.context.active_object

        light_coll = get_collection("3 Points Lighting")

        # 创建灯光
        # 主光
        main_light = get_obj_by_attr_value("Tri-Lighting", "MainLight")
        if not main_light:
            main_light = bpy.data.objects.new("MainLight", bpy.data.lights.new("MainLightData", type='AREA'))
            main_light.data.size = 1
            main_light.data.energy = 150
            main_light.data.color = hex_to_rgb("#FFDACA")
            main_light.data.volume_factor = 0
            main_light["Tri-Lighting"] = "MainLight"

        # 辅光
        fill_light = get_obj_by_attr_value("Tri-Lighting", "FillLight")
        if not fill_light:
            fill_light = bpy.data.objects.new("FillLight", bpy.data.lights.new("FillLightData", type='AREA'))
            fill_light.data.size = 1
            fill_light.data.energy = 150 * 0.2
            fill_light.data.color = hex_to_rgb("#76C2FF")
            fill_light.data.volume_factor = 0
            fill_light["Tri-Lighting"] = "FillLight"

        # 背光
        back_light = get_obj_by_attr_value("Tri-Lighting", "BackLight")
        if not back_light:
            back_light = bpy.data.objects.new("BackLight", bpy.data.lights.new("BackLightData", type='AREA'))
            back_light.data.size = 1
            back_light.data.energy = 250
            back_light.data.color = hex_to_rgb("#00D9FF")
            back_light.data.volume_factor = 0
            back_light["Tri-Lighting"] = "BackLight"

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
    if obj.type == 'ARMATURE':
        return obj

    for child in obj.children:
        result = find_armature(child)
        if result:
            return result

    return None
