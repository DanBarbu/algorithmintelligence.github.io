"""
buoy_generator.py — Parametric buoy geometry.

Builds a revolved hull from the stacked ``BuoySection`` profile in a
``BuoyParams`` object, adds simple sensor/payload proxies, and returns a single
parented Empty ("Buoy") that the hydrodynamics module animates. The hull mesh
is created bottom-up in the buoy's local frame with the keel at z=0; the whole
assembly is then shifted so the origin sits at the centre of gravity, which is
what the rigid-body motion is applied about.

Run inside Blender:
    import bpy; import buoy_generator, config
    buoy_generator.build(config.BuoyParams())
"""

from __future__ import annotations

import math
from typing import List

import bpy
import bmesh
from mathutils import Vector

from config import BuoyParams


def _material(name: str, color, metallic=0.0, roughness=0.5, emission=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if emission is not None and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 4.0
    return mat


def _revolve_hull(params: BuoyParams) -> bpy.types.Object:
    """Loft a surface of revolution through the section rims."""
    secs = params.sections
    seg = max(8, params.revolve_segments)

    bm = bmesh.new()
    rings: List[List[bmesh.types.BMVert]] = []
    for s in secs:
        ring = []
        # Degenerate (radius ~0) rings collapse to a single pole vertex.
        if s.radius < 1e-4:
            ring = [bm.verts.new((0.0, 0.0, s.z))] * seg
        else:
            for i in range(seg):
                a = 2.0 * math.pi * i / seg
                ring.append(bm.verts.new((s.radius * math.cos(a),
                                          s.radius * math.sin(a), s.z)))
        rings.append(ring)

    for lower, upper in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            a, b, c, d = lower[i], lower[j], upper[j], upper[i]
            verts = [v for v in (a, b, c, d)]
            # Skip faces that collapse at a pole (shared vertex).
            if len({v.index if v.index >= 0 else id(v) for v in verts}) < 3:
                uniq = []
                for v in verts:
                    if v not in uniq:
                        uniq.append(v)
                if len(uniq) >= 3:
                    try:
                        bm.faces.new(uniq)
                    except ValueError:
                        pass
                continue
            try:
                bm.faces.new((a, b, c, d))
            except ValueError:
                pass

    # Cap the keel bottom.
    if secs[0].radius >= 1e-4:
        try:
            bm.faces.new(list(reversed(rings[0])))
        except ValueError:
            pass

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("BuoyHull")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("BuoyHull", mesh)
    bpy.context.collection.objects.link(obj)

    # Shade smooth.
    for p in mesh.polygons:
        p.use_smooth = True
    return obj


def _payload_proxy(name, radius, depth, z, color, metallic=0.3, roughness=0.4,
                   emission=None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth,
                                         location=(0, 0, z), vertices=24)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(_material(name + "_mat", color, metallic,
                                        roughness, emission))
    return obj


def build(params: BuoyParams) -> bpy.types.Object:
    """Create the buoy assembly and return the root Empty at the CG."""
    # Root empty placed at the CG height; children are offset so the keel sits
    # below and the mast above. Motion is applied to this empty.
    cg = params.cg_height
    root = bpy.data.objects.new(f"Buoy_{params.name}", None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.3
    bpy.context.collection.objects.link(root)

    parts: List[bpy.types.Object] = []

    hull = _revolve_hull(params)
    hull.data.materials.append(
        _material("hull_mat", (0.95, 0.78, 0.05), metallic=0.1, roughness=0.55))
    parts.append(hull)

    # Electronics collar band (thin ring emphasising reserve buoyancy zone).
    collar_z = next((s.z for s in params.sections if s.name == "collar"),
                    params.height * 0.65)
    collar = _payload_proxy("collar_band", params.max_radius * 1.02, 0.08,
                            collar_z, (0.12, 0.12, 0.14), metallic=0.6,
                            roughness=0.3)
    parts.append(collar)

    # Navigation light on the mast tip.
    light = _payload_proxy("nav_light", 0.05, 0.08, params.height - 0.05,
                           (1.0, 0.35, 0.05), metallic=0.0, roughness=0.2,
                           emission=(1.0, 0.3, 0.05))
    parts.append(light)

    # Steel keel weight proxy (dense, low).
    keel = _payload_proxy("keel_weight", params.sections[0].radius + 0.04,
                          0.06, 0.03, (0.25, 0.25, 0.28), metallic=0.9,
                          roughness=0.35)
    parts.append(keel)

    for p in parts:
        p.parent = root
        p.location = (p.location.x, p.location.y, p.location.z - cg)

    root["cg_height"] = cg
    root["total_mass"] = params.total_mass
    root["draft_est"] = params.waterline_z if params.waterline_z is not None else cg
    return root


def clear_buoys():
    """Remove previously generated buoy objects (idempotent rebuilds)."""
    for obj in list(bpy.data.objects):
        if obj.name.startswith("Buoy_") or obj.name in {
                "BuoyHull", "collar_band", "nav_light", "keel_weight"}:
            bpy.data.objects.remove(obj, do_unlink=True)
