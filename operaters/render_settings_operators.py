import bpy


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
