import math
import os

import bpy

from mathutils import Vector

from ..constants import (CAMERA_Z_FACTOR, FILL_LIGHT_ANGLE,
                         KEY_LIGHT_ANGLE, LIGHT_COLOR_PRESETS, LIGHT_CONTROLLER_ATTR,
                         LIGHT_EXCLUDE_COLLECTION, LIGHT_HEIGHT_ANGLE, LIGHT_MARKER, LIGHT_ROLES,
                         LIGHT_ROOT_PROPERTY, LIGHT_ROTATION_X, LIGHT_SIZE, PRECISION)

from ..properties.scene_settings_properties import (apply_resolution_preset, get_light_groups,
                                                    is_complete_light_group)

from .render_preview_operators import do_camera_to_view_selected, switch_to_camera_view
from ..utils import (
    center_view_camera,
    copy_obj,
    deselect_all_objects,
    find_ancestor,
    find_pmx_root_with_child,
    find_rigid_body_parent,
    get_action_fcurves,
    get_collection,
    get_fcurve_frames,
    hex_to_rgb,
    is_mmd_tools_enabled,
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
    bl_description = "按预设应用渲染分辨率"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        scene = context.scene
        output = scene.mmd_kafei_tools_output_settings

        if not apply_resolution_preset(scene, output.resolution):
            self.report(type={'ERROR'}, message=bpy.app.translations.pgettext_iface(
                "Unknown resolution preset: {}").format(output.resolution))
            return {'CANCELLED'}

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

        # 像素比一并交换，保证显示宽高比与画幅翻转一致（1:1 时无影响）
        rd.pixel_aspect_x, rd.pixel_aspect_y = rd.pixel_aspect_y, rd.pixel_aspect_x

        # 相机视角下重新对准相机
        center_view_camera()

        return {'FINISHED'}


class ResetLightSettingsOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.reset_light_settings"
    bl_label = "重置"
    bl_description = "将灯光设置中可实时调整的参数重置为默认值"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.mmd_kafei_tools_light_settings
        for name in ("key_position", "preset", "exposure",
                     "key_energy", "fill_energy", "back_energy",
                     "key_distance", "fill_distance", "back_distance", "back_angle"):
            rna_prop = props.bl_rna.properties[name]
            setattr(props, name, rna_prop.default)
        return {'FINISHED'}


def set_cons(obj, target, subtarget=None):
    """设置子级约束"""
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

    # 用 Blender 自带的「清除反向」
    bpy.context.view_layer.update()
    with bpy.context.temp_override(object=obj, active_object=obj,
                                   selected_objects=[obj], selected_editable_objects=[obj]):
        bpy.ops.constraint.childof_clear_inverse(constraint=cons.name, owner='OBJECT')


def get_light_controllers():
    """按记录的 root 名称来获取灯光控制器，每个 root 只有一个控制器"""
    controllers = {}
    for obj in bpy.data.objects:
        if obj.get(LIGHT_MARKER) == LIGHT_CONTROLLER_ATTR:
            controllers.setdefault(obj.get(LIGHT_ROOT_PROPERTY), obj)
    return controllers


def remove_light_exclude_collection(root_name):
    """删除该 root 对应的灯光链接排除集合"""
    collection = bpy.data.collections.get(f"{translate(LIGHT_EXCLUDE_COLLECTION)}_{root_name}")
    if collection is None:
        return
    for obj in list(collection.objects):
        collection.objects.unlink(obj)
    unlink(collection)
    bpy.data.collections.remove(collection)


def remove_light_group(group, controller=None, root_name=None):
    """删除一组插件生成的灯光及其控制器"""
    for obj in group.values():
        light = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if light is not None and light.users == 0:
            bpy.data.lights.remove(light)
    if controller is not None:
        bpy.data.objects.remove(controller, do_unlink=True)
    if root_name is not None:
        remove_light_exclude_collection(root_name)


def is_rigid_body_object(obj, rigid_body_parents):
    """对象是否位于 MMD 刚体分组下"""
    ancestor = obj
    while ancestor is not None:
        if ancestor in rigid_body_parents:
            return True
        ancestor = ancestor.parent
    return False


def get_root_meshes(root_names):
    """收集指定 root 下的网格，以及指向这些 root 骨架的修改器持有者"""
    scene_objects = list(bpy.context.scene.objects)
    # 缓存每个对象的最外层祖先，避免重复向上遍历
    object_root_names = {obj: find_ancestor(obj).name for obj in scene_objects}

    # 每个 pmx root 只查找一次刚体分组，避免逐对象反复扫描子级
    rigid_body_parents = set()
    if is_mmd_tools_enabled():
        pmx_roots = {find_pmx_root_with_child(obj) for obj in scene_objects} - {None}
        for pmx_root in pmx_roots:
            rigid_body_parent = find_rigid_body_parent(pmx_root)
            if rigid_body_parent is not None:
                rigid_body_parents.add(rigid_body_parent)

    objects = []
    for obj in scene_objects:
        # 不收集刚体
        if is_rigid_body_object(obj, rigid_body_parents):
            continue
        if obj.type == 'MESH' and object_root_names[obj] in root_names:
            objects.append(obj)
            continue
        # 如果骨架修改器关联的骨架的root，在root_names中，则也会被收集
        for modifier in obj.modifiers:
            if modifier.type != 'ARMATURE':
                continue
            armature = modifier.object
            if armature is None:
                continue
            armature_root_name = (object_root_names.get(armature)
                                  or find_ancestor(armature).name)
            if armature_root_name in root_names:
                objects.append(obj)
                break
    return objects


def supports_light_linking(light):
    """当前 Blender 版本是否支持灯光链接与阴影链接"""
    linking = getattr(light, "light_linking", None)
    return (linking is not None
            and hasattr(linking, "receiver_collection")
            and hasattr(linking, "blocker_collection"))


def apply_light_linking(lights, root_name, other_root_names):
    """
    把其它 root 下的网格加入灯光链接与阴影链接并排除
    light_linking 在概念上同时涵盖灯光链接与阴影链接
    """
    if not all(supports_light_linking(light) for light in lights):
        return

    collection_name = f"{translate(LIGHT_EXCLUDE_COLLECTION)}_{root_name}"
    collection = bpy.data.collections.get(collection_name)
    meshes = get_root_meshes(other_root_names)

    if not meshes:
        for light in lights:
            light.light_linking.receiver_collection = None
            light.light_linking.blocker_collection = None
        if collection is not None:
            for obj in list(collection.objects):
                collection.objects.unlink(obj)
            unlink(collection)
            bpy.data.collections.remove(collection)
        return

    if collection is None:
        # 仅作为灯光链接的接收集合使用，不链接到大纲中，避免污染场景层级
        collection = bpy.data.collections.new(collection_name)
    else:
        for obj in list(collection.objects):
            collection.objects.unlink(obj)
    for obj in meshes:
        collection.objects.link(obj)

    for light in lights:
        light.light_linking.receiver_collection = collection
        light.light_linking.blocker_collection = collection

    # 集合内全部网格设为排除，仅照亮本 root
    for entry in collection.collection_objects:
        entry.light_linking.link_state = 'EXCLUDE'


def move_to_collection(obj, collection):
    """把对象移动到指定集合"""
    for other in list(obj.users_collection):
        if other != collection:
            other.objects.unlink(obj)
    if collection not in obj.users_collection:
        collection.objects.link(obj)


def link_collection(parent, collection):
    """把集合挂到指定父级集合下"""
    for other in bpy.data.collections:
        entry = other.children.get(collection.name)
        if entry is None:
            continue
        if other == parent:
            return
        other.children.unlink(collection)
    parent.children.link(collection)


def arrange_light_groups(props):
    """按互斥与灯光组数整理灯光所属集合及对象命名"""
    scene = bpy.context.scene
    light_coll = get_collection(translate("灯光"))
    groups = get_light_groups(scene)
    controllers = get_light_controllers()

    root_names = [root_name for root_name, group in groups.items()
                  if root_name is not None and is_complete_light_group(group)]
    # 互斥且存在多组时，按 root 分组到子集合并使用 root 前缀命名
    prefixed = props.mutex and len(root_names) > 1
    sub_suffix = f"_{translate('灯光')}"
    light_names = (translate("主光"), translate("辅光"), translate("背光"))
    controller_name = translate("灯光控制器")

    used_collections = set()
    for root_name in root_names:
        group = groups[root_name]
        if prefixed:
            collection = bpy.data.collections.get(f"{root_name}{sub_suffix}")
            if collection is None:
                collection = bpy.data.collections.new(f"{root_name}{sub_suffix}")
            link_collection(light_coll, collection)
        else:
            collection = light_coll
        used_collections.add(collection)

        for light_role, light_name in zip(LIGHT_ROLES, light_names):
            obj = group.get(light_role)
            if obj is None:
                continue
            move_to_collection(obj, collection)
            obj.name = f"{root_name}_{light_name}" if prefixed else light_name

        controller = controllers.get(root_name)
        if controller is not None:
            move_to_collection(controller, collection)
            controller.name = (f"{root_name}_{controller_name}" if prefixed
                               else controller_name)

    # 清理不再使用的空子集合
    for child in list(light_coll.children):
        if child in used_collections or child.objects:
            continue
        if child.name.endswith(sub_suffix):
            unlink(child)
            bpy.data.collections.remove(child)


class LightSettingsOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.light_settings"
    bl_label = "设置"
    bl_description = "设置三点照明"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not self.gen_light(context):
            return {'CANCELLED'}
        return {'FINISHED'}

    # ------------------------------------------------------------------ #
    #  内部工具方法
    # ------------------------------------------------------------------ #
    def _create_light(self, attr_value: str, new_name: str) -> bpy.types.Object:
        """
        新建灯光
        Tri-Lighting 名称取自 https://docs.blender.org/manual/nb/3.6/addons/lighting/trilighting.html
        """
        light_data = bpy.data.lights.new(f"{attr_value}Data", type='AREA')
        light_data.size = LIGHT_SIZE
        # todo 设为0的必要性？
        light_data.volume_factor = 0
        obj = bpy.data.objects.new(new_name, light_data)
        obj[LIGHT_MARKER] = attr_value
        return obj

    # ------------------------------------------------------------------ #
    #  位置 / 旋转计算
    # ------------------------------------------------------------------ #
    @staticmethod
    def _apply_transforms(lights: list, props) -> None:
        key_light, fill_light, back_light = lights

        rotation_x = math.radians(LIGHT_ROTATION_X)
        key_y = math.radians(KEY_LIGHT_ANGLE)
        fill_y = math.radians(FILL_LIGHT_ANGLE)
        z_angle = math.radians(LIGHT_HEIGHT_ANGLE)

        key_factor = 1 if props.key_position == "RIGHT" else -1
        fill_factor = -key_factor

        d_key = props.key_distance
        d_fill = props.fill_distance
        d_back = props.back_distance
        back_z = props.back_angle

        # 主光
        key_light.rotation_euler = (rotation_x, 0, key_y * key_factor)
        key_light.location = (
            d_key * math.sin(key_y) * key_factor,
            -d_key * math.cos(key_y),
            d_key * math.tan(z_angle),
        )

        # 辅光
        fill_light.rotation_euler = (rotation_x, 0, fill_y * fill_factor)
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
    #  目标解析
    # ------------------------------------------------------------------ #
    def _resolve_target(self, obj, props):
        """解析对象对应的约束目标，返回 (目标对象, 子级名称)，无法解析时返回 None"""
        if obj is None:
            return None

        if props.target_type == "ARMATURE":
            target = obj if obj.type == "ARMATURE" else find_armature(find_ancestor(obj))
            if target is None or props.bone_name not in target.pose.bones:
                return None
            return target, props.bone_name

        if obj.type != 'MESH' or props.vg_name not in obj.vertex_groups:
            return None
        return obj, props.vg_name

    # ------------------------------------------------------------------ #
    #  主流程
    # ------------------------------------------------------------------ #
    def gen_light(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_light_settings
        active_obj = context.active_object

        if not self.check_props(context, props):
            return False

        new_light_names = ["主光", "辅光", "背光"]
        # 灯光定义：(属性值, 能量)
        light_defs = [
            ("KeyLight", props.key_energy),
            ("FillLight", props.fill_energy),
            ("BackLight", props.back_energy),
        ]

        # ---------- 灯光颜色 ----------
        colors = LIGHT_COLOR_PRESETS.get(props.preset, LIGHT_COLOR_PRESETS["DEFAULT"])

        # ---------- 目标与 root ----------
        # 按角色生成时，选中的多个角色一并生成灯光
        selected_objects = list(context.selected_objects) if props.mutex else []
        target_list = []
        used_root_names = set()
        for obj in [active_obj, *selected_objects]:
            resolved = self._resolve_target(obj, props)
            if resolved is None:
                continue
            root_name = find_ancestor(resolved[0]).name
            # 同一角色的多个对象只生成一组灯光
            if root_name in used_root_names:
                continue
            used_root_names.add(root_name)
            target_list.append((root_name, resolved[0], resolved[1]))

        if not target_list:
            self.report(type={'ERROR'}, message="Target not found!")
            return False

        # ---------- 清理旧灯光 ----------
        # 每次执行都按当前选中对象重建灯光，不再复用已有灯光
        groups = get_light_groups(scene)
        controllers = get_light_controllers()
        if props.mutex:
            # 按角色生成时重建选中角色的灯光和旧版（无 root 记录）的灯光，其它模型的灯光组保留
            rebuild_root_names = used_root_names | {None}
            # 对应 root 对象已不存在的灯光组一并移除
            for root_name in set(groups) | set(controllers):
                if root_name is not None and bpy.data.objects.get(root_name) is None:
                    rebuild_root_names.add(root_name)
        else:
            # 否则整个场景只保留一组灯光
            rebuild_root_names = set(groups) | set(controllers)
        for root_name in rebuild_root_names:
            remove_light_group(groups.get(root_name, {}), controllers.get(root_name), root_name)

        # 新建对象必须先挂到灯光集合：否则约束的清除反向会不生效
        light_coll = get_collection(translate("灯光"))

        # ---------- 创建三盏灯与控制器 ----------
        for root_name, target, subtarget in target_list:
            lights = []
            for i, (attr, energy) in enumerate(light_defs):
                obj = self._create_light(attr, translate(new_light_names[i]))
                obj.data.energy = energy
                obj.data.exposure = props.exposure
                obj.data.color = hex_to_rgb(colors[i])
                obj[LIGHT_ROOT_PROPERTY] = root_name
                lights.append(obj)

            # 位置旋转
            self._apply_transforms(lights, props)

            # 灯光控制器
            light_root = bpy.data.objects.new(translate("灯光控制器"), None)
            light_root[LIGHT_MARKER] = LIGHT_CONTROLLER_ATTR
            light_root[LIGHT_ROOT_PROPERTY] = root_name

            for obj in (*lights, light_root):
                if not obj.users_collection:
                    light_coll.objects.link(obj)

            # 约束设置
            set_cons(light_root, target, subtarget=subtarget)
            for light in lights:
                set_cons(light, light_root)

        # ---------- 灯光链接 ----------
        if props.mutex:
            # 所有灯光组都排除其它 root 的网格，保证模型之间互不影响，但是依然可以照亮场景
            all_groups = get_light_groups(scene)
            all_root_names = {root_name for root_name in all_groups if root_name is not None}
            for root_name, root_group in all_groups.items():
                if root_name is None or not is_complete_light_group(root_group):
                    continue
                apply_light_linking([root_group[light_role] for light_role in LIGHT_ROLES],
                                    root_name, all_root_names - {root_name})
        else:
            root_name = target_list[0][0]
            root_group = get_light_groups(scene).get(root_name, {})
            apply_light_linking([root_group[light_role] for light_role in LIGHT_ROLES],
                                root_name, set())

        # ---------- 集合与命名 ----------
        arrange_light_groups(props)

        return True

    def check_props(self, context, props):
        active_object = context.active_object
        target_type = props.target_type
        bone_name = props.bone_name
        vg_name = props.vg_name
        if target_type == "ARMATURE":
            if not active_object:
                self.report(type={'ERROR'}, message='Select armature object!')
                return False
            if active_object.type == "ARMATURE":
                armature = active_object
            else:
                ancestor = find_ancestor(active_object)
                armature = find_armature(ancestor)
            if not armature:
                self.report(type={'ERROR'}, message='Armature not found!')
                return False
            if bone_name not in armature.pose.bones:
                self.report(type={'ERROR'},
                            message=bpy.app.translations.pgettext_iface("Bone \"{}\" not found!").format(bone_name))
                return False
            return True
        elif target_type == "MESH":
            if not active_object:
                self.report(type={'ERROR'}, message='Select mesh object!')
                return False
            if active_object.type != 'MESH':
                self.report(type={'ERROR'}, message='Select mesh object!')
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
        return False


def apply_light_transforms(lights, props):
    """按灯光参数更新三盏灯的位置与旋转"""
    LightSettingsOperator._apply_transforms(lights, props)


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
        if not self.gen_camera_animation(context):
            return {'CANCELLED'}
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
        props = context.scene.mmd_kafei_tools_camera_settings

        if self.check_props(context, props) is False:
            return False

        active_object = context.active_object

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
            empty = set_empty(context, props, active_object)

        # 创建跟随相机
        camera = create_follow_camera(context, props)

        # 拷贝骨架并精简骨骼
        if target_type == "ARMATURE":
            bone_name = props.bone_name
            armature_copied = copy_and_prune_armature(armature, bone_name)

        # 记录当前场景
        main_scene = context.scene

        # 创建并切换到临时场景
        # 添加一个新的空场景，并拷贝当前场景的设置。可排除frame_start、frame_end、fps等设置因新场景初始化带来的影响
        scenes_before = set(bpy.data.scenes)
        bpy.ops.scene.new(type='EMPTY')
        scenes_after = set(bpy.data.scenes)
        tmp_scene = (scenes_after - scenes_before).pop()

        try:
            context.window.scene = tmp_scene
            tmp_scene.name = "TmpScene"

            # 烘焙相机动画
            if target_type == "ARMATURE":
                tmp_scene.collection.objects.link(armature_copied)
                bake_camera_animation(context, props, camera, armature=armature_copied)
                bpy.data.objects.remove(armature_copied, do_unlink=True)
            else:
                tmp_scene.collection.objects.link(empty)
                bake_camera_animation(context, props, camera, empty=empty)
                bpy.data.objects.remove(empty, do_unlink=True)
        except Exception as e:
            # 异常时清理已创建的相机与临时对象，并提示用户
            for obj in (camera.parent, camera, armature_copied, empty):
                if obj is None:
                    continue
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except ReferenceError:
                    pass
            self.report({'ERROR'}, f"相机动画生成失败：{e}")
            return False
        finally:
            # 无论烘焙是否成功，都恢复主场景并清理临时场景
            context.window.scene = main_scene
            bpy.data.scenes.remove(tmp_scene)

        # 选中相机控制器 激活相机
        deselect_all_objects()
        select_and_activate(camera.parent)
        context.scene.camera = camera
        # 切换到相机视图
        with context.temp_override(**view3d_context()):
            switch_to_camera_view()

        # 结束时恢复为场景起始帧
        context.scene.frame_set(context.scene.frame_start)

        return True

    def check_props(self, context, props):
        active_object = context.active_object
        target_type = props.target_type
        bone_name = props.bone_name
        vg_name = props.vg_name
        if target_type == "ARMATURE":
            if not active_object or not active_object.select_get():
                # 必须同时满足选中且激活
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
            if frame_start is None or frame_end is None:
                self.report(type={'ERROR'}, message=f'Armature has no keyframes!')
                return False
            return True
        elif target_type == "MESH":
            # 获取选中网格对象
            selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
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


class CameraSettingsMeshOperator(bpy.types.Operator):
    """网格目标专用入口：在提示中额外说明顶点消失的影响"""
    bl_idname = "mmd_kafei_tools.camera_settings_mesh"
    bl_label = "执行"
    bl_description = ("生成相机跟随动画\n"
                      "顶点被焊接、遮罩等修改器移除时，相机动画会受到影响")

    def execute(self, context):
        return bpy.ops.mmd_kafei_tools.camera_settings('EXEC_DEFAULT')


def set_empty(context, props, active_object):
    # 获取跟随对象
    vg_name = props.vg_name
    selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
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
    context.scene.collection.objects.link(empty)
    empty.parent = mesh_object
    empty.parent_type = 'VERTEX'
    empty.parent_vertices[0] = vertex.index
    return empty


def bake_camera_animation(context, props, camera, armature=None, empty=None):
    bone_name = props.bone_name
    threshold_x = props.threshold_x
    threshold_y = props.threshold_y
    threshold_z = props.threshold_z
    max_gap = props.max_gap
    savepoint_x = None
    savepoint_y = None
    savepoint_z = None
    is_first_frame = True
    # 获取帧范围
    target_type = props.target_type
    if target_type == "ARMATURE":
        frame_start, frame_end = get_armature_keyframe_range(armature)
    else:
        frame_start, frame_end = context.scene.frame_start, context.scene.frame_end

    depsgraph = context.evaluated_depsgraph_get()
    for frame in range(frame_start, frame_end + 1):
        context.scene.frame_set(frame)

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
        if is_first_frame:
            savepoint_x, savepoint_y, savepoint_z = lo_x, lo_y, lo_z
            is_first_frame = False
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
            # 假设角色高度为1，相机视野高为1。若角色蹲下使高为0.5，则为了使角色处于中心，相机应下降0.25
            camera.location[2] += delta_z * CAMERA_Z_FACTOR

        # 插入关键帧
        camera.keyframe_insert(data_path="location", frame=frame)

        # 更新参考点
        savepoint_x, savepoint_y = lo_x, lo_y

        if abs(delta_z) > threshold_z:
            savepoint_z = lo_z
    # 根据 最大不同帧间隔 设置关键帧
    fcurves = get_action_fcurves(camera)
    # 按 array_index 建立 X/Y/Z 通道映射，不依赖 F-Curve 的列表顺序
    fcurve_map = {fc.array_index: fc for fc in fcurves if fc.data_path == "location"}

    # kp.co.x 帧号，kp.co.y 关键帧的数值
    all_frame_numbers = [kp.co.x for fc in fcurve_map.values() for kp in fc.keyframe_points]
    # 去重并排序
    frames = sorted(set(all_frame_numbers))

    for i in range(len(frames) - 1):
        f1, f2 = int(frames[i]), int(frames[i + 1])
        gap = f2 - f1
        if gap <= max_gap:
            continue

        # 获取帧上的 location 值
        loc1 = Vector((
            fcurve_map[0].evaluate(f1),
            fcurve_map[1].evaluate(f1),
            fcurve_map[2].evaluate(f1),
        ))
        loc2 = Vector((
            fcurve_map[0].evaluate(f2),
            fcurve_map[1].evaluate(f2),
            fcurve_map[2].evaluate(f2),
        ))

        # 差值判断
        if (loc2 - loc1).length < PRECISION:
            continue

        # 目标插入帧
        insert_frame = f2 - max_gap
        # 插入 loc1
        camera.location = loc1
        camera.keyframe_insert(data_path="location", frame=insert_frame)

    context.scene.frame_set(0)


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


def create_follow_camera(context, props):
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
    active_object = context.active_object
    selected_objects = context.selected_objects
    deselect_all_objects()
    select_and_activate(empty)
    bpy.ops.object.transform_apply(scale=True)
    restore_selection(selected_objects, active_object)
    camera.parent = empty
    camera.matrix_parent_inverse = empty.matrix_world.inverted()

    # 设置相机初始位置
    context.scene.frame_set(0)

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

    frame_start = None
    frame_end = None

    for fcurve in fcurves:
        # 批量读取该曲线的全部帧号，避免逐关键帧访问 RNA 属性
        frames = get_fcurve_frames(fcurve)
        if not frames:
            continue

        fc_start = min(frames)
        fc_end = max(frames)
        frame_start = fc_start if frame_start is None else min(frame_start, fc_start)
        frame_end = fc_end if frame_end is None else max(frame_end, fc_end)

    if frame_start is None:
        return None, None

    return int(frame_start), int(frame_end)
