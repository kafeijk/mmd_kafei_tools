import bpy
import re

ABC_NAME_PATTERN = re.compile(r'xform_(\d+)_material_(\d+)')


def deselect_all_objects():
    """对场景中的选中对象和活动对象取消选择"""
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None


def select_and_activate(obj):
    """选中并激活物体"""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def set_visibility(obj, hide_set_flag, hide_viewport_flag, hide_render_flag):
    """设置Blender物体的可见性相关属性"""
    # 是否在视图中隐藏
    obj.hide_set(hide_set_flag)
    # 是否在视图中禁用
    obj.hide_viewport = hide_viewport_flag
    # 是否在渲染中禁用
    obj.hide_render = hide_render_flag


def hide_object(obj):
    """隐藏物体。在视图中隐藏，在视图中禁用，在渲染中禁用"""
    set_visibility(obj, True, True, True)


def show_object(obj):
    """显示物体。在视图中取消隐藏，在视图中取消禁用，在渲染中取消禁用"""
    set_visibility(obj, False, False, False)


def sort_mesh_objects(mesh_objects, mmd_type):
    """依据mmd_type对mesh物体名称进行排序"""
    if mmd_type == 'ROOT':
        mesh_objects.sort(key=lambda obj: obj.name)
    else:
        mesh_objects.sort(key=lambda obj: int(ABC_NAME_PATTERN.match(obj.name).group(2)))
    return mesh_objects


def get_mesh_objects(obj):
    """获取空物体下面的mesh对象，顺序为大纲顺序"""
    mesh_objects = [obj] if obj.type == 'MESH' else []
    for child in obj.children:
        if child.type in {'ARMATURE', 'MESH'}:
            mesh_objects.extend(get_mesh_objects(child))
    return mesh_objects


def get_abc_objects():
    """获取场景中的abc对象"""
    abc_objects = [obj for obj in bpy.context.scene.objects if ABC_NAME_PATTERN.match(obj.name)]
    return abc_objects


def modifiers_by_type(obj, typename):
    """通过类型获取修改器"""
    return [x for x in obj.modifiers if x.type == typename]


def find_pmx_root():
    """寻找pmx对应空物体"""
    return next((obj for obj in bpy.context.scene.objects if obj.mmd_type == 'ROOT'), None)


def find_abc_root():
    """寻找abc对应空物体"""
    return next(
        (obj for obj in bpy.context.scene.objects if obj.type == 'EMPTY' and not obj.parent and obj.mmd_type == 'NONE'),
        None)


def move_object_to_collection_recursive(obj, target_collection):
    """将指定对象及其子级（递归）移动到指定集合"""
    # 将对象从原始集合中移除
    if obj.users_collection:
        obj.users_collection[0].objects.unlink(obj)
    # 将对象添加到目标集合中
    target_collection.objects.link(obj)
    # 递归处理子对象
    for child in obj.children:
        move_object_to_collection_recursive(child, target_collection)

def case_insensitive_replace(pattern, replacement, string):
    """忽略大小写替换"""
    return re.sub(pattern, replacement, string, flags=re.IGNORECASE)