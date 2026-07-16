"""
render_animation.py — Cameras, lighting and automated rendering.

Sets up world lighting (HDRI if supplied, otherwise a procedural sky + sun),
places one of several cameras (chase vessel, underwater, orbit, static) and
renders the baked animation to an MP4 (or a PNG sequence).
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

from config import SceneParams


def setup_world(scene: SceneParams):
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")

    if scene.use_hdri and scene.hdri_path and os.path.exists(scene.hdri_path):
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(scene.hdri_path)
        bg = nt.nodes.new("ShaderNodeBackground")
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    else:
        # Procedural sky.
        sky = nt.nodes.new("ShaderNodeTexSky")
        if hasattr(sky, "sky_type"):
            sky.sky_type = 'NISHITA'
            sky.sun_elevation = math.radians(25)
            sky.sun_rotation = math.radians(120)
        bg = nt.nodes.new("ShaderNodeBackground")
        bg.inputs["Strength"].default_value = 1.0
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # Key sun for crisp specular glints on the water.
    if "Sun" not in bpy.data.objects:
        light = bpy.data.lights.new("Sun", type='SUN')
        light.energy = 3.0
        sun = bpy.data.objects.new("Sun", light)
        sun.rotation_euler = (math.radians(50), 0, math.radians(120))
        bpy.context.collection.objects.link(sun)


def _new_camera(name, loc, target=None) -> bpy.types.Object:
    cam_data = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = loc
    if target is not None:
        d = (Vector(target) - Vector(loc))
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return cam


def setup_camera(scene: SceneParams, buoy_root: bpy.types.Object):
    """Place and (for chase/orbit) animate a camera, set it active."""
    mode = scene.camera
    scn = bpy.context.scene
    frame_end = scene.frame_end

    if mode == "underwater":
        cam = _new_camera("Cam_Underwater", (3.5, -3.5, -1.2), (0, 0, -0.5))
        cam.data.lens = 18
    elif mode == "static":
        cam = _new_camera("Cam_Static", (12, -12, 4), (0, 0, 0.5))
        cam.data.lens = 50
    elif mode == "orbit":
        cam = _new_camera("Cam_Orbit", (10, 0, 3), (0, 0, 0.5))
        cam.data.lens = 40
        # Orbit via a parented empty spun over the timeline.
        pivot = bpy.data.objects.new("CamPivot", None)
        bpy.context.collection.objects.link(pivot)
        cam.parent = pivot
        pivot.rotation_euler = (0, 0, 0)
        pivot.keyframe_insert("rotation_euler", frame=1)
        pivot.rotation_euler = (0, 0, math.radians(120))
        pivot.keyframe_insert("rotation_euler", frame=frame_end)
        _track_to(cam, buoy_root)
    else:  # chase vessel
        cam = _new_camera("Cam_Chase", (9, -9, 3.2), (0, 0, 0.5))
        cam.data.lens = 35
        # Subtle boat-like bob on the chase camera.
        for f in range(1, frame_end + 1, max(1, scene.fps // 4)):
            t = f / scene.fps
            cam.location = (9 + 0.4 * math.sin(t * 0.7),
                            -9 + 0.3 * math.cos(t * 0.5),
                            3.2 + 0.25 * math.sin(t * 0.9))
            cam.keyframe_insert("location", frame=f)
        _track_to(cam, buoy_root)

    scn.camera = cam
    return cam


def _track_to(cam, target):
    con = cam.constraints.new(type='TRACK_TO')
    con.target = target
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'


def render(scene: SceneParams, output_path: str, animation: bool = True):
    scn = bpy.context.scene
    scn.frame_start = 1
    scn.frame_end = scene.frame_end
    scn.render.fps = scene.fps

    try:
        scn.render.engine = scene.engine
    except TypeError:
        scn.render.engine = 'BLENDER_EEVEE_NEXT'  # Blender 4.2+

    if scn.render.engine.startswith("CYCLES"):
        scn.cycles.samples = scene.samples
    else:
        if hasattr(scn, "eevee"):
            scn.eevee.taa_render_samples = scene.samples

    scn.render.resolution_x = scene.resolution_x
    scn.render.resolution_y = scene.resolution_y
    scn.render.image_settings.file_format = 'FFMPEG'
    scn.render.ffmpeg.format = 'MPEG4'
    scn.render.ffmpeg.codec = 'H264'
    scn.render.ffmpeg.constant_rate_factor = 'HIGH'
    scn.render.filepath = output_path

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    bpy.ops.render.render(animation=animation)
