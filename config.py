from ...common.types.framework import is_extension

# https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html#extensions-and-namespace
# 插件唯一包名，与 bl_info 中的插件名不同；用于在 python 代码中标识插件
__addon_name__ = ".".join(__package__.split(".")[0:3]) if is_extension() else __package__.split(".")[0]
