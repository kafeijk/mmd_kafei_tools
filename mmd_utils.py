# The following section references and adapts functions from the mmd_tools addon

import bpy
from .utils import get_addon_version


def get_mmd_tools_version():
    v = get_addon_version("mmd_tools")
    if v > (-1, -1, -1):
        return v
    return get_addon_version("MMD Tools")


def get_mmd_armature_id():
    """
    获取mmd骨架修改器名称
    """
    v = get_mmd_tools_version()
    if v < (4, 3, 2):
        return "mmd_bone_order_override"
    return "mmd_armature"


def unsafe_change_bone_id(bone: bpy.types.PoseBone, new_bone_id: int, bone_morphs, pose_bones):
    """
    Change bone ID and updates all references without validating if new_bone_id is already in use.
    If new_bone_id is already in use, it may cause conflicts and corrupt existing bone references.
    """
    # Store the original bone_id and change it
    bone_id = bone.mmd_bone.bone_id
    bone.mmd_bone.bone_id = new_bone_id

    # Update all bone_id references in bone morphs
    for bone_morph in bone_morphs:
        for data in bone_morph.data:
            if data.bone_id == bone_id:
                data.bone_id = new_bone_id

    # Update all additional_transform_bone_id references in pose bones
    for pose_bone in pose_bones:
        if not hasattr(pose_bone, "is_mmd_shadow_bone") or not pose_bone.is_mmd_shadow_bone:
            mmd_bone = pose_bone.mmd_bone
            if mmd_bone.additional_transform_bone_id == bone_id:
                mmd_bone.additional_transform_bone_id = new_bone_id

    # Update all display_connection_bone_id references in pose bones
    for pose_bone in pose_bones:
        if not hasattr(pose_bone, "is_mmd_shadow_bone") or not pose_bone.is_mmd_shadow_bone:
            mmd_bone = pose_bone.mmd_bone
            if mmd_bone.display_connection_bone_id == bone_id:
                mmd_bone.display_connection_bone_id = new_bone_id
