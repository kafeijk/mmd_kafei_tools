from . import auto_load

# https://docs.blender.org/manual/en/3.0/advanced/scripting/addon_tutorial.html
bl_info = {
    "name": "mmd_kafei_tools",
    "description": "MMD实用工具",
    "author": "来杯咖啡再说",
    "version": (1, 4, 0),
    "blender": (3, 0, 0),  # 低于此版本的blender，插件不会显示在插件列表中
    "location": "View3D > Sidebar > KafeiTools Panel",
    "category": "Object",
}

auto_load.init()


def register():
    auto_load.register()


def unregister():
    auto_load.unregister()


if __name__ == "__main__":
    register()
