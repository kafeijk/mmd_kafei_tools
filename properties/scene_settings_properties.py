import math

import bpy

from ..constants import (LIGHT_COLOR_PRESETS,
                         LIGHT_MARKER, LIGHT_ROLES, LIGHT_ROLE_ALIASES, LIGHT_ROOT_PROPERTY,
                         RESOLUTION_PRESETS)
from ..utils import hex_to_rgb


def update_render_settings(self, context):
    """渲染引擎参数变更后立即应用渲染设置"""
    from ..operators.scene_settings_operators import apply_render_settings
    apply_render_settings(context)


def update_world_settings(self, context):
    """世界环境参数变更后立即应用世界环境"""
    from ..operators.scene_settings_operators import apply_world_settings
    apply_world_settings(context)


class RenderSettingsProperty(bpy.types.PropertyGroup):
    engine: bpy.props.EnumProperty(
        name="渲染引擎",
        description="用于渲染的引擎",
        items=[
            ("EEVEE", "EEVEE", "EEVEE"),
            ("CYCLES", "Cycles", "Cycles")

        ],
        default="EEVEE",
        update=update_render_settings
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_render_settings = bpy.props.PointerProperty(type=RenderSettingsProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_render_settings


class WorldSettingsProperty(bpy.types.PropertyGroup):
    world_name: bpy.props.EnumProperty(
        name="世界环境",
        description="世界环境",
        items=[
            ("DEFAULT", "默认", "世界背景为黑色，无光照贡献"),
            ("CITY", "城市", "城市"),
            ("COURTYARD", "庭院", "庭院"),
            ("FOREST", "森林", "森林"),
            ("INTERIOR", "室内", "室内"),
            ("NIGHT", "夜景", "夜景"),
            ("STUDIO", "摄影棚", "摄影棚"),
            ("SUNRISE", "日出", "日出"),
            ("SUNSET", "日落", "日落"),
        ],
        default="DEFAULT",
        update=update_world_settings
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_world_settings = bpy.props.PointerProperty(type=WorldSettingsProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_world_settings


def apply_resolution_preset(scene, identifier):
    """按预设设置渲染分辨率，并恢复缩放比例/像素比默认值"""
    preset = RESOLUTION_PRESETS.get(identifier)
    if preset is None:
        return False
    _, width, height = preset
    rd = scene.render
    rd.resolution_x = width
    rd.resolution_y = height
    rd.resolution_percentage = rd.bl_rna.properties["resolution_percentage"].default
    rd.pixel_aspect_x = rd.bl_rna.properties["pixel_aspect_x"].default
    rd.pixel_aspect_y = rd.bl_rna.properties["pixel_aspect_y"].default
    return True


def update_resolution(self, context):
    """分辨率下拉变更后立即生效；相机视角下重新对准相机"""
    if not apply_resolution_preset(context.scene, self.resolution):
        return
    from ..utils import center_view_camera
    center_view_camera()


class OutputSettingsProperty(bpy.types.PropertyGroup):
    resolution: bpy.props.EnumProperty(
        name="分辨率",
        description="分辨率",
        items=[
            (identifier, label, f"{width}x{height}")
            for identifier, (label, width, height) in RESOLUTION_PRESETS.items()
        ],
        default="1080P",
        update=update_resolution
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_output_settings = bpy.props.PointerProperty(type=OutputSettingsProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_output_settings


def get_light_groups(scene=None):
    """按记录的 root 名称来分组插件生成的灯光，返回 {root: {灯光角色: 灯光对象}}"""
    scene = scene or bpy.context.scene
    groups = {}
    for obj in scene.objects:
        if obj.type != 'LIGHT':
            continue
        light_role = obj.get(LIGHT_MARKER)
        if light_role in LIGHT_ROLE_ALIASES:
            light_role = LIGHT_ROLE_ALIASES[light_role]
        if light_role not in LIGHT_ROLES:
            continue
        groups.setdefault(obj.get(LIGHT_ROOT_PROPERTY), {})[light_role] = obj
    return groups


def is_complete_light_group(group):
    """三盏灯是否齐全"""
    return all(light_role in group for light_role in LIGHT_ROLES)


def is_light_linking_supported():
    """灯光链接是否可用：Cycles 4.0+ 生效；其他引擎需 4.3+；Workbench 始终不支持"""
    properties = bpy.types.Object.bl_rna.properties
    linking = properties.get("light_linking")
    if linking is None:
        return False
    if not {"receiver_collection", "blocker_collection"} <= set(linking.fixed_type.properties.keys()):
        return False
    scene = getattr(bpy.context, "scene", None)
    engine = scene.render.engine if scene else "CYCLES"
    # Workbench 实际不受灯光影响
    if engine == "BLENDER_WORKBENCH":
        return False
    if engine != "CYCLES" and bpy.app.version < (4, 3, 0):
        return False
    return True


def update_light_transforms(self, context):
    """位置/距离/角度变化时，若三盏灯齐全则实时更新三盏灯"""
    from ..operators.scene_settings_operators import apply_light_transforms
    for group in get_light_groups(context.scene).values():
        if not is_complete_light_group(group):
            continue
        apply_light_transforms([group[light_role] for light_role in LIGHT_ROLES], self)


def update_light_linking(self, context):
    """“目标间互不影响”变化时，实时更新所有插件灯光的链接排除"""
    if self.light_type != "AREA" or not is_light_linking_supported():
        return
    from ..operators.scene_settings_operators import sync_light_linking
    sync_light_linking(self.independent)


def update_preset(self, context):
    """颜色预设变化时，若三盏灯齐全则实时更新颜色"""
    colors = LIGHT_COLOR_PRESETS.get(self.preset, LIGHT_COLOR_PRESETS["DEFAULT"])
    for group in get_light_groups(context.scene).values():
        if not is_complete_light_group(group):
            continue
        for light_role, color_hex in zip(LIGHT_ROLES, colors):
            group[light_role].data.color = hex_to_rgb(color_hex)


def update_light_energy(self, context):
    """功率或曝光度变化时，若三盏灯齐全则同步功率与曝光度"""
    from ..operators.scene_settings_operators import apply_light_exposure
    energies = (self.key_energy, self.fill_energy, self.back_energy)
    for group in get_light_groups(context.scene).values():
        if not is_complete_light_group(group):
            continue
        for light_role, energy in zip(LIGHT_ROLES, energies):
            apply_light_exposure(group[light_role].data, energy, self.exposure)


class LightSettingsProperty(bpy.types.PropertyGroup):
    target_type: bpy.props.EnumProperty(
        name="目标类型",
        description="灯光跟随目标的类型",
        items=[
            ("ARMATURE", "骨架", "骨架"),
            ("MESH", "网格", "网格")

        ],
        default="ARMATURE"
    )

    bone_name: bpy.props.StringProperty(
        name="骨骼",
        description="骨骼名称",
        default='頭'
    )

    vg_name: bpy.props.StringProperty(
        name="顶点组",
        description="顶点组名称",
        default='Group'
    )

    # ---------------------- 灯光参数 ----------------------
    light_type: bpy.props.EnumProperty(
        name="灯光类型",
        description="面光可为每个目标创建一组灯光；面光（复用）整个场景只保留一组灯光",
        items=[
            ("AREA", "面光", "为每个目标创建一组灯光"),
            ("AREA_REUSE", "面光（复用）", "整个场景只保留一组灯光"),
        ],
        default="AREA"
    )

    independent: bpy.props.BoolProperty(
        name="目标间互不影响",
        description="通过灯光链接排除其它目标的网格，使各目标的灯光互不影响",
        default=True,
        update=update_light_linking
    )

    preset: bpy.props.EnumProperty(
        name="颜色预设",
        description="灯光颜色预设",
        items=[
            ("DEFAULT", "默认", "默认"),
            ("RED_BLUE", "红蓝", "红蓝"),
            ("BLUE_PURPLE", "蓝紫", "蓝紫"),
            ("MOONLIGHT", "冷月", "冷月"),
            ("SAKURA", "樱粉", "樱粉"),  # 相对默认更有肉色
            ("SOFT_WHITE", "柔白", "柔白")  # 相对默认皮肤更白

        ],
        default="DEFAULT",
        update=update_preset
    )

    exposure: bpy.props.FloatProperty(
        name="曝光度",
        description="将光强乘以 2^曝光度，以指数形式对灯光功率进行缩放",
        default=0,
        soft_min=-10,
        soft_max=10,
        update=update_light_energy
    )

    key_energy: bpy.props.IntProperty(
        name="主光功率",
        description="主光的功率",
        default=150,
        min=0,
        update=update_light_energy
    )

    fill_energy: bpy.props.IntProperty(
        name="辅光功率",
        description="辅光的功率",
        default=60,
        min=0,
        update=update_light_energy
    )

    back_energy: bpy.props.IntProperty(
        name="背光功率",
        description="背光的功率",
        default=100,
        min=0,
        update=update_light_energy
    )

    show_advanced: bpy.props.BoolProperty(
        name="显示更多参数",
        description="勾选后显示距离与灯光类型参数",
        default=False
    )

    key_distance: bpy.props.FloatProperty(
        name="主光距离",
        description="主光到目标的直线距离",
        subtype='DISTANCE',
        default=2,
        min=0.0,
        update=update_light_transforms
    )

    fill_distance: bpy.props.FloatProperty(
        name="辅光距离",
        description="辅光到目标的直线距离",
        subtype='DISTANCE',
        default=1.5,
        min=0.0,
        update=update_light_transforms
    )

    back_distance: bpy.props.FloatProperty(
        name="背光距离",
        description="背光到目标的直线距离",
        subtype='DISTANCE',
        default=1,
        min=0.0,
        update=update_light_transforms
    )

    key_position: bpy.props.EnumProperty(
        name="主光位置",
        description="以角色自身为基准，主光的位置",
        items=[
            ("LEFT", "左", "左"),
            ("RIGHT", "右", "右")

        ],
        default="LEFT",
        update=update_light_transforms
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_light_settings = bpy.props.PointerProperty(type=LightSettingsProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_light_settings


class CameraSettingsProperty(bpy.types.PropertyGroup):
    target_type: bpy.props.EnumProperty(
        name="目标类型",
        description="相机跟随目标的类型",
        items=[
            ("ARMATURE", "骨架", "骨架"),
            ("MESH", "网格", "网格")

        ],
        default="ARMATURE"
    )

    bone_name: bpy.props.StringProperty(
        name="骨骼",
        description="相机跟随的骨骼名称",
        default="下半身"
    )

    vg_name: bpy.props.StringProperty(
        name="顶点组",
        description="顶点组名称",
        default='Group'
    )

    threshold_x: bpy.props.FloatProperty(
        name="增量阈值 X",
        description="骨骼X轴上位置的增量阈值，当骨骼位置变化超过该值时更新相机位置",
        default=0.1,
        min=0.0,
        subtype='DISTANCE'
    )

    threshold_y: bpy.props.FloatProperty(
        name="Y",
        description="骨骼Y轴上位置的增量阈值，当骨骼位置变化超过该值时更新相机位置",
        default=0.1,
        min=0.0,
        subtype='DISTANCE'

    )

    threshold_z: bpy.props.FloatProperty(
        name="Z",
        description="骨骼Z轴上位置的增量阈值，当骨骼位置变化超过该值时更新相机位置",
        default=0.1,
        min=0.0,
        subtype='DISTANCE'
    )

    rotation_euler_x: bpy.props.FloatProperty(
        name="相机旋转 X",
        description="相机X轴旋转",
        subtype="ANGLE",
        default=math.radians(85)
    )

    max_gap: bpy.props.IntProperty(
        name="最大不同帧间隔",
        description="两个不同关键帧之间的最大帧间隔，用于避免角色几乎不动时相机缓慢移动的问题",
        default=15,
        min=1,
    )

    @staticmethod
    def register():
        bpy.types.Scene.mmd_kafei_tools_camera_settings = bpy.props.PointerProperty(type=CameraSettingsProperty)

    @staticmethod
    def unregister():
        del bpy.types.Scene.mmd_kafei_tools_camera_settings
