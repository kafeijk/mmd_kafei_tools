import re
import bmesh
import bpy

from mmd_kafei_tools import utils


class TRANSFER_OT_preset_xiaoer(bpy.types.Operator):
    bl_idname = "transfer.preset_xiaoer"
    bl_label = "转移"
    bl_description = "小二预设转移 pmx -> abc"
    bl_options = {'REGISTER', 'UNDO'}

    bpy.types.Scene.outline_width = bpy.props.FloatProperty(
        name="描边权重",
        description="描边权重，根据缩放比例填写，默认×12.5，对应导入时的0.08",
        default=12.5
    )

    def execute(self, context):
        process(context.scene.outline_width)
        return {'FINISHED'}


class ModifyImageColorspace(bpy.types.Operator):
    bl_idname = "transfer.modify_image_colorspace"
    bl_label = "根据关键词修改贴图色彩空间"
    bl_description = "根据关键词修改贴图色彩空间"
    bl_options = {'REGISTER', 'UNDO'}

    def get_colorspace(self, context):
        # 仅取常用色彩空间
        source_list = [
            ("sRGB", "sRGB", "sRGB", 0),
            ("Utility - sRGB - Texture", "Utility - sRGB - Texture", "Utility - sRGB - Texture", 1),
            ("Utility - Raw", "Utility - Raw", "Utility - Raw", 2),
            ("Utility - Linear - sRGB", "Utility - Linear - sRGB", "Utility - Linear - sRGB", 3),
            ("Non-Color", "Non-Color", "Non-Color", 4),

        ]
        colorspace_all = []
        for item in bpy.types.Image.bl_rna.properties['colorspace_settings'].fixed_type.properties['name'].enum_items:
            colorspace_all.append(item.identifier)
        index = 0
        target_list = []
        for source in source_list:
            if source[0] in colorspace_all:
                target_list.append((source[0], source[0], source[0], index))
                index = index + 1
        return target_list

    bpy.types.Scene.colorspace = bpy.props.EnumProperty(
        name='色彩空间',
        description='图像色彩空间',
        items=get_colorspace,
        default=0
    )

    bpy.types.Scene.image_keyword_list_str = bpy.props.StringProperty(
        name="关键词",
        description="贴图名称关键词，不区分大小写，用英文逗号隔开",
        default='Diffuse,Shadow_Ramp,bmp'
    )

    def execute(self, context):
        modify_image_colorspace(context.scene.colorspace, context.scene.image_keyword_list_str)
        return {'FINISHED'}


class ModifyHueSat(bpy.types.Operator):
    bl_idname = "transfer.modify_hue_sat"
    bl_label = "修改调色节点组色相/饱和度/明度"
    bl_description = "修改调色节点组色相/饱和度/明度"
    bl_options = {'REGISTER', 'UNDO'}

    bpy.types.Scene.hue = bpy.props.FloatProperty(
        name="色相",
        description="色相",
        default=0.5
    )
    bpy.types.Scene.saturation = bpy.props.FloatProperty(
        name="饱和度",
        description="饱和度",
        default=1
    )
    bpy.types.Scene.value = bpy.props.FloatProperty(
        name="明度",
        description="明度",
        default=2
    )

    def execute(self, context):
        modify_hue_sat(context.scene.hue, context.scene.saturation, context.scene.value)
        return {'FINISHED'}


def link_materials_between_objects(abc_pmx_map):
    """关联pmx材质到abc上面"""
    for abc_mesh_object, pmx_mesh_object in abc_pmx_map.items():
        utils.deselect_all_objects()
        # 选中并激活abc对象
        utils.select_and_activate(abc_mesh_object)
        # 选中并激活pmx对象
        utils.select_and_activate(pmx_mesh_object)
        # 复制UV贴图
        bpy.ops.object.join_uvs()
        # 关联材质
        bpy.ops.object.make_links_data(type='MATERIAL')
    utils.deselect_all_objects()


def link_modifiers_between_objects(abc_pmx_map):
    """复制pmx修改器到abc上面（同时保留网格序列缓存修改器，删除骨架修改器）"""
    for abc_mesh_object, pmx_mesh_object in abc_pmx_map.items():
        utils.deselect_all_objects()
        # 备份abc的修改器（不进行这一步的话abc的修改器会丢失）
        # 创建一个临时网格对象（立方体）
        bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        temp_mesh_object = bpy.context.active_object
        # 将abc的修改器关联到临时网格对象上面
        utils.select_and_activate(temp_mesh_object)
        utils.select_and_activate(abc_mesh_object)
        bpy.ops.object.make_links_data(type='MODIFIERS')

        # 复制pmx修改器到abc上面
        utils.deselect_all_objects()
        utils.select_and_activate(abc_mesh_object)
        utils.select_and_activate(pmx_mesh_object)
        bpy.ops.object.make_links_data(type='MODIFIERS')

        # 将临时网格对象的修改器名称、类型、属性复制到abc的新建修改器上面
        utils.deselect_all_objects()
        modifier_src = temp_mesh_object.modifiers[0]
        modifier_dst = abc_mesh_object.modifiers.new(modifier_src.name, modifier_src.type)
        properties = [p.identifier for p in modifier_src.bl_rna.properties
                      if not p.is_readonly]
        for prop in properties:
            setattr(modifier_dst, prop, getattr(modifier_src, prop))

        # 如果网格对象缓存修改器不在第一位，则将其移动到第一位
        utils.select_and_activate(abc_mesh_object)
        while abc_mesh_object.modifiers.find(modifier_dst.name) != 0:
            bpy.ops.object.modifier_move_up(modifier=modifier_dst.name)
        # 删除骨架修改器
        armature_modifiers = utils.modifiers_by_type(abc_mesh_object, 'ARMATURE')
        for armature_modifier in armature_modifiers:
            abc_mesh_object.modifiers.remove(armature_modifier)

        # 删除临时网格对象
        utils.deselect_all_objects()
        utils.select_and_activate(temp_mesh_object)
        bpy.ops.object.delete()


def find_locator():
    """寻找abc对应空物体"""
    return next(
        (obj for obj in bpy.context.scene.objects if obj.type == 'EMPTY' and obj.name in '面部定位'),
        None)


def process_outline(abc_pmx_map, outline_width):
    """描边宽度调整"""
    for abc_object, pmx_object in abc_pmx_map.items():
        modifier = None
        for mod in abc_object.modifiers:
            if mod.type == 'NODES':
                modifier = mod
                break
        if modifier:
            # 因为是浮点类型，所以一定要写小数点，不然会有问题
            modifier["Input_7"] = outline_width * 1.0
            # 解决使用Python更改修改器输入值时未触发更新的问题。详见 https://projects.blender.org/blender/blender/issues/87006
            modifier.node_group.interface_update(bpy.context)


def process_locator(abc_mesh_objects):
    """处理定位头部的物体"""
    located_obj = None
    for abc_mesh_obj in abc_mesh_objects:
        # 遍历每个对象的材质槽
        for material_slot in abc_mesh_obj.material_slots:
            # 获取材质
            material = material_slot.material
            # 检查材质的节点
            if material:
                # 获取材质节点树
                nodes = material.node_tree.nodes
                # 遍历节点，检查是否包含名称为 "actual_face" 的节点组
                for node in nodes:
                    if node.type == 'GROUP' and 'actual_face' in node.node_tree.name.lower():
                        located_obj = abc_mesh_obj
    if not located_obj:
        return
    locator = find_locator()
    if not locator:
        return
    # 清除locator_object父级（保持变换）
    world_loc = locator.matrix_world.to_translation()
    locator.parent = None
    locator.matrix_world.translation = world_loc
    target_collection = located_obj.users_collection[0]

    # 将locator移动到abc所在集合
    if target_collection:
        utils.move_object_to_collection_recursive(locator, target_collection)
    utils.deselect_all_objects()
    utils.select_and_activate(located_obj)
    min_z_vertex = None
    min_x_vertex = None
    max_x_vertex = None
    min_z = float('inf')
    min_x = float('inf')
    max_x = float('-inf')
    for face in located_obj.data.polygons:
        for vert_index in face.vertices:
            vertex = located_obj.data.vertices[vert_index]
            global_coord = located_obj.matrix_world @ vertex.co
            # Check minimum z
            if global_coord.z < min_z:
                min_z = global_coord.z
                min_z_vertex = vertex
            # Check minimum x
            if global_coord.x < min_x:
                min_x = global_coord.x
                min_x_vertex = vertex
            # Check maximum x
            if global_coord.x > max_x:
                max_x = global_coord.x
                max_x_vertex = vertex
    average_x = ((located_obj.matrix_world @ min_x_vertex.co).x + (located_obj.matrix_world @ max_x_vertex.co).x + (
            located_obj.matrix_world @ min_z_vertex.co).x) / 3
    average_y = ((located_obj.matrix_world @ min_x_vertex.co).y + (located_obj.matrix_world @ max_x_vertex.co).y + (
            located_obj.matrix_world @ min_z_vertex.co).y) / 3
    average_z = ((located_obj.matrix_world @ min_x_vertex.co).z + (located_obj.matrix_world @ max_x_vertex.co).z + (
            located_obj.matrix_world @ min_z_vertex.co).z) / 3

    # 进入编辑模式，将获取到的三个顶点选中
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action='DESELECT')

    # 获取网格数据
    mesh_target = located_obj.data
    # 使用bmesh创建一个网格实例
    bm_target = bmesh.from_edit_mesh(mesh_target)
    vertices = [v for v in bm_target.verts]
    selected_vertices = []
    for vert in vertices:
        if vert.index in (min_z_vertex.index, min_x_vertex.index, max_x_vertex.index):
            selected_vertices.append(vert.index)

            vert.select = True
    # 更新网格
    bmesh.update_edit_mesh(mesh_target)

    # 编辑模式下选择网格对象并设置三个顶点为父级
    utils.show_object(locator)
    locator.select_set(True)
    bpy.ops.object.vertex_parent_set()
    bpy.ops.object.mode_set(mode='OBJECT')
    # 将locator的位置设置为平均值
    locator.location = (average_x, average_y, average_z)
    utils.set_visibility(locator, False, False, True)
    # 将作为顶点父级的顶点放入顶点组中
    vertex_group_name = locator.name
    vertex_group = located_obj.vertex_groups.new(name=vertex_group_name)
    for index in selected_vertices:
        vertex_group.add([index], 1.0, 'REPLACE')


def process_light():
    """处理灯光物体"""
    light_collection = next((collection for collection in bpy.data.collections if "灯光" in collection.name), None)
    if light_collection is None:
        light_collection = bpy.data.collections.new("灯光")
        bpy.context.scene.collection.children.link(light_collection)
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT' and obj.name in bpy.context.view_layer.objects:
            utils.move_object_to_collection_recursive(obj, light_collection)


def is_completed(abc_mesh_objects):
    for abc_mesh_object in abc_mesh_objects:
        # 检查是否有材质槽
        if not abc_mesh_object.material_slots:
            return False
        # 检查每个材质槽的材质是否不为None
        for slot in abc_mesh_object.material_slots:
            if slot.material is None:
                return False
    # 如果所有物体都通过了上述检查，则返回True
    return True


def gen_abc_root(pmx_root, abc_mesh_objects):
    pmx_root_name = pmx_root.name
    users_collection = abc_mesh_objects[0].users_collection
    target_collection = None
    if users_collection and users_collection[0].name != 'Scene Collection':
        target_collection = users_collection[0]
    else:
        target_collection = next((collection for collection in bpy.data.collections if "角色" in collection.name), None)
        if target_collection is None:
            target_collection = bpy.data.collections.new("角色")
            bpy.context.scene.collection.children.link(target_collection)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[
        target_collection.name]
    # 创建一个名称为 pmx_root_name+" abc" 的空物体
    abc_root = None
    if 'pmx' in pmx_root_name.lower():
        abc_root = bpy.data.objects.new(utils.case_insensitive_replace("pmx", "abc", pmx_root_name), None)
    else:
        abc_root = bpy.data.objects.new(pmx_root_name + " abc", None)
    bpy.context.collection.objects.link(abc_root)
    # 将abc_mesh_objects全部移动到users_collection中并将空物体设置为父级
    for obj in abc_mesh_objects:
        obj.parent = abc_root
    utils.move_object_to_collection_recursive(abc_root, target_collection)
    return abc_root


def modify_image_colorspace(colorspace, image_keyword_list_str):
    """修改指定类型图像的色彩空间"""
    image_keyword_list = [keyword.strip() for keyword in image_keyword_list_str.split(",")]
    for image in bpy.data.images:
        if any(keyword.lower() in image.name.lower() for keyword in image_keyword_list):
            # 修改图像的色彩空间
            image.colorspace_settings.name = colorspace


# 遍历所有节点组
def modify_hue_sat(hue, saturation, value):
    """修改指定节点组的色相/饱和度/明度"""
    for node_group in bpy.data.node_groups:
        if "调色" in node_group.name:
            # 遍历节点组中的所有节点
            for node in node_group.nodes:
                # 检查节点类型是否为色相饱和度明度节点
                if node.type == 'HUE_SAT':
                    node.inputs["Hue"].default_value = hue
                    node.inputs["Saturation"].default_value = saturation
                    node.inputs["Value"].default_value = value


def process(outline_width):
    """一键上材质（三渲二abc流程）（小二）"""
    pmx_root = utils.find_pmx_root()
    abc_root = utils.find_abc_root()
    pmx_mesh_objects = utils.get_mesh_objects(pmx_root)
    abc_mesh_objects = utils.get_abc_objects()
    utils.sort_mesh_objects(pmx_mesh_objects, pmx_root.mmd_type)
    if abc_root is None and len(abc_mesh_objects) > 0:
        abc_root = gen_abc_root(pmx_root, abc_mesh_objects)
    utils.sort_mesh_objects(abc_mesh_objects, abc_root.mmd_type)
    abc_pmx_map = dict(zip(abc_mesh_objects, pmx_mesh_objects))
    if not is_completed(abc_mesh_objects):
        link_materials_between_objects(abc_pmx_map)
        link_modifiers_between_objects(abc_pmx_map)
        process_light()
        process_locator(abc_mesh_objects)
    process_outline(abc_pmx_map, outline_width)


if __name__ == "__main__":
    # process(12.5)
    # modify_image_colorspace(context.scene.colorspace, context.scene.image_keyword_list_str)
    pass
