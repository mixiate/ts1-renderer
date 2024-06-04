bl_info = {
    "name": "The Sims 1 Renderer",
    "description": "Renders sprites for The Sims 1. To be used with the TS1 Compiler.",
    "author": "mix",
    "version": (1, 3, 0),
    "blender": (4, 1, 0),
    "location": "View3D > Sidebar > The Sims Tab",
    "warning": "",
    "doc_url": "https://github.com/mixsims/ts1-renderer/wiki",
    "tracker_url": "https://github.com/mixsims/ts1-renderer/issues",
    "support": "COMMUNITY",
    "category": "Render",
}


if "bpy" in locals():
    import sys
    import importlib

    for name in tuple(sys.modules):
        if name.startswith(__name__ + "."):
            importlib.reload(sys.modules[name])


import bmesh
import bpy
import bpy_extras
import copy
import json
import math
import mathutils
import os
import shutil
import subprocess


class TS1R_addon_preferences(bpy.types.AddonPreferences):
    """Preferences for the addon."""

    bl_idname = __name__

    compiler_path: bpy.props.StringProperty(
        name="TS1 Compiler Path",
        description="Path to the TS1 Compiler",
        subtype='FILE_PATH',
        default="",
    )

    def draw(self, _: bpy.context) -> None:
        """Draw the addon preferences ui."""
        self.layout.prop(self, "compiler_path")


class TS1R_OT_set_view_north_west(bpy.types.Operator):
    """Rotates the The Sims Rotation Origin object to the north west view position"""

    bl_idname = "tsr.set_view_north_west"
    bl_label = "Set View North West"
    bl_options = {'REGISTER'}

    def execute(self, context):
        update(self, context)
        bpy.data.objects["The Sims Rotation Origin"].rotation_euler = (
            0,
            0,
            math.radians(0),
        )
        return {'FINISHED'}


class TS1R_OT_set_view_north_east(bpy.types.Operator):
    """Rotates the The Sims Rotation Origin object to the north east view position"""

    bl_idname = "tsr.set_view_north_east"
    bl_label = "Set View North East"
    bl_options = {'REGISTER'}

    def execute(self, context):
        update(self, context)
        bpy.data.objects["The Sims Rotation Origin"].rotation_euler = (
            0,
            0,
            math.radians(-90),
        )
        return {'FINISHED'}


class TS1R_OT_set_view_south_east(bpy.types.Operator):
    """Rotates the The Sims Rotation Origin object to the south east view position"""

    bl_idname = "tsr.set_view_south_east"
    bl_label = "Set View South East"
    bl_options = {'REGISTER'}

    def execute(self, context):
        update(self, context)
        bpy.data.objects["The Sims Rotation Origin"].rotation_euler = (
            0,
            0,
            math.radians(-180),
        )
        return {'FINISHED'}


class TS1R_OT_set_view_south_west(bpy.types.Operator):
    """Rotates the The Sims Rotation Origin object to the south west view position"""

    bl_idname = "tsr.set_view_south_west"
    bl_label = "Set View South West"
    bl_options = {'REGISTER'}

    def execute(self, context):
        update(self, context)
        bpy.data.objects["The Sims Rotation Origin"].rotation_euler = (
            0,
            0,
            math.radians(-270),
        )
        return {'FINISHED'}


class TS1R_OT_set_render_resolution_and_camera(bpy.types.Operator):
    """Sets the render resolution to the sprites dimensions and sets the active camera to The Sims Camera"""

    bl_idname = "tsr.set_render_resolution_and_camera"
    bl_label = "Set Render Resolution and Camera"
    bl_options = {'REGISTER'}

    def execute(self, context):
        TILE_WIDTH_HALF = 64

        BASE_SPRITE_WIDTH = 136
        BASE_SPRITE_HEIGHT = 384

        extra_tiles = (context.scene.tsr_x - 1) + (context.scene.tsr_y - 1)

        # keep the image proportional or the orthographic scale calculation
        # is thrown off when the image becomes wider than it is tall
        context.scene.render.resolution_x = BASE_SPRITE_WIDTH + (extra_tiles * TILE_WIDTH_HALF)
        context.scene.render.resolution_y = BASE_SPRITE_HEIGHT + (extra_tiles * TILE_WIDTH_HALF)

        context.scene.camera = bpy.data.objects["The Sims Camera"]
        return {'FINISHED'}


def update(self, context):
    context.scene.use_nodes = True

    depth_group_node_tree = bpy.data.node_groups.get("The Sims Renderer Pre Depth")
    if depth_group_node_tree is None:
        depth_group_node_tree = bpy.data.node_groups.new("The Sims Renderer Pre Depth", 'CompositorNodeTree')
        depth_group_node_tree.interface.new_socket(
            name="Image",
            in_out='INPUT',
            socket_type='NodeSocketColor',
        )
        depth_group_node_tree.interface.new_socket(
            name="Depth",
            in_out='INPUT',
            socket_type='NodeSocketFloat',
        )
        depth_group_node_tree.interface.new_socket(
            name="Depth",
            in_out='OUTPUT',
            socket_type='NodeSocketFloat',
        )

    depth_input_node = depth_group_node_tree.nodes.get("The Sims Depth Input")
    if depth_input_node is None:
        depth_input_node = depth_group_node_tree.nodes.new('NodeGroupInput')
        depth_input_node.location = (0, 0)
        depth_input_node.name = "The Sims Depth Input"
        depth_input_node.label = depth_input_node.name

    depth_alpha_convert_node = depth_group_node_tree.nodes.get("The Sims Depth Alpha Convert")
    if depth_alpha_convert_node is None:
        depth_alpha_convert_node = depth_group_node_tree.nodes.new(type='CompositorNodePremulKey')
        depth_alpha_convert_node.location = (200, 0)
        depth_alpha_convert_node.name = "The Sims Depth Alpha Convert"
        depth_alpha_convert_node.label = depth_alpha_convert_node.name
        depth_alpha_convert_node.mapping = 'PREMUL_TO_STRAIGHT'
        depth_group_node_tree.links.new(depth_input_node.outputs[0], depth_alpha_convert_node.inputs[0])

    depth_switch_node = depth_group_node_tree.nodes.get("The Sims Depth Switch")
    if depth_switch_node is None:
        depth_switch_node = depth_group_node_tree.nodes.new('CompositorNodeSwitch')
        depth_switch_node.location = (400, 0)
        depth_switch_node.name = "The Sims Depth Switch"
        depth_switch_node.label = depth_switch_node.name
        depth_switch_node.check = False
        depth_group_node_tree.links.new(depth_alpha_convert_node.outputs[0], depth_switch_node.inputs[0])
        depth_group_node_tree.links.new(depth_input_node.outputs[1], depth_switch_node.inputs[1])

    depth_output_node = depth_group_node_tree.nodes.get("The Sims Depth Output")
    if depth_output_node is None:
        depth_output_node = depth_group_node_tree.nodes.new('NodeGroupOutput')
        depth_output_node.location = (600, 0)
        depth_output_node.name = "The Sims Depth Output"
        depth_output_node.label = depth_output_node.name
        depth_group_node_tree.links.new(depth_switch_node.outputs[0], depth_output_node.inputs[0])

    depth_group_node = bpy.context.scene.node_tree.nodes.get("The Sims Renderer Pre Depth")
    if depth_group_node is None:
        depth_group_node = bpy.context.scene.node_tree.nodes.new('CompositorNodeGroup')
        depth_group_node.node_tree = bpy.data.node_groups["The Sims Renderer Pre Depth"]
        depth_group_node.location = (200, 0)
        depth_group_node.name = "The Sims Renderer Pre Depth"
        depth_group_node.label = depth_group_node.name
        depth_group_node.width = 200
        render_layers = bpy.context.scene.node_tree.nodes.get("Render Layers")
        if render_layers is not None:
            bpy.context.scene.node_tree.links.new(render_layers.outputs[0], depth_group_node.inputs[0])
            bpy.context.scene.node_tree.links.new(render_layers.outputs[2], depth_group_node.inputs[1])

    group_node_tree = bpy.data.node_groups.get("The Sims Renderer")
    if group_node_tree is None:
        group_node_tree = bpy.data.node_groups.new("The Sims Renderer", 'CompositorNodeTree')
        group_node_tree.interface.new_socket(
            name="Image",
            in_out='INPUT',
            socket_type='NodeSocketColor',
        )
        group_node_tree.interface.new_socket(
            name="Alpha",
            in_out='INPUT',
            socket_type='NodeSocketColor',
        )
        group_node_tree.interface.new_socket(
            name="Depth",
            in_out='INPUT',
            socket_type='NodeSocketColor',
        )

    input_node = group_node_tree.nodes.get("The Sims Input")
    if input_node is None:
        input_node = group_node_tree.nodes.new('NodeGroupInput')
        input_node.location = (0, 0)
        input_node.name = "The Sims Input"
        input_node.label = input_node.name

    alpha_convert_node = group_node_tree.nodes.get("The Sims Alpha Convert")
    if alpha_convert_node is None:
        alpha_convert_node = group_node_tree.nodes.new(type='CompositorNodePremulKey')
        alpha_convert_node.location = (156, 55)
        alpha_convert_node.name = "The Sims Alpha Convert"
        alpha_convert_node.label = alpha_convert_node.name
        alpha_convert_node.mapping = 'PREMUL_TO_STRAIGHT'

    color_output_node = group_node_tree.nodes.get("The Sims Color Output")
    if color_output_node is None:
        color_output_node = group_node_tree.nodes.new(type='CompositorNodeOutputFile')
        color_output_node.location = (312, 105)
        color_output_node.name = "The Sims Color Output"
        color_output_node.label = color_output_node.name
        color_output_node.format.file_format = 'PNG'
        color_output_node.format.color_mode = 'RGB'
        color_output_node.file_slots[0].path = "color"
        group_node_tree.links.new(alpha_convert_node.outputs[0], color_output_node.inputs[0])

    alpha_output_node = group_node_tree.nodes.get("The Sims Alpha Output")
    if alpha_output_node is None:
        alpha_output_node = group_node_tree.nodes.new(type='CompositorNodeOutputFile')
        alpha_output_node.location = (312, 0)
        alpha_output_node.name = "The Sims Alpha Output"
        alpha_output_node.label = alpha_output_node.name
        alpha_output_node.format.file_format = 'OPEN_EXR'
        alpha_output_node.format.color_mode = 'RGB'
        alpha_output_node.format.color_management = 'OVERRIDE'
        alpha_output_node.format.view_settings.view_transform = 'Raw'
        alpha_output_node.format.linear_colorspace_settings.name = 'Non-Color'
        alpha_output_node.file_slots[0].path = "alpha"

    depth_output_node = group_node_tree.nodes.get("The Sims Depth Output")
    if depth_output_node is None:
        depth_output_node = group_node_tree.nodes.new(type='CompositorNodeOutputFile')
        depth_output_node.location = (312, -105)
        depth_output_node.name = "The Sims Depth Output"
        depth_output_node.label = depth_output_node.name
        depth_output_node.format.file_format = 'OPEN_EXR'
        depth_output_node.format.color_mode = 'RGB'
        depth_output_node.format.color_management = 'OVERRIDE'
        depth_output_node.format.view_settings.view_transform = 'Raw'
        depth_output_node.format.linear_colorspace_settings.name = 'Non-Color'
        depth_output_node.file_slots[0].path = "depth"

    group_node = bpy.context.scene.node_tree.nodes.get("The Sims Renderer")
    if group_node is None:
        group_node = bpy.context.scene.node_tree.nodes.new('CompositorNodeGroup')
        group_node.node_tree = bpy.data.node_groups["The Sims Renderer"]
        group_node.location = (600, 0)
        group_node.name = "The Sims Renderer"
        group_node.label = group_node.name
        group_node.width = 200
        render_layers = bpy.context.scene.node_tree.nodes.get("Render Layers")
        if render_layers is not None:
            bpy.context.scene.node_tree.links.new(render_layers.outputs[0], group_node.inputs[0])
            bpy.context.scene.node_tree.links.new(render_layers.outputs[1], group_node.inputs[1])
        bpy.context.scene.node_tree.links.new(depth_group_node.outputs[0], group_node.inputs[2])

    the_sims_collection = bpy.data.collections.get("The Sims")
    if the_sims_collection is None:
        the_sims_collection = bpy.data.collections.new("The Sims")
        context.scene.collection.children.link(the_sims_collection)
        the_sims_collection.hide_render = True

    rotation_origin = bpy.data.objects.get("The Sims Rotation Origin")
    if rotation_origin is None:
        rotation_origin = bpy.data.objects.new("The Sims Rotation Origin", None)
        the_sims_collection.objects.link(rotation_origin)
        rotation_origin.hide_select = True
        rotation_origin.hide_set(True)
        rotation_origin.hide_render = True

    extra_tiles = (context.scene.tsr_x - 1) + (context.scene.tsr_y - 1)

    camera = context.scene.objects.get("The Sims Camera")
    if camera is None:
        camera_data = bpy.data.cameras.new(name="The Sims Camera")
        camera = bpy.data.objects.new("The Sims Camera", camera_data)
        the_sims_collection.objects.link(camera)
        camera.hide_select = True
        camera.hide_set(True)
        camera.hide_render = True

    MAX_OBJECT_HEIGHT = 4
    BASE_IMAGE_WIDTH = 128
    PADDED_IMAGE_WIDTH = BASE_IMAGE_WIDTH + 8
    BASE_ORTHO_SCALE = (2 - (BASE_IMAGE_WIDTH / PADDED_IMAGE_WIDTH)) * MAX_OBJECT_HEIGHT
    TILE_DIAGONAL_DISTANCE = math.sqrt(2)
    EXTRA_ORTHO_SCALE = TILE_DIAGONAL_DISTANCE / 2
    camera.data.ortho_scale = BASE_ORTHO_SCALE + (extra_tiles * EXTRA_ORTHO_SCALE)

    DISTANCE_IN_TILES = 17
    ISOMETRIC_PERSPECTIVE_FORESHORTENING = math.sqrt(2 / 3)
    TILE_HEIGHT = ISOMETRIC_PERSPECTIVE_FORESHORTENING
    camera_height = (DISTANCE_IN_TILES * TILE_HEIGHT) + (MAX_OBJECT_HEIGHT / 2)
    camera.location = (DISTANCE_IN_TILES, -DISTANCE_IN_TILES, camera_height)
    camera.rotation_euler = (math.radians(60), 0, math.radians(45))
    camera.parent = rotation_origin
    camera.data.type = 'ORTHO'
    camera.data.clip_start = 5
    camera.data.clip_end = TILE_DIAGONAL_DISTANCE * DISTANCE_IN_TILES * 2
    camera.data.shift_x = 0
    camera.data.shift_y = 0

    object_bounds = context.scene.objects.get("The Sims Object Bounds")
    if object_bounds is None:
        object_bounds_mesh = bpy.data.meshes.new("The Sims Object Bounds")
        object_bounds = bpy.data.objects.new("The Sims Object Bounds", object_bounds_mesh)
        the_sims_collection.objects.link(object_bounds)
        object_bounds.hide_select = True
        object_bounds.hide_set(True)
        object_bounds.hide_render = True

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(object_bounds_mesh)
        bm.free()

    object_bounds.location = (0, 0, 2)
    object_bounds.dimensions = (context.scene.tsr_x, context.scene.tsr_y, 4)


class TS1R_OT_setup(bpy.types.Operator):
    """Setup The Sims Renderer"""

    bl_idname = "tsr.setup"
    bl_label = "Setup"
    bl_options = {'REGISTER'}

    def execute(self, context):
        context.scene.frame_start = 1
        context.scene.frame_end = 1
        update(self, context)
        return {'FINISHED'}


def render_color_and_alpha(context, direction, rotation, output_dir):
    bpy.ops.render.render(animation=False)

    output_dir = bpy.path.abspath("//") + output_dir
    frame_number = "{:04d}".format(context.scene.frame_current)
    os.replace(
        output_dir + "color" + frame_number + ".png",
        output_dir + direction + "_color.png",
    )
    os.replace(
        output_dir + "alpha" + frame_number + ".exr",
        output_dir + direction + "_alpha.exr",
    )


def render_depth(context, size, direction, rotation, output_dir, extra):
    bpy.ops.render.render(animation=False)

    output_dir = bpy.path.abspath("//") + output_dir
    frame_number = "{:04d}".format(context.scene.frame_current)
    file_name = "_depth.exr" if extra is False else "_depth_extra.exr"
    os.replace(
        output_dir + "depth" + frame_number + ".exr",
        output_dir + size + "_" + direction + file_name,
    )


def render_rotation(context, direction, rotation, output_dir):
    bpy.data.objects["The Sims Rotation Origin"].rotation_euler = (
        0,
        0,
        math.radians(rotation),
    )
    context.view_layer.update()

    border_min_x = 1
    border_max_x = 0
    border_min_y = 1
    border_max_y = 0

    for obj in context.view_layer.objects:
        renderable_object_types = ['FONT', 'MESH', 'META', 'SURFACE']
        if obj.hide_render is False and obj.visible_camera and obj.type in renderable_object_types:
            vertices = [mathutils.Vector(vertex) for vertex in obj.bound_box]
            world_vertices = [obj.matrix_world @ vertex for vertex in vertices]

            object_min_x = 1
            object_max_x = 0
            object_min_y = 1
            object_max_y = 0

            for vertex in world_vertices:
                view_coord = bpy_extras.object_utils.world_to_camera_view(context.scene, context.scene.camera, vertex)
                object_min_x = min(object_min_x, view_coord[0])
                object_max_x = max(object_max_x, view_coord[0])
                object_min_y = min(object_min_y, view_coord[1])
                object_max_y = max(object_max_y, view_coord[1])

            border_min_x = min(border_min_x, object_min_x)
            border_max_x = max(border_max_x, object_max_x)
            border_min_y = min(border_min_y, object_min_y)
            border_max_y = max(border_max_y, object_max_y)

    BORDER_PADDING = 0.01
    context.scene.render.border_min_x = max(0, border_min_x - BORDER_PADDING)
    context.scene.render.border_max_x = min(1, border_max_x + BORDER_PADDING)
    context.scene.render.border_min_y = max(0, border_min_y - BORDER_PADDING)
    context.scene.render.border_max_y = min(1, border_max_y + BORDER_PADDING)

    render_group_node_tree = context.scene.node_tree.nodes.get("The Sims Renderer").node_tree
    input_node = render_group_node_tree.nodes.get("The Sims Input")
    alpha_convert_node = render_group_node_tree.nodes.get("The Sims Alpha Convert")
    color_output_node = render_group_node_tree.nodes.get("The Sims Color Output")
    alpha_output_node = render_group_node_tree.nodes.get("The Sims Alpha Output")
    depth_alpha_convert_node = render_group_node_tree.nodes.get("The Sims Depth Alpha Convert")
    depth_output_node = render_group_node_tree.nodes.get("The Sims Depth Output")

    depth_group_node_tree = context.scene.node_tree.nodes.get("The Sims Renderer Pre Depth").node_tree
    depth_switch_node = depth_group_node_tree.nodes.get("The Sims Depth Switch")

    render_group_node_tree.links.new(input_node.outputs[2], depth_output_node.inputs[0])

    depth_switch_node.check = hasattr(bpy.app, "tsr_depth")

    output_dir_relative = "//" + output_dir

    color_output_node.base_path = output_dir_relative
    alpha_output_node.base_path = output_dir_relative
    depth_output_node.base_path = output_dir_relative

    original_eevee_filter_width = context.scene.render.filter_size

    original_cycles_max_bounces = context.scene.cycles.max_bounces
    context.scene.cycles.max_bounces = 0
    original_cycles_filter_width = context.scene.cycles.filter_width
    context.scene.cycles.filter_width = 1
    original_cycles_use_denoising = context.scene.cycles.use_denoising
    context.scene.cycles.use_denoising = False
    original_cycles_use_adaptive_sampling = context.scene.cycles.use_adaptive_sampling
    context.scene.cycles.use_adaptive_sampling = False

    original_cycles_samples = context.scene.cycles.samples

    context.view_layer.material_override = bpy.data.materials["The Sims Depth Override"]

    original_resolution_percentage = context.scene.render.resolution_percentage

    if hasattr(bpy.app, "tsr_depth") is False:
        context.scene.cycles.samples = 1

    context.scene.render.resolution_percentage = 25
    render_depth(context, "small", direction, rotation, output_dir, False)
    context.scene.render.resolution_percentage = 50
    render_depth(context, "medium", direction, rotation, output_dir, False)
    context.scene.render.resolution_percentage = 100
    render_depth(context, "large", direction, rotation, output_dir, False)

    context.scene.cycles.samples = original_cycles_samples

    if hasattr(bpy.app, "tsr_depth") is False:
        context.scene.render.resolution_percentage = 25
        render_depth(context, "small", direction, rotation, output_dir, True)
        context.scene.render.resolution_percentage = 50
        render_depth(context, "medium", direction, rotation, output_dir, True)
        context.scene.render.resolution_percentage = 100
        render_depth(context, "large", direction, rotation, output_dir, True)

    render_group_node_tree.links.remove(input_node.outputs[2].links[0])

    context.view_layer.material_override = None

    context.scene.cycles.use_adaptive_sampling = original_cycles_use_adaptive_sampling
    context.scene.cycles.use_denoising = original_cycles_use_denoising
    context.scene.cycles.filter_width = original_cycles_filter_width
    context.scene.cycles.max_bounces = original_cycles_max_bounces

    render_group_node_tree.links.new(input_node.outputs[0], alpha_convert_node.inputs[0])
    render_group_node_tree.links.new(input_node.outputs[1], alpha_output_node.inputs[0])

    context.scene.render.resolution_percentage = 200
    render_color_and_alpha(context, direction, rotation, output_dir)

    render_group_node_tree.links.remove(input_node.outputs[0].links[0])
    render_group_node_tree.links.remove(input_node.outputs[1].links[0])

    context.scene.render.resolution_percentage = original_resolution_percentage


def render_frames(context, object_name):
    context.scene.tsr_frame_range_start = min(context.scene.tsr_frame_range_start, context.scene.frame_start)
    context.scene.tsr_frame_range_end = max(context.scene.tsr_frame_range_end, context.scene.frame_end)

    for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
        context.scene.frame_set(frame)

        frame_name = "{}".format(frame)
        for marker in context.scene.timeline_markers:
            if marker.frame == frame:
                frame_name = marker.name

        frame_directory = object_name + " - full sprites/" + frame_name + "/"

        frame_directory_abs = bpy.path.abspath("//") + frame_directory
        if os.path.isdir(frame_directory_abs):
            shutil.rmtree(frame_directory_abs)

        if context.scene.tsr_render_nw:
            render_rotation(context, "nw", 0, frame_directory)
        if context.scene.tsr_render_ne:
            render_rotation(context, "ne", -90, frame_directory)
        if context.scene.tsr_render_se:
            render_rotation(context, "se", -180, frame_directory)
        if context.scene.tsr_render_sw:
            render_rotation(context, "sw", -270, frame_directory)


def is_gltf_variants_enabled(context):
    return (
        "io_scene_gltf2" in context.preferences.addons
        and context.preferences.addons["io_scene_gltf2"].preferences.KHR_materials_variants_ui
    )


class TS1R_OT_render(bpy.types.Operator):
    """Render all frames in the current frame range"""

    bl_idname = "tsr.render"
    bl_label = "Render"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if context.scene.render.engine != "CYCLES":
            self.report({'ERROR'}, "Rendering is only supported with Cycles")
            return {'FINISHED'}

        if bpy.path.display_name_from_filepath(context.blend_data.filepath) == "":
            self.report({'ERROR'}, "Please save your blend file")
            return {'FINISHED'}

        update(self, context)

        original_frame = context.scene.frame_current
        original_rotation = copy.copy(bpy.data.objects["The Sims Rotation Origin"].rotation_euler)
        original_render_film_transparent = context.scene.render.film_transparent
        original_view_layer_use_pass_z = context.view_layer.use_pass_z
        original_camera = context.scene.camera
        original_render_resolution_x = context.scene.render.resolution_x
        original_render_resolution_y = context.scene.render.resolution_y
        original_render_use_border = context.scene.render.use_border
        original_render_use_crop_to_border = context.scene.render.use_crop_to_border
        original_render_border_min_x = context.scene.render.border_min_x
        original_render_border_max_x = context.scene.render.border_max_x
        original_render_border_min_y = context.scene.render.border_min_y
        original_render_border_max_y = context.scene.render.border_max_y

        context.scene.render.film_transparent = True
        context.view_layer.use_pass_z = True

        context.scene.render.use_border = True
        context.scene.render.use_crop_to_border = False

        bpy.ops.tsr.set_render_resolution_and_camera()

        depth_override_material = bpy.data.materials.new(name="The Sims Depth Override")
        depth_override_material.use_nodes = True
        depth_override_material.node_tree.nodes.remove(depth_override_material.node_tree.nodes["Principled BSDF"])

        if hasattr(bpy.app, "tsr_depth") is False:
            camera_data_node = depth_override_material.node_tree.nodes.new(type='ShaderNodeCameraData')
            depth_override_material.node_tree.links.new(
                camera_data_node.outputs[1],
                depth_override_material.node_tree.nodes["Material Output"].inputs[0],
            )

        object_name = bpy.path.display_name_from_filepath(context.blend_data.filepath)

        if is_gltf_variants_enabled(context) and len(context.scene.gltf2_KHR_materials_variants_variants) > 0:
            if context.scene.gltf2_active_variant >= len(context.scene.gltf2_KHR_materials_variants_variants):
                context.scene.gltf2_active_variant = len(context.scene.gltf2_KHR_materials_variants_variants) - 1

            original_variant = context.scene.gltf2_active_variant

            for variant in context.scene.gltf2_KHR_materials_variants_variants:
                if (
                    context.scene.tsr_render_all_variants == False
                    and variant.variant_idx != context.scene.gltf2_active_variant
                ):
                    continue
                variant_object_name = object_name + " - " + variant.name
                context.scene.gltf2_active_variant = variant.variant_idx
                bpy.ops.scene.gltf2_display_variant()
                render_frames(context, variant_object_name)

            context.scene.gltf2_active_variant = original_variant
            bpy.ops.scene.gltf2_display_variant()
        else:
            render_frames(context, object_name)

        context.scene.frame_current = original_frame
        bpy.data.objects["The Sims Rotation Origin"].rotation_euler = original_rotation
        context.scene.render.film_transparent = original_render_film_transparent
        context.view_layer.use_pass_z = original_view_layer_use_pass_z
        context.scene.camera = original_camera
        context.scene.render.resolution_x = original_render_resolution_x
        context.scene.render.resolution_y = original_render_resolution_y
        context.scene.render.use_border = original_render_use_border
        context.scene.render.use_crop_to_border = original_render_use_crop_to_border
        context.scene.render.border_min_x = original_render_border_min_x
        context.scene.render.border_max_x = original_render_border_max_x
        context.scene.render.border_min_y = original_render_border_min_y
        context.scene.render.border_max_y = original_render_border_max_y

        bpy.data.materials.remove(depth_override_material)

        if context.scene.tsr_auto_split:
            bpy.ops.tsr.split()

        return {'FINISHED'}


def write_object_description(context):
    original_frame = context.scene.frame_current

    object_description = dict()
    object_description["dimensions"] = {
        "x": context.scene.tsr_x,
        "y": context.scene.tsr_y,
    }
    frame_id_map = list()

    for frame in range(context.scene.tsr_frame_range_start, context.scene.tsr_frame_range_end + 1):
        context.scene.frame_set(frame)
        frame_name = "{}".format(frame)
        for marker in context.scene.timeline_markers:
            if marker.frame == frame:
                frame_name = marker.name

        frame_id_map.append(
            {
                "name": frame_name,
                "sprite_id": context.scene.tsr_sprite_id,
                "sprite_id_reverse_x": context.scene.tsr_sprite_id_reverse_x,
                "sprite_id_reverse_y": context.scene.tsr_sprite_id_reverse_y,
                "palette_id": context.scene.tsr_palette_id,
            }
        )

    context.scene.frame_current = original_frame

    object_description["frames"] = frame_id_map

    source_directory = bpy.path.abspath("//")
    object_name = bpy.path.display_name_from_filepath(bpy.context.blend_data.filepath)

    with open(
        source_directory + object_name + " - object description.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(object_description, file, ensure_ascii=False, indent=2)


def split_frames(self, context, source_directory, object_name, variant):
    write_object_description(context)

    compiler_path = bpy.path.abspath(context.preferences.addons["render_ts1"].preferences.compiler_path)

    if variant is None:
        result = subprocess.run(
            [
                compiler_path,
                "split",
                source_directory,
                object_name,
            ],
            capture_output=True,
            text=True,
        )
        if result.stderr != "":
            self.report({'ERROR'}, result.stderr)
    else:
        result = subprocess.run(
            [
                compiler_path,
                "split",
                source_directory,
                object_name,
                "-v",
                variant,
            ],
            capture_output=True,
            text=True,
        )
        if result.stderr != "":
            self.report({'ERROR'}, result.stderr)


class TS1R_OT_split(bpy.types.Operator):
    """Split rendered images in to sprites"""

    bl_idname = "tsr.split"
    bl_label = "Split"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if bpy.path.display_name_from_filepath(context.blend_data.filepath) == "":
            self.report({'ERROR'}, "Please save your blend file")
            return {'FINISHED'}

        compiler_path = bpy.path.abspath(context.preferences.addons["render_ts1"].preferences.compiler_path)

        if os.path.isfile(compiler_path) is False:
            self.report({'ERROR'}, "Please set the path to the compiler in the add-on preferences")
            return {'FINISHED'}

        source_directory = bpy.path.abspath("//")
        blender_file_name = bpy.path.display_name_from_filepath(bpy.context.blend_data.filepath)

        if is_gltf_variants_enabled(context) and len(context.scene.gltf2_KHR_materials_variants_variants) > 0:
            if context.scene.gltf2_active_variant >= len(context.scene.gltf2_KHR_materials_variants_variants):
                context.scene.gltf2_active_variant = len(context.scene.gltf2_KHR_materials_variants_variants) - 1

            for variant in context.scene.gltf2_KHR_materials_variants_variants:
                if (
                    context.scene.tsr_render_all_variants == False
                    and variant.variant_idx != context.scene.gltf2_active_variant
                ):
                    continue
                split_frames(self, context, source_directory, blender_file_name, variant.name)

        else:
            split_frames(self, context, source_directory, blender_file_name, None)

        if context.scene.tsr_auto_update_xml:
            bpy.ops.tsr.update_xml()

        elif context.scene.tsr_auto_compile:
            if context.scene.tsr_use_advanced_compile:
                bpy.ops.tsr.compile_advanced()
            else:
                bpy.ops.tsr.compile()

        return {'FINISHED'}


class TS1R_OT_update_xml(bpy.types.Operator):
    """Update the object XML file with the split sprites"""

    bl_idname = "tsr.update_xml"
    bl_label = "Update XML"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if bpy.path.display_name_from_filepath(context.blend_data.filepath) == "":
            self.report({'ERROR'}, "Please save your blend file")
            return {'FINISHED'}

        compiler_path = bpy.path.abspath(context.preferences.addons["render_ts1"].preferences.compiler_path)

        if os.path.isfile(compiler_path) is False:
            self.report({'ERROR'}, "Please set the path to the compiler in the add-on preferences")
            return {'FINISHED'}

        source_directory = bpy.path.abspath("//")
        object_name = bpy.path.display_name_from_filepath(bpy.context.blend_data.filepath)
        variant_name = None

        if is_gltf_variants_enabled(context) and len(context.scene.gltf2_KHR_materials_variants_variants) > 0:
            variant_name = context.scene.gltf2_KHR_materials_variants_variants[0].name

        if variant_name is None:
            result = subprocess.run(
                [
                    compiler_path,
                    "update-xml",
                    source_directory,
                    object_name,
                ],
                capture_output=True,
                text=True,
            )
            if result.stderr != "":
                self.report({'ERROR'}, result.stderr)
        else:
            result = subprocess.run(
                [
                    compiler_path,
                    "update-xml",
                    source_directory,
                    object_name,
                    "-v",
                    variant_name,
                ],
                capture_output=True,
                text=True,
            )
            if result.stderr != "":
                self.report({'ERROR'}, result.stderr)

        if context.scene.tsr_auto_compile:
            if context.scene.tsr_use_advanced_compile:
                bpy.ops.tsr.compile_advanced()
            else:
                bpy.ops.tsr.compile()

        return {'FINISHED'}


class TS1R_OT_compile(bpy.types.Operator):
    """Compile the xml file in to the final iff file"""

    bl_idname = "tsr.compile"
    bl_label = "Compile"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if bpy.path.display_name_from_filepath(context.blend_data.filepath) == "":
            self.report({'ERROR'}, "Please save your blend file")
            return {'FINISHED'}

        compiler_path = bpy.path.abspath(context.preferences.addons["render_ts1"].preferences.compiler_path)

        if os.path.isfile(compiler_path) is False:
            self.report({'ERROR'}, "Please set the path to the compiler in the add-on preferences")
            return {'FINISHED'}

        source_directory = bpy.path.abspath("//")
        blender_file_name = bpy.path.display_name_from_filepath(context.blend_data.filepath) + ".xml"
        xml_file_path = os.path.join(source_directory, blender_file_name)

        result = subprocess.run(
            [
                compiler_path,
                "compile",
                xml_file_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.stderr != "":
            self.report({'ERROR'}, result.stderr)

        return {'FINISHED'}


class TS1R_OT_compile_advanced(bpy.types.Operator):
    """Compile the xml file in to the final iff file"""

    bl_idname = "tsr.compile_advanced"
    bl_label = "Compile"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if bpy.path.display_name_from_filepath(context.blend_data.filepath) == "":
            self.report({'ERROR'}, "Please save your blend file")
            return {'FINISHED'}

        compiler_path = bpy.path.abspath(context.preferences.addons["render_ts1"].preferences.compiler_path)

        if os.path.isfile(compiler_path) is False:
            self.report({'ERROR'}, "Please set the path to the compiler in the add-on preferences")
            return {'FINISHED'}

        if context.scene.tsr_creator_name == "":
            self.report({'ERROR'}, "Please enter your name")
            return {'FINISHED'}

        if context.scene.tsr_format_string == "":
            self.report({'ERROR'}, "Please enter a formatting string")
            return {'FINISHED'}

        source_directory = bpy.path.abspath("//")

        if is_gltf_variants_enabled(context) and len(context.scene.gltf2_KHR_materials_variants_variants) > 0:
            if context.scene.gltf2_active_variant >= len(context.scene.gltf2_KHR_materials_variants_variants):
                context.scene.gltf2_active_variant = len(context.scene.gltf2_KHR_materials_variants_variants) - 1

            for variant in context.scene.gltf2_KHR_materials_variants_variants:
                if (
                    context.scene.tsr_compile_all_variants == False
                    and variant.variant_idx != context.scene.gltf2_active_variant
                ):
                    continue

                first_variant_name = context.scene.gltf2_KHR_materials_variants_variants[0].name

                result = subprocess.run(
                    [
                        compiler_path,
                        "compile-advanced",
                        source_directory,
                        context.scene.tsr_format_string,
                        context.scene.tsr_creator_name,
                        bpy.path.display_name_from_filepath(context.blend_data.filepath),
                        first_variant_name,
                        variant.name,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.stderr != "":
                    self.report({'ERROR'}, result.stderr)
        else:
            result = subprocess.run(
                [
                    compiler_path,
                    "compile-advanced",
                    source_directory,
                    context.scene.tsr_format_string,
                    context.scene.tsr_creator_name,
                    bpy.path.display_name_from_filepath(context.blend_data.filepath),
                ],
                capture_output=True,
                text=True,
            )
            if result.stderr != "":
                self.report({'ERROR'}, result.stderr)

        return {'FINISHED'}


class TS1R_OT_add_rotations(bpy.types.Operator):
    """Add all 4 rotations to the draw groups in the object's XML file"""

    bl_idname = "tsr.add_rotations"
    bl_label = "Add Rotations"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if bpy.path.display_name_from_filepath(context.blend_data.filepath) == "":
            self.report({'ERROR'}, "Please save your blend file")
            return {'FINISHED'}

        compiler_path = bpy.path.abspath(context.preferences.addons["render_ts1"].preferences.compiler_path)

        if os.path.isfile(compiler_path) is False:
            self.report({'ERROR'}, "Please set the path to the compiler in the add-on preferences")
            return {'FINISHED'}

        source_directory = bpy.path.abspath("//")
        blender_file_name = bpy.path.display_name_from_filepath(context.blend_data.filepath) + ".xml"
        xml_file_path = os.path.join(source_directory, blender_file_name)

        result = subprocess.run(
            [
                compiler_path,
                "add-rotations",
                xml_file_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout != "":
            for line in result.stdout.splitlines():
                self.report({'INFO'}, line)
        if result.stderr != "":
            self.report({'ERROR'}, result.stderr)

        return {'FINISHED'}


class TS1R_PT_the_sims_renderer_panel(bpy.types.Panel):
    bl_label = "The Sims Renderer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "The Sims"

    def draw(self, context):
        if (
            context.scene.objects.get("The Sims Rotation Origin") is None
            and bpy.data.meshes.get("The Sims Rotation Origin") is not None
        ):
            col = self.layout.column(align=True)
            col.label(text="Can only be used in one scene.")
            return

        if context.scene.objects.get("The Sims Rotation Origin") is None:
            setup_button = self.layout.column(align=True)
            setup_button.operator("tsr.setup", text="Setup")
            return

        dimensions = self.layout.split(align=True)
        dimensions.prop(context.scene, "tsr_x", text="X")
        dimensions.prop(context.scene, "tsr_y", text="Y")

        set_resolution_and_camera_button = self.layout.column(align=True)
        set_resolution_and_camera_button.operator(
            "tsr.set_render_resolution_and_camera",
            text="Set resolution and camera",
        )

        compass = self.layout.grid_flow(align=True, columns=2, row_major=True)
        compass.operator("tsr.set_view_north_west", text="NW")
        compass.operator("tsr.set_view_north_east", text="NE")
        compass.operator("tsr.set_view_south_west", text="SW")
        compass.operator("tsr.set_view_south_east", text="SE")

        render_compass = self.layout.grid_flow(align=True, columns=2, row_major=True)
        render_compass.prop(context.scene, "tsr_render_nw")
        render_compass.prop(context.scene, "tsr_render_ne")
        render_compass.prop(context.scene, "tsr_render_sw")
        render_compass.prop(context.scene, "tsr_render_se")

        add_rotations = self.layout.column()
        add_rotations.operator("tsr.add_rotations", text="Add Rotations")

        sprite_id_box = self.layout.box()

        sprite_id = sprite_id_box.column(align=True)
        sprite_id.prop(context.scene, "tsr_sprite_id")

        sprite_id_rev = sprite_id.grid_flow(align=True, columns=2, row_major=True)
        sprite_id_rev.prop(context.scene, "tsr_sprite_id_reverse_x", text="Reverse X")
        sprite_id_rev.prop(context.scene, "tsr_sprite_id_reverse_y", text="Reverse Y")

        palette_id = self.layout.column(align=True)
        palette_id.prop(context.scene, "tsr_palette_id")

        frame_range = self.layout.column(align=True)
        frame_range.prop(context.scene, "tsr_frame_range_start")
        frame_range.prop(
            context.scene,
            "tsr_frame_range_end",
        )

        if is_gltf_variants_enabled(context) and len(context.scene.gltf2_KHR_materials_variants_variants) > 0:
            render_all_variants = self.layout.column(align=True)
            render_all_variants.prop(context.scene, "tsr_render_all_variants")

        render_button = self.layout.column(align=True)
        render_button.operator("tsr.render", text="Render")

        split = self.layout.split(factor=0.7)
        split.operator("tsr.split", text="Split")
        split.prop(context.scene, "tsr_auto_split", text="Auto")

        update = self.layout.split(factor=0.7)
        update.operator("tsr.update_xml", text="Update XML")
        update.prop(context.scene, "tsr_auto_update_xml", text="Auto")

        compile_button = self.layout.split(factor=0.7)
        if context.scene.tsr_use_advanced_compile:
            compile_button.operator("tsr.compile_advanced", text="Compile")
        else:
            compile_button.operator("tsr.compile", text="Compile")
        compile_button.prop(context.scene, "tsr_auto_compile", text="Auto")

        advanced_compile_box = self.layout.box()
        use_advanced_compile = advanced_compile_box.column(align=True)
        use_advanced_compile.prop(context.scene, "tsr_use_advanced_compile")

        if context.scene.tsr_use_advanced_compile:
            creator_name = advanced_compile_box.column(align=True)
            creator_name.label(text="Creator name:")
            creator_name.prop(context.scene, "tsr_creator_name")

            format_string = advanced_compile_box.column(align=True)
            format_string.label(text="Format string:")
            format_string.prop(context.scene, "tsr_format_string")

            if is_gltf_variants_enabled(context) and len(context.scene.gltf2_KHR_materials_variants_variants) > 0:
                compile_all_variants = advanced_compile_box.column(align=True)
                compile_all_variants.prop(context.scene, "tsr_compile_all_variants")

            if is_gltf_variants_enabled(context):
                self.layout.label(text="glTF Material Variants")
                bpy.types.SCENE_PT_gltf2_variants.draw(self, context)


classes = (
    TS1R_addon_preferences,
    TS1R_OT_setup,
    TS1R_OT_set_view_north_west,
    TS1R_OT_set_view_north_east,
    TS1R_OT_set_view_south_east,
    TS1R_OT_set_view_south_west,
    TS1R_OT_set_render_resolution_and_camera,
    TS1R_OT_render,
    TS1R_OT_split,
    TS1R_OT_update_xml,
    TS1R_OT_compile,
    TS1R_OT_compile_advanced,
    TS1R_OT_add_rotations,
    TS1R_PT_the_sims_renderer_panel,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.tsr_x = bpy.props.IntProperty(
        name="X Dimension",
        description="X dimension in tiles",
        default=1,
        min=1,
        max=32,
        update=update,
        options=set(),
    )
    bpy.types.Scene.tsr_y = bpy.props.IntProperty(
        name="Y Dimension",
        description="Y Dimension in tiles",
        default=1,
        min=1,
        max=32,
        update=update,
        options=set(),
    )

    bpy.types.Scene.tsr_render_nw = bpy.props.BoolProperty(
        name="Render NW",
        description="Render the north west view",
        default=True,
    )
    bpy.types.Scene.tsr_render_ne = bpy.props.BoolProperty(
        name="Render NE",
        description="Render the north east view",
        default=True,
    )
    bpy.types.Scene.tsr_render_se = bpy.props.BoolProperty(
        name="Render SE",
        description="Render the south east view",
        default=True,
    )
    bpy.types.Scene.tsr_render_sw = bpy.props.BoolProperty(
        name="Render SW",
        description="Render the south west view",
        default=True,
    )

    bpy.types.Scene.tsr_frame_range_start = bpy.props.IntProperty(
        name="Frame Range Start",
        description="The start of the range of frames. This will update automatically but you will need to manually reduce the range if you remove frames",
        default=1,
        options=set(),
    )

    bpy.types.Scene.tsr_frame_range_end = bpy.props.IntProperty(
        name="Frame Range End",
        description="The end of the range of frames. This will update automatically but you will need to manually reduce the range if you remove frames",
        default=1,
        options=set(),
    )

    bpy.types.Scene.tsr_sprite_id = bpy.props.IntProperty(
        name="Base Sprite ID",
        description="The base sprite ID for this frame. Tiles of multi tile objects will have successive IDs, counting up the x axis, then the y. Each frames ID needs to be at least X*Y apart from eachother. Make sure to keyframe this for every frame",
        default=0,
    )
    bpy.types.Scene.tsr_sprite_id_reverse_x = bpy.props.BoolProperty(
        name="Sprite ID Reverse X",
        description="Reverse the generated sprite ID for multi tile objects on the x axis",
        default=False,
    )
    bpy.types.Scene.tsr_sprite_id_reverse_y = bpy.props.BoolProperty(
        name="Sprite ID Reverse Y",
        description="Reverse the generated sprite ID for multi tile objects on the y axis",
        default=False,
    )

    bpy.types.Scene.tsr_palette_id = bpy.props.IntProperty(
        name="Palette ID",
        description="The palette ID for this frame. Frames with the same ID will share a single palette. Make sure to keyframe this for every frame",
        default=0,
    )

    bpy.types.Scene.tsr_auto_split = bpy.props.BoolProperty(
        name="Auto Split",
        description="Automatically split after rendering",
        default=False,
        options=set(),
    )
    bpy.types.Scene.tsr_auto_update_xml = bpy.props.BoolProperty(
        name="Auto Update XML",
        description="Automatically update xml after splitting",
        default=False,
        options=set(),
    )
    bpy.types.Scene.tsr_auto_compile = bpy.props.BoolProperty(
        name="Auto Compile",
        description="Automatically compile after splitting or updating xml",
        default=False,
        options=set(),
    )

    bpy.types.Scene.tsr_use_advanced_compile = bpy.props.BoolProperty(
        name="Advanced Compile",
        description="Use the compilers advanced setting, allowing color variants",
        default=False,
        options=set(),
    )

    bpy.types.Scene.tsr_creator_name = bpy.props.StringProperty(
        name="",
        description="Your name",
        default="",
        options=set(),
    )

    bpy.types.Scene.tsr_format_string = bpy.props.StringProperty(
        name="",
        description="Format string for the iff file name. {name} {hash} {object} {variant} available",
        default="{name}{object}{variant}",
        options=set(),
    )

    bpy.types.Scene.tsr_render_all_variants = bpy.props.BoolProperty(
        name="Render All Variants",
        description="Render all variants or just the currently selected one",
        default=False,
        options=set(),
    )
    bpy.types.Scene.tsr_compile_all_variants = bpy.props.BoolProperty(
        name="Compile All Variants",
        description="Compile all variants or just the currently selected one",
        default=False,
        options=set(),
    )


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    del bpy.types.Scene.tsr_x
    del bpy.types.Scene.tsr_y

    del bpy.types.Scene.tsr_render_nw
    del bpy.types.Scene.tsr_render_ne
    del bpy.types.Scene.tsr_render_se
    del bpy.types.Scene.tsr_render_sw

    del bpy.types.Scene.tsr_frame_range_start
    del bpy.types.Scene.tsr_frame_range_end

    del bpy.types.Scene.tsr_sprite_id
    del bpy.types.Scene.tsr_sprite_id_reverse_x
    del bpy.types.Scene.tsr_sprite_id_reverse_y

    del bpy.types.Scene.tsr_palette_id

    del bpy.types.Scene.tsr_auto_split
    del bpy.types.Scene.tsr_auto_update_xml
    del bpy.types.Scene.tsr_auto_compile

    del bpy.types.Scene.tsr_use_advanced_compile

    del bpy.types.Scene.tsr_creator_name

    del bpy.types.Scene.tsr_format_string

    del bpy.types.Scene.tsr_render_all_variants
    del bpy.types.Scene.tsr_compile_all_variants


if __name__ == "__main__":
    register()
