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
