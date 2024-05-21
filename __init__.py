from mmd_kafei_tools import auto_load

bl_info = {
    "name": "mmd_kafei_tools",
    "description": "MMD实用工具",
    "author": "来杯咖啡再说",
    "version": (0, 1, 0),
    "blender": (3, 6, 4),
    "location": "View3D > Sidebar > MMD Tools Panel",
    "category": "Object",
}

auto_load.init()
def register():
    auto_load.register()


def unregister():
    auto_load.unregister()


if __name__ == "__main__":
    register()
