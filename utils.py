import bpy
import re

ABC_NAME_PATTERN = re.compile(r'xform_(\d+)_material_(\d+)')
# 默认精度
PRECISION = 0.0001


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
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def deselect_all_objects():
    """对场景中的选中对象和活动对象取消选择"""
    if bpy.context.active_object is None:
        return
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = None


def show_object(obj):
    """显示物体。在视图取消禁用选择，在视图中取消隐藏，在视图中取消禁用，在渲染中取消禁用"""
    set_visibility(obj, False, False, False, False)


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


def walk_island(vert):
    ''' walk all un-tagged linked verts '''
    vert.tag = True
    yield (vert)
    linked_verts = [e.other_vert(vert) for e in vert.link_edges
                    if not e.other_vert(vert).tag]

    for v in linked_verts:
        if v.tag:
            continue
        yield from walk_island(v)


def get_islands(bm, verts=[]):
    """https://blender.stackexchange.com/questions/75332/how-to-find-the-number-of-loose-parts-with-blenders-python-api"""

    def tag(verts, switch):
        for v in verts:
            v.tag = switch

    tag(bm.verts, True)
    tag(verts, False)
    ret = {"islands": []}
    verts = set(verts)
    while verts:
        v = verts.pop()
        verts.add(v)
        island = set(walk_island(v))
        ret["islands"].append(list(island))
        tag(island, False)  # remove tag = True
        verts -= island
    return ret


def move_to_target_collection_recursive(obj, target_collection):
    """将指定对象及其子级（递归）移动到指定集合"""
    # 将对象从原始集合中移除
    if obj.users_collection:
        for collection in obj.users_collection:
            collection.objects.unlink(obj)
    # 将对象添加到目标集合中
    target_collection.objects.link(obj)
    # 递归处理子对象
    for child in obj.children:
        move_to_target_collection_recursive(child, target_collection)
