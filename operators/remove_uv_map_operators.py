from ..utils import (
    deselect_all_objects,
    find_pmx_armature,
    find_pmx_objects,
    select_and_activate,
)


def do_remove_uv_maps(pmx_root):
    armature = find_pmx_armature(pmx_root)
    objs = find_pmx_objects(armature)
    for obj in objs:
        deselect_all_objects()
        select_and_activate(obj)
        remove_uv_maps(obj, True)


def remove_uv_maps(obj, keep_first):
    uv_maps = obj.data.uv_layers
    if keep_first:
        uv_maps_to_remove = uv_maps[1:]
    else:
        uv_maps_to_remove = uv_maps
    for uv_map in reversed(uv_maps_to_remove):
        obj.data.uv_layers.remove(uv_map)
    # https://blender.stackexchange.com/questions/163300/how-to-update-an-object-after-changing-its-uv-coordinates
    obj.data.update()
