
from ..utils import *


class ModifyColorspaceOperator(bpy.types.Operator):
    bl_idname = "mmd_kafei_tools.modify_colorspace"
    bl_label = "修改"
    bl_description = "修改贴图色彩空间"
    bl_options = {'REGISTER', 'UNDO'}  # 启用撤销功能

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}  # 让Blender知道操作已成功完成

    def check_props(self, props):
        colorspace = props.colorspace
        keywords = props.keywords
        selected_only = props.selected_only

        if not colorspace:
            self.report(type={'ERROR'}, message=f'请选择色彩空间！')
            return False
        if not keywords and not selected_only:
            self.report(type={'ERROR'}, message=f'未填写关键词时，必须开启仅选中！')
            return False
        if selected_only and len(bpy.context.selected_objects) == 0:
            self.report(type={'ERROR'}, message=f'请选择至少一个物体！')
            return False
        return True

    def main(self, context):
        scene = context.scene
        props = scene.mmd_kafei_tools_modify_colorspace
        if not self.check_props(props):
            return
        colorspace = props.colorspace
        keywords = props.keywords
        selected_only = props.selected_only
        objs = bpy.context.selected_objects
        # 关键词列表
        keyword_list = []
        if keywords:
            keyword_list = [keyword.lower().strip() for keyword in keywords.split(",")]

        # 如果作用于全部物体，则直接对图像对象进行修改
        if not selected_only:
            for image in bpy.data.images:
                if len(keyword_list) == 0:
                    image.colorspace_settings.name = colorspace
                else:
                    if any(keyword in image.name.lower().strip() for keyword in keyword_list):
                        # 修改图像的色彩空间
                        image.colorspace_settings.name = colorspace
        else:
            # 如果不是作用于全部物体，则需要筛选出作用的图像对象
            images = set()
            for obj in objs:
                if not obj.material_slots:  # 材质槽为空
                    continue
                for slot in obj.material_slots:
                    material = slot.material
                    if not material:  # 有材质槽但无材质
                        continue

                    node_tree = material.node_tree
                    if not node_tree:  # 有材质但无节点树
                        continue

                    nodes = node_tree.nodes
                    if not nodes:  # 有节点树但无节点
                        continue

                    for node in nodes:
                        if node.type == 'TEX_IMAGE':
                            image = node.image
                            images.add(image)
            for image in images:
                if len(keyword_list) == 0:
                    image.colorspace_settings.name = colorspace
                else:
                    if any(keyword in image.name.lower().strip() for keyword in keyword_list):
                        # 修改图像的色彩空间
                        image.colorspace_settings.name = colorspace
