"""
ocean_generator.py — Configurable Sea State 0-6 ocean surface.

Creates a large ocean plane driven by Blender's Ocean modifier, mapped from the
requested ``SeaState`` (Hs, Tp, heading). The modifier's ``time`` is driven from
the scene frame so the surface animates during render. A glass-like water
material is attached.

The Ocean modifier gives the *visual* sea surface. The buoy is glued to this
exact evaluated surface by the hydrodynamics module (raycasting against it), so
the visible waves and the buoy motion stay consistent.
"""

from __future__ import annotations

import math

import bpy

from config import SeaState, SceneParams


def _water_material() -> bpy.types.Material:
    mat = bpy.data.materials.get("Ocean_mat") or bpy.data.materials.new("Ocean_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.02, 0.09, 0.13, 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.06
        if "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 0.85
        elif "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = 0.85
        if "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = 1.333
    return mat


def _hs_to_wind(hs: float) -> float:
    """Empirical map from significant wave height to Ocean-modifier wind speed.

    The Ocean modifier is a Phillips/JONSWAP-like generator whose amplitude
    scales strongly with wind velocity. This heuristic reproduces the target
    Hs closely enough for previsualisation (verified against modifier output
    for the preset table).
    """
    return max(1.0, 6.5 * math.sqrt(max(hs, 0.0)))


def build(sea: SeaState, scene: SceneParams) -> bpy.types.Object:
    """Create/replace the ocean object and return it."""
    clear_ocean()

    bpy.ops.mesh.primitive_plane_add(size=scene.ocean_size, location=(0, 0, 0))
    ocean = bpy.context.active_object
    ocean.name = "Ocean"

    mod = ocean.modifiers.new(name="Ocean", type='OCEAN')
    mod.geometry_mode = 'GENERATE'
    mod.resolution = scene.ocean_resolution
    mod.spatial_size = scene.ocean_spatial
    if hasattr(mod, "spectrum"):
        mod.spectrum = 'JONSWAP'
    if hasattr(mod, "sharpen_peak_jonswap"):
        mod.sharpen_peak_jonswap = max(0.0, (sea.gamma - 1.0) / 6.0)
    if hasattr(mod, "fetch_jonswap"):
        mod.fetch_jonswap = 120.0

    mod.wind_velocity = _hs_to_wind(sea.hs)
    mod.wave_scale = max(0.2, sea.hs)
    mod.wave_scale_min = max(0.01, sea.peak_wavelength * 0.02)
    mod.choppiness = sea.choppiness
    mod.wave_alignment = 0.65          # bias waves toward the wind direction
    mod.wind_velocity_angle = math.radians(sea.wind_dir_deg) \
        if hasattr(mod, "wind_velocity_angle") else 0.0
    if hasattr(mod, "wave_direction"):
        mod.wave_direction = math.radians(sea.wind_dir_deg)
    mod.damping = 0.5
    mod.random_seed = scene.seed

    # Foam (visual cue for higher sea states).
    if hasattr(mod, "use_foam"):
        mod.use_foam = sea.index >= 3
        if mod.use_foam:
            mod.foam_coverage = -0.3 + 0.15 * sea.index

    # Drive modifier time from the scene frame: time = frame / fps.
    drv = mod.driver_add("time").driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = "f"
    var.targets[0].id_type = 'SCENE'
    var.targets[0].id = bpy.context.scene
    var.targets[0].data_path = "frame_current"
    drv.expression = f"f / {float(scene.fps)}"

    ocean.data.materials.append(_water_material())
    for p in ocean.data.polygons:
        p.use_smooth = True

    ocean["sea_index"] = sea.index
    ocean["hs"] = sea.hs
    ocean["tp"] = sea.tp
    return ocean


def clear_ocean():
    for name in ("Ocean",):
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
