# The following section references and adapts functions from the mmd_tools addon

import bpy
from .utils import get_addon_version, find_pmx_armature

from .tools.opencc import OpenCC

cc_s2t = OpenCC("s2t")
cc_t2jp = OpenCC("t2jp")


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


def fix_bone_issues(root):
    armature = find_pmx_armature(root)

    if armature is None:
        return

    name_counts = {}
    processed_names = set()

    # First collect all names and mark duplicates
    for pose_bone in armature.pose.bones:
        if getattr(pose_bone, "is_mmd_shadow_bone", False):
            continue
        name_j = pose_bone.mmd_bone.name_j
        name_counts[name_j] = name_counts.get(name_j, 0) + 1

    # Process all bones - fix both length and duplicates
    for pose_bone in armature.pose.bones:
        if getattr(pose_bone, "is_mmd_shadow_bone", False):
            continue

        original_name = pose_bone.mmd_bone.name_j

        # Check if name is too long in cp932
        name_too_long = False
        has_non_japanese = False
        try:
            encoded = original_name.encode("cp932")
            name_too_long = len(encoded) > 15
        except UnicodeEncodeError:
            has_non_japanese = True

        is_duplicate = original_name in processed_names or name_counts.get(original_name, 0) > 1

        # Only process bones that need fixing
        if not (name_too_long or has_non_japanese or is_duplicate):
            processed_names.add(original_name)
            continue

        # First convert/remove non-Japanese characters
        converted_name = cc_s2t.convert(original_name)
        converted_name = cc_t2jp.convert(converted_name)

        new_name = ""
        for char in converted_name:
            try:
                char.encode("cp932")
                new_name += char
            except UnicodeEncodeError:
                continue

        # If name becomes empty after filtering, use a default name
        if not new_name:
            new_name = "bone"

        # Then truncate from right if still too long
        while new_name:
            try:
                encoded = new_name.encode("cp932")
                if len(encoded) <= 13:  # Leave room for suffixes
                    break
                new_name = new_name[:-1]
            except UnicodeEncodeError:
                new_name = new_name[:-1]

        # Now handle duplicate names
        final_name = new_name
        if new_name in processed_names:
            for suffix in range(2, 100):
                test_name = f"{new_name}{suffix}"
                try:
                    encoded_test = test_name.encode("cp932")
                    if len(encoded_test) <= 15 and test_name not in processed_names:
                        final_name = test_name
                        break
                except UnicodeEncodeError:
                    continue

        # Apply the final name and update processed_names
        pose_bone.mmd_bone.name_j = final_name
        processed_names.add(final_name)


def fix_morph_issues(root):
    if root is None:
        return

    processed_names = set()
    morph_types = ["vertex_morphs", "group_morphs", "bone_morphs", "material_morphs", "uv_morphs"]

    for morph_type in morph_types:
        if not hasattr(root.mmd_root, morph_type):
            continue

        morphs = getattr(root.mmd_root, morph_type)
        for morph in morphs:
            original_name = morph.name

            # Check if name is too long in cp932
            name_too_long = False
            has_non_japanese = False
            try:
                encoded = original_name.encode("cp932")
                name_too_long = len(encoded) > 15
            except UnicodeEncodeError:
                has_non_japanese = True

            # Skip if name is valid length and not a duplicate
            if not (name_too_long or has_non_japanese) and original_name not in processed_names:
                processed_names.add(original_name)
                continue

            # First convert/remove non-Japanese characters
            converted_name = cc_s2t.convert(original_name)
            converted_name = cc_t2jp.convert(converted_name)

            new_name = ""
            for char in converted_name:
                try:
                    char.encode("cp932")
                    new_name += char
                except UnicodeEncodeError:
                    continue

            # If name becomes empty after filtering, use a default name
            if not new_name:
                new_name = "morph"

            # Then truncate from right if still too long
            while new_name:
                try:
                    encoded = new_name.encode("cp932")
                    if len(encoded) <= 14:
                        break
                    new_name = new_name[:-1]
                except UnicodeEncodeError:
                    new_name = new_name[:-1]

            # Now check if the new name is unique or needs a suffix
            final_name = new_name
            if new_name in processed_names:
                for suffix in range(2, 10):  # Plenty of suffixes
                    test_name = f"{new_name}{suffix}"
                    try:
                        encoded_test = test_name.encode("cp932")
                        if len(encoded_test) <= 15 and test_name not in processed_names:
                            final_name = test_name
                            break
                    except UnicodeEncodeError:
                        continue

            # Apply the final name and update processed_names
            morph.name = final_name
            processed_names.add(final_name)
