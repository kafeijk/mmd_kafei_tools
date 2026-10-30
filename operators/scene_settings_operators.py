import math
import os

import bpy

from mathutils import Vector

from ..constants import BACK_LIGHT_ENERGY, FILL_LIGHT_ENERGY, KEY_LIGHT_ENERGY, PRECISION, RESOLUTION_PRESETS

from .render_preview_operators import do_camera_to_view_selected, switch_to_camera_view
from ..utils import (
    copy_obj,
    deselect_all_objects,
    find_ancestor,
    get_action_fcurves,
    get_collection,
    hex_to_rgb,
    restore_selection,
    safe_set,
    select_and_activate,
    set_visibility,
    translate,
    unlink,
    view3d_context,
)


# EEVEE 的实现分支与引擎标识随版本变化，集中在此维护
# 4.2 起为 EEVEE Next；5.0 起引擎标识又改回 BLENDER_EEVEE
# https://developer.blender.org/docs/release_notes/5.0/python_api/#render
IS_EEVEE_NEXT = bpy.app.version >= (4, 2, 0)
EEVEE_ENGINE = 'BLENDER_EEVEE_NEXT' if (4, 2, 0) <= bpy.app.version < (5, 0, 0) else 'BLENDER_EEVEE'

# 版本阈值
IS_4_0_OR_NEWER = bpy.app.version >= (4, 0, 0)
IS_5_0_OR_NEWER = bpy.app.version >= (5, 0, 0)


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
        # 设置渲染参数。
        if engine == "EEVEE":
            if IS_EEVEE_NEXT:
                set_eevee_next(context)
            else:
                set_eevee(context)
        elif engine == "CYCLES":
            set_cycles(context)

        # 色彩管理 - 查看变换
        if bpy.context.scene.display_settings.display_device == 'sRGB':
            bpy.context.scene.view_settings.view_transform = 'Filmic'

        # 着色方式 - 渲染
        with bpy.context.temp_override(**view3d_context()):
            try:
                bpy.context.space_data.shading.type = 'RENDERED'
            except (AttributeError, TypeError):
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
        warning = set_env(context, world_name, 1)
        if warning is not None:
            self.report(type={'WARNING'}, message=warning)


def has_link(links, from_socket, to_socket):
    """判断节点连接是否存在"""
    return any(link.from_socket == from_socket and link.to_socket == to_socket for link in links)


def is_default_world(world):
    """世界是否为"黑背景、无光照贡献"的目标结构"""
    if world.node_tree is None:
        return False
    nodes = world.node_tree.nodes
    background = next((n for n in nodes if n.bl_idname == "ShaderNodeBackground"), None)
    output = next((n for n in nodes if n.bl_idname == "ShaderNodeOutputWorld"), None)
    if background is None or output is None or len(nodes) != 2:
        return False
    if tuple(background.inputs['Color'].default_value) != (0.0, 0.0, 0.0, 1.0):
        return False
    if background.inputs['Strength'].default_value != 0:
        return False
    return has_link(world.node_tree.links, background.outputs['Background'], output.inputs['Surface'])


def is_env_world(world, env_texture_path, strength):
    """世界是否为指定天空球的目标结构"""
    if world.node_tree is None:
        return False
    nodes = world.node_tree.nodes
    node_types = ("ShaderNodeTexCoord", "ShaderNodeMapping", "ShaderNodeTexEnvironment",
                  "ShaderNodeBackground", "ShaderNodeOutputWorld")
    if len(nodes) != len(node_types):
        return False
    node_map = {n.bl_idname: n for n in nodes}
    if any(node_type not in node_map for node_type in node_types):
        return False
    tex_coord = node_map["ShaderNodeTexCoord"]
    mapping = node_map["ShaderNodeMapping"]
    env_tex = node_map["ShaderNodeTexEnvironment"]
    background = node_map["ShaderNodeBackground"]
    output = node_map["ShaderNodeOutputWorld"]
    expected_links = (
        (tex_coord.outputs['Generated'], mapping.inputs['Vector']),
        (mapping.outputs['Vector'], env_tex.inputs['Vector']),
        (env_tex.outputs['Color'], background.inputs['Color']),
        (background.outputs['Background'], output.inputs['Surface']),
    )
    links = world.node_tree.links
    if not all(has_link(links, from_socket, to_socket) for from_socket, to_socket in expected_links):
        return False
    if background.inputs['Strength'].default_value != strength:
        return False
    # 未指定贴图属于异常结构，不视为可复用
    if env_tex.image is None:
        return False
    return os.path.abspath(bpy.path.abspath(env_tex.image.filepath)) == os.path.abspath(env_texture_path)


def find_matching_world(world_name, match_func):
    """查找同名（含 .001 等后缀）且结构一致的世界"""
    for world in bpy.data.worlds:
        if world.name == world_name or world.name.startswith(f"{world_name}."):
            if match_func(world):
                return world
    return None


def set_env(context, world_name, strength):
    """设置世界环境，返回需要提示的信息（None 表示无需提示）"""
    scene = context.scene
    is_default = world_name == "DEFAULT"
    world_display_name = "World" if is_default else world_name.capitalize()

    if is_default:
        env_texture_path = ""
    else:
        # 环境纹理目录：LOCAL 资源路径 + 官方数据目录（resource_path 结果可能不存在，但不会返回None）
        # https://docs.blender.org/api/current/bpy.utils.html#bpy.utils.resource_path
        env_folder = os.path.join(bpy.utils.resource_path('LOCAL'), 'datafiles', 'studiolights', 'world')
        # Blender 自带的 HDRI 文件名为全小写
        env_file_name = f'{world_name.lower()}.exr'
        env_texture_path = os.path.join(env_folder, env_file_name)

    # 已有结构一致的同名世界时直接复用，否则新建
    match_func = is_default_world if is_default else (lambda w: is_env_world(w, env_texture_path, strength))
    world = find_matching_world(world_display_name, match_func)
    if world is not None:
        scene.world = world
        return

    # 新建世界：名称与节点开关为公共步骤，节点处理按类型分叉
    world = bpy.data.worlds.new(world_display_name)
    if not IS_5_0_OR_NEWER:  # Blender 5.0之后，use_nodes始终为True，之后将会被移除
        world.use_nodes = True
    world_nodes = world.node_tree

    if is_default:
        # 黑背景、无光照贡献
        for node in world_nodes.nodes:
            if node.bl_idname == "ShaderNodeBackground":
                node.inputs[0].default_value = (0, 0, 0, 1)
                node.inputs[1].default_value = 0
        # 设置世界环境
        scene.world = world
        return

    # 天空球：清空默认节点后重建
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

    warning = None
    if not os.path.exists(env_texture_path):
        warning = bpy.app.translations.pgettext_iface(
            "HDRI Map not found. Add manually. Path: {}").format(env_texture_path)
    else:
        image = bpy.data.images.load(env_texture_path, check_existing=True)
        env_tex_node.image = image

        if scene.display_settings.display_device == 'ACES':
            safe_set(image.colorspace_settings, "name", 'Utility - Linear - sRGB')
        else:
            if not IS_4_0_OR_NEWER:
                safe_set(image.colorspace_settings, "name", "Linear")  # 2.x 3.x 默认
            else:
                safe_set(image.colorspace_settings, "name", "Linear Rec.709")  # 4.x 默认

    # 依次按顺序相连接
    world_nodes.links.new(tex_coord_node.outputs['Generated'], mapping_node.inputs['Vector'])
    world_nodes.links.new(mapping_node.outputs['Vector'], env_tex_node.inputs['Vector'])
    world_nodes.links.new(env_tex_node.outputs['Color'], background_node.inputs['Color'])
    world_nodes.links.new(background_node.outputs['Background'], world_output_node.inputs['Surface'])
    # 设置背景强度
    background_node.inputs['Strength'].default_value = strength
    # 设置世界环境
    scene.world = world
    return warning


def reset(struct):
    """恢复指定结构体默认设置"""
    # setattr(bpy.context.scene.eevee, "use_taa_reprojection", True)
    for prop in struct.bl_rna.properties:
        if prop.identifier == "rna_type":
            continue
        try:
            val = getattr(struct, prop.identifier)
        except (AttributeError, ReferenceError):
            # 属性不可读或数据块已失效
            continue

        if isinstance(val, bpy.types.bpy_struct):
            reset(val)
        else:
            try:
                setattr(struct, prop.identifier, prop.default)
            except Exception:
                pass


def set_eevee(context):
    scene = context.scene
    # 预设目的：快速渲染视频。非图像渲染，非渲染高质量视频
    # 渲染引擎 - Eevee
    safe_set(scene.render, "engine", EEVEE_ENGINE)
    # 恢复 Eevee 默认设置
    reset(scene.eevee)

    # 环境光遮蔽
    safe_set(scene.eevee, "use_gtao", True)
    # 辉光
    safe_set(scene.eevee, "use_bloom", True)

    # 屏幕空间反射
    safe_set(scene.eevee, "use_ssr", True)
    # 折射
    safe_set(scene.eevee, "use_ssr_refraction", True)
    # 半精度追踪
    safe_set(scene.eevee, "use_ssr_halfres", False)

    # 运动模糊
    safe_set(scene.eevee, "use_motion_blur", False)

    # 阴影
    # 矩形尺寸
    safe_set(scene.eevee, "shadow_cube_size", '1024')
    # 级联大小
    safe_set(scene.eevee, "shadow_cascade_size", '1024')
    # 高位深
    safe_set(scene.eevee, "use_shadow_high_bitdepth", True)
    # 柔和阴影
    safe_set(scene.eevee, "use_soft_shadows", True)


def set_eevee_next(context):
    scene = context.scene
    # 渲染引擎 - Eevee
    safe_set(scene.render, "engine", EEVEE_ENGINE)
    # 恢复 Eevee 默认设置
    reset(scene.eevee)

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


def set_cycles(context):
    scene = context.scene
    cycles = scene.cycles
    render = scene.render

    # cuda快还是optix快？ optix更快些，但是，如果没有optix或在条件影响下cuda更快，则选择cuda
    # 参考链接：https://irendering.net/is-cuda-or-optix-faster-in-blender-cycles/

    # 渲染设备选自己的GPU。 不要选CPU；不要二者都选

    # 渲染引擎 - Cycles
    scene.render.engine = 'CYCLES'
    # 恢复 Cycles 默认设置
    reset(scene.cycles)

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

        preset = RESOLUTION_PRESETS.get(output.resolution)
        if preset is None:
            self.report(type={'ERROR'}, message=bpy.app.translations.pgettext_iface(
                "Unknown resolution preset: {}").format(output.resolution))
            return {'CANCELLED'}

        _, width, height = preset
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
    bl_description = "设置三点照明"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.gen_light(context)
        return {'FINISHED'}

    # ------------------------------------------------------------------ #
    #  内部工具方法
    # ------------------------------------------------------------------ #
    def _get_or_create_light(self, old_name: str, attr_value: str, energy: float, color_hex: str,
                             new_name: str, preset_flag: bool) -> bpy.types.Object:
        """
        查找已有灯光（兼容旧名和新名），不存在则新建。
        preset_flag=True 时强制应用颜色预设。
        Tri-Lighting 名称取自 https://docs.blender.org/manual/nb/3.6/addons/lighting/trilighting.html
        """
        obj = get_obj_by_attr_value("Tri-Lighting", attr_value)
        if not obj:
            obj = get_obj_by_attr_value("Tri-Lighting", old_name)  # 兼容旧属性写法

        if not obj:
            light_data = bpy.data.lights.new(f"{attr_value}Data", type='AREA')
            light_data.size = 1
            light_data.energy = energy
            light_data.volume_factor = 0
            light_data.color = hex_to_rgb(color_hex)
            obj = bpy.data.objects.new(new_name, light_data)
            obj["Tri-Lighting"] = attr_value

        # 兼容旧属性
        if obj.name == old_name:
            obj["Tri-Lighting"] = attr_value
        # 兼容旧命名
        obj.name = new_name

        if preset_flag:
            obj.data.color = hex_to_rgb(color_hex)

        return obj

    # ------------------------------------------------------------------ #
    #  位置 / 旋转计算
    # ------------------------------------------------------------------ #
    def _apply_transforms(self, lights: list, props) -> None:
        key_light, fill_light, back_light = lights

        key_y = math.radians(30)
        fill_y = math.radians(60)
        z_angle = math.radians(15)

        key_factor = 1 if props.key_position == "RIGHT" else -1
        fill_factor = -key_factor

        d_key = props.key_distance
        d_fill = props.fill_distance
        d_back = props.back_distance
        back_z = props.back_angle

        # 主光
        key_light.rotation_euler = (math.radians(75), 0, key_y * key_factor)
        key_light.location = (
            d_key * math.sin(key_y) * key_factor,
            -d_key * math.cos(key_y),
            d_key * math.tan(z_angle),
        )

        # 辅光
        fill_light.rotation_euler = (math.radians(75), 0, fill_y * fill_factor)
        fill_light.location = (
            d_fill * math.sin(fill_y) * fill_factor,
            -d_fill * math.cos(fill_y),
            d_fill * math.tan(z_angle),
        )

        # 背光
        back_light.rotation_euler = (back_z, 0, 0)
        back_light.location = (
            0,
            -d_back * math.sin(back_z),
            d_back * math.cos(back_z),
        )

    # ------------------------------------------------------------------ #
    #  主流程
    # ------------------------------------------------------------------ #
    def gen_light(self, context) -> None:
        scene = context.scene
        props = scene.mmd_kafei_tools_light_settings
        active_obj = context.active_object

        if not self.check_props(props):
            return

        new_light_names = ["主光", "辅光", "背光"]
        # 灯光预设配置
        light_presets = {
            "DEFAULT": ("#FFD1BC", "#DAEAFF", "#BCDAFF"),
            "RED_BLUE": ("#FF5959", "#BCC4FF", "#5979FF"),
            "BLUE_PURPLE": ("#5979FF", "#E1BCFF", "#C459FF"),
        }
        # 灯光定义：(旧名, 属性值, 能量, 位置索引)
        light_defs = [
            ("MainLight", "KeyLight", KEY_LIGHT_ENERGY, 0),
            ("FillLight", "FillLight", FILL_LIGHT_ENERGY, 1),
            ("BackLight", "BackLight", BACK_LIGHT_ENERGY, 2),
        ]

        # ---------- 集合 ----------
        new_coll_name = translate("灯光")
        light_coll = get_collection(new_coll_name)

        # ---------- 灯光颜色 ----------
        colors = light_presets.get(props.preset, light_presets["DEFAULT"])

        # ---------- 创建/获取三盏灯 ----------
        lights = [
            self._get_or_create_light(
                old_name=old,
                attr_value=attr,
                energy=energy,
                color_hex=colors[i],
                new_name=translate(new_light_names[i]),
                preset_flag=props.preset_flag,
            )
            for i, (old, attr, energy, _) in enumerate(light_defs)
        ]

        # ---------- 位置旋转 ----------
        self._apply_transforms(lights, props)

        # ---------- 灯光控制器 ----------
        new_root_name = translate("灯光控制器")
        light_root = get_obj_by_attr_value("Tri-Lighting", "LightRoot")
        if not light_root:
            light_root = bpy.data.objects.new(new_root_name, None)
            light_root["Tri-Lighting"] = "LightRoot"
        # 兼容旧命名
        light_root.name = new_root_name

        # ---------- 链接到集合 ----------
        for obj in (*lights, light_root):
            # 从原集合中移除
            uc_set = set()
            if obj.users_collection:
                for uc in obj.users_collection:
                    uc.objects.unlink(obj)
                    uc_set.add(uc)
                for uc in uc_set:
                    if uc == light_coll:
                        continue
                    if uc.objects:
                        continue
                    unlink(uc)

            # 链接到新集合
            if obj.name in light_coll.objects:
                continue
            light_coll.objects.link(obj)

        # ---------- 约束设置 ----------
        target_type = props.target_type
        if target_type == "ARMATURE":
            armature = (active_obj if active_obj.type == "ARMATURE"
                        else find_armature(find_ancestor(active_obj)))
            set_cons(light_root, armature, subtarget=props.bone_name)
        elif target_type == "MESH":
            set_cons(light_root, active_obj, subtarget=props.vg_name)

        for light in lights:
            set_cons(light, light_root)

        deselect_all_objects()
        select_and_activate(active_obj)

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
            if not active_object:
                self.report(type={'ERROR'}, message=f'Select mesh object!')
                return False
            if active_object.type not in ['MESH', 'LATTICE']:
                self.report(type={'ERROR'}, message=f'Select mesh object!')
                return False
            if vg_name not in active_object.vertex_groups:
                msg = bpy.app.translations.pgettext_iface("Vertex group \"{}\" not found!").format(vg_name)
                self.report({'ERROR'}, message=msg)
                return False
            # 校验顶点组是否至少含有一个顶点
            vg_index = active_object.vertex_groups[vg_name].index
            has_vertex = any(v for v in active_object.data.vertices if vg_index in [g.group for g in v.groups])
            if not has_vertex:
                msg = bpy.app.translations.pgettext_iface("Object \"{}\" vertex group \"{}\" has no vertices!").format(
                    active_object.name, vg_name)
                self.report({'ERROR'}, message=msg)
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

        if IS_EEVEE_NEXT:
            set_eevee_next(context)
            safe_set(scene.eevee, "use_raytracing", False)  # 取消光追，只需要光照即可，避免颜色对模型的影响
        else:
            set_eevee(context)
            # 取消辉光
            safe_set(scene.eevee, "use_bloom", False)

        # 胶片透明
        bpy.context.scene.render.film_transparent = True

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
        # 查看变换
        if bpy.context.scene.display_settings.display_device == 'sRGB':
            bpy.context.scene.view_settings.view_transform = 'Filmic'
        # 视口设置（叠加层/着色方式/X 光）
        with bpy.context.temp_override(**view3d_context()):
            # 显示叠加层
            bpy.context.space_data.overlay.show_overlays = False
            # 着色方式 渲染
            bpy.context.space_data.shading.type = 'RENDERED'
            # 关闭透视模式 https://blender.stackexchange.com/questions/159525/how-to-toggle-xray-in-viewport-with-python
            views3d = [area for area in bpy.context.screen.areas if area.type == 'VIEW_3D']
            for area in views3d:
                shading = area.spaces.active.shading
                shading.show_xray = False
                shading.show_xray_wireframe = False

        # 设置并切换到自定义世界环境
        warning = set_env(context, "SUNSET", 2)
        if warning is not None:
            self.report(type={'WARNING'}, message=warning)
        if IS_EEVEE_NEXT:
            world = scene.world
            world_nodes = world.node_tree
            for node in world_nodes.nodes:
                if node.bl_idname == "ShaderNodeMapping":
                    node.inputs[2].default_value[2] = math.radians(30)

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
        camera = create_follow_camera(props)

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
        # 切换到相机视图
        with bpy.context.temp_override(**view3d_context()):
            switch_to_camera_view()

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
            frame_start, frame_end = get_armature_keyframe_range(armature)
            if not frame_start and not frame_end:
                self.report(type={'ERROR'}, message=f'Armature has no keyframes!')
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
    for frame in range(frame_start, frame_end + 1):
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
            camera.location[2] += delta_z / 2  # 假设角色高度为1，相机视野高为1。若角色蹲下使高为0.5，则为了使角色处于中心，相机应下降0.25

        # 插入关键帧
        camera.keyframe_insert(data_path="location", frame=frame)

        # 更新参考点
        savepoint_x, savepoint_y = lo_x, lo_y

        if abs(delta_z) > threshold_z:
            savepoint_z = lo_z
    # 根据 最大不同帧间隔 设置关键帧
    fcurves = get_action_fcurves(camera)
    fcurves = [fc for fc in fcurves if fc.data_path == "location"]

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


def create_follow_camera(props):
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

    do_camera_to_view_selected('PERSPECTIVE', True,
                               props.rotation_euler_x, math.radians(0), math.radians(0),
                               1, camera=camera)
    camera.keyframe_insert(data_path="location", frame=0)
    return camera


def get_armature_keyframe_range(armature):
    """ 获取指定 Armature 对象的关键帧范围 """
    fcurves = get_action_fcurves(armature)
    if fcurves is None:
        return None, None

    # 用于存储所有关键帧帧号
    keyframe_numbers = []

    for fcurve in fcurves:
        for keyframe_point in fcurve.keyframe_points:
            frame_number = keyframe_point.co.x  # co.x 帧号
            keyframe_numbers.append(frame_number)

    # 如果找到了关键帧
    if keyframe_numbers:
        min_frame = int(min(keyframe_numbers))
        max_frame = int(max(keyframe_numbers))
        return min_frame, max_frame

    return None, None
