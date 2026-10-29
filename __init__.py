import bpy

from .config import __addon_name__
from .m17n import translation_dict
from ...common.class_loader import auto_load

# https://docs.blender.org/manual/en/3.0/advanced/scripting/addon_tutorial.html
bl_info = {
    "name": "MMD Kafei Tools",
    "description": "MMD实用工具",
    "author": "来杯咖啡再说",
    "version": (1, 9, 2),
    "blender": (3, 2, 0),  # 低于此版本的blender，插件不会显示在插件列表中
    "location": "View3D > Sidebar > KafeiTools Panel",
    "category": "Object",
}


def register():
    auto_load.init()
    auto_load.register()

    bpy.app.translations.register(__addon_name__, translation_dict)

    print("{} addon is installed.".format(__addon_name__))


def unregister():
    bpy.app.translations.unregister(__addon_name__)

    auto_load.unregister()

    print("{} addon is uninstalled.".format(__addon_name__))


if __name__ == "__main__":
    register()
