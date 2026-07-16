"""
mooring_generator.py — Drifting and anchored mooring configurations.

Builds the visible mooring geometry (anchor, tether/chain, drogue) and returns
a small state object the hydrodynamics module reads to apply a restoring force
on the buoy. Two deployment modes from the brief:

    drifting  buoy --short chain--> drogue weight (no seabed contact)
    anchored  buoy --elastic tether--> concrete seabed anchor (single point)

The mooring's *dynamic* effect (a spring-damper pull toward the anchor once the
tether goes taut) is computed in hydrodynamics.py; here we only build geometry
and expose the parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import bpy
from mathutils import Vector

from config import MooringParams


@dataclass
class MooringState:
    mode: str
    anchor_pos: Vector           # world-space anchor / drogue attach point
    rest_length: float           # slack length before the line resists
    stiffness: float
    damping: float
    line_obj: Optional[bpy.types.Object] = None


def _material(name, color, metallic=0.6, roughness=0.5):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    return mat


def _line(name, start: Vector, end: Vector, radius=0.03) -> bpy.types.Object:
    """A thin cylinder between two points, used as a hookable tether object.

    A curve with a bevel would drape more realistically; a straight cylinder
    keeps the endpoints trivially updatable per-frame by the animator.
    """
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=radius,
                          radius2=radius, depth=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj.data.materials.append(_material(name + "_mat", (0.15, 0.15, 0.16)))
    _aim_line(obj, start, end)
    return obj


def _aim_line(obj: bpy.types.Object, start: Vector, end: Vector):
    """Position/scale a unit-length cylinder to span start->end."""
    mid = (start + end) * 0.5
    d = end - start
    length = max(d.length, 1e-4)
    obj.location = mid
    obj.scale = (1.0, 1.0, length)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = d.normalized().to_track_quat('Z', 'Y')


def build(params: MooringParams, buoy_start: Vector) -> MooringState:
    """Create mooring geometry for the chosen mode and return its state."""
    clear_mooring()
    mode = params.mode.lower()

    if mode == "free":
        return MooringState("free", buoy_start.copy(),
                            rest_length=1e9, stiffness=0.0, damping=0.0)

    if mode == "drifting":
        # Drogue hangs a short chain below the buoy; anchor point = drogue,
        # which itself drifts with the buoy (soft, damped).
        drogue_pos = buoy_start + Vector((0, 0, -params.chain_length))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=drogue_pos)
        drogue = bpy.context.active_object
        drogue.name = "Drogue"
        drogue.data.materials.append(_material("drogue_mat", (0.2, 0.2, 0.22),
                                               metallic=0.8))
        line = _line("MooringChain", buoy_start, drogue_pos, radius=0.02)
        return MooringState("drifting", drogue_pos, rest_length=params.chain_length,
                            stiffness=params.stiffness * 0.4,
                            damping=params.damping, line_obj=line)

    # anchored
    anchor_pos = Vector((params.anchor_offset[0], params.anchor_offset[1],
                         -params.depth))
    bpy.ops.mesh.primitive_cube_add(size=0.8, location=anchor_pos)
    anchor = bpy.context.active_object
    anchor.name = "Anchor"
    anchor.scale = (1.0, 1.0, 0.5)
    anchor.data.materials.append(_material("anchor_mat", (0.35, 0.34, 0.33),
                                           metallic=0.0, roughness=0.9))
    line = _line("MooringTether", buoy_start, anchor_pos, radius=0.03)
    return MooringState("anchored", anchor_pos, rest_length=params.tether_length,
                        stiffness=params.stiffness, damping=params.damping,
                        line_obj=line)


def update_line(state: MooringState, buoy_pos: Vector):
    """Re-aim the visible tether/chain to the buoy's current position."""
    if state.line_obj is not None:
        _aim_line(state.line_obj, buoy_pos, state.anchor_pos)


def clear_mooring():
    for name in ("Anchor", "Drogue", "MooringTether", "MooringChain"):
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
