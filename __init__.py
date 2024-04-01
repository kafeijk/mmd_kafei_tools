bl_info = {
    "name": "mmd_kafei_tools",
    "description": "MMD实用工具",
    "author": "来杯咖啡再说",
    "version": (0, 1, 0),
    "blender": (3, 6, 4),
    "location": "View3D > Sidebar > MMD Tools Panel",
    "category": "Object",
}

import bpy
from .operators import TRANSFER_OT_preset_xiaoer
from .operators import ModifyImageColorspace
from .operators import ModifyHueSat
from .panel import PresetTransferPanel

classes = (TRANSFER_OT_preset_xiaoer, ModifyImageColorspace, ModifyHueSat, PresetTransferPanel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
