import bpy
import re

ABC_NAME_PATTERN = re.compile(r'xform_(\d+)_material_(\d+)')


def find_pmx_root():
    """寻找pmx对应空物体"""
    return next((obj for obj in bpy.context.scene.objects if obj.mmd_type == 'ROOT'), None)


def find_pmx_armature(pmx_root):
    return next((child for child in pmx_root.children if child.type == 'ARMATURE'), None)


def find_pmx_objects(pmx_armature):
    return list((child for child in pmx_armature.children if child.type == 'MESH'))


def find_abc_objects():
    """获取场景中的abc对象"""
    abc_objects = [obj for obj in bpy.context.scene.objects if ABC_NAME_PATTERN.match(obj.name)]
    return abc_objects


def sort_pmx_objects(objects):
    objects.sort(key=lambda obj: obj.name)


def sort_abc_objects(objects):
    objects.sort(key=lambda obj: int(ABC_NAME_PATTERN.match(obj.name).group(2)))


def select_and_activate(obj):
    """选中并激活物体"""
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def deselect_all_objects():
    """对场景中的选中对象和活动对象取消选择"""
    if bpy.context.active_object is None:
        return
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None


def set_visibility(obj, hide_select_flag, hide_set_flag, hide_viewport_flag, hide_render_flag):
    """设置Blender物体的可见性相关属性"""
    # 是否可选
    obj.hide_select = hide_select_flag
    # 是否在视图中隐藏
    obj.hide_set(hide_set_flag)
    # 是否在视图中禁用
    obj.hide_viewport = hide_viewport_flag
    # 是否在渲染中禁用
    obj.hide_render = hide_render_flag
