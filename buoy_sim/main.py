"""
main.py — Orchestrates the full buoy simulation pipeline inside Blender.

Usage (Blender must be on your PATH):

    blender --background --python buoy_sim/main.py -- \
        --sea 3 --hs 1.8 --tp 7.0 --duration 60 --camera chase \
        --mooring anchored --render out/sea3.mp4

Every module is data-driven from ``config.py``; the CLI just overrides fields
on a ``SimConfig`` and runs generate -> bake -> render. Omit ``--render`` to
only build and save the .blend for interactive inspection.

Natural-language requests map directly onto flags, e.g.
    "Sea State 3 with 1.8 m and a 7-second period"  -> --sea 3 --hs 1.8 --tp 7
    "increase ballast 15%, shrink housing 10%"       -> --ballast-scale 1.15 --housing-scale 0.9
"""

from __future__ import annotations

import argparse
import os
import sys

# Make sibling modules importable when run via `blender --python`.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import config  # noqa: E402
import buoy_generator  # noqa: E402
import ocean_generator  # noqa: E402
import mooring_generator  # noqa: E402
import hydrodynamics  # noqa: E402
import render_animation  # noqa: E402
from mathutils import Vector  # noqa: E402


def parse_args(argv):
    p = argparse.ArgumentParser(description="Parametric buoy sea-state simulation")
    p.add_argument("--sea", type=int, default=3, help="sea state index 0-6")
    p.add_argument("--hs", type=float, default=None, help="override Hs (m)")
    p.add_argument("--tp", type=float, default=None, help="override Tp (s)")
    p.add_argument("--heading", type=float, default=None, help="wave heading (deg)")
    p.add_argument("--duration", type=float, default=30.0, help="seconds")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--camera", default="chase",
                   choices=["chase", "underwater", "orbit", "static"])
    p.add_argument("--mooring", default="anchored",
                   choices=["free", "drifting", "anchored"])
    p.add_argument("--engine", default="BLENDER_EEVEE",
                   help="BLENDER_EEVEE or CYCLES")
    p.add_argument("--ballast-scale", type=float, default=1.0,
                   help="multiply ballast + keel mass")
    p.add_argument("--housing-scale", type=float, default=1.0,
                   help="scale upper housing/collar radius")
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--render", default=None, help="output MP4 path (skip to only save .blend)")
    p.add_argument("--save-blend", default=None, help="path to save the .blend")
    p.add_argument("--export-motion", default=None, help="CSV path for the 6-DOF log")
    return p.parse_args(argv)


def apply_buoy_overrides(buoy: config.BuoyParams, args) -> config.BuoyParams:
    """Apply parametric tweaks so 'increase ballast 15%' works from the CLI."""
    if args.ballast_scale != 1.0:
        buoy.mass_items = [
            (name, m * args.ballast_scale if name in ("ballast", "steel_keel_weight")
             else m, z)
            for (name, m, z) in buoy.mass_items]
    if args.housing_scale != 1.0:
        for s in buoy.sections:
            if s.name in ("collar", "housing_top", "shoulder"):
                s.radius *= args.housing_scale
    return buoy


def build_config(args) -> config.SimConfig:
    sea = config.sea_state(args.sea, hs=args.hs, tp=args.tp,
                           wind_dir_deg=args.heading)
    buoy = apply_buoy_overrides(config.BuoyParams(), args)
    mooring = config.MooringParams(mode=args.mooring)
    scene = config.SceneParams(fps=args.fps, duration_s=args.duration,
                               camera=args.camera, engine=args.engine,
                               seed=args.seed)
    return config.SimConfig(buoy=buoy, mooring=mooring, sea=sea, scene=scene)


def clean_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for coll in (bpy.data.meshes, bpy.data.materials):
        for item in list(coll):
            if item.users == 0:
                coll.remove(item)


def run(argv):
    args = parse_args(argv)
    cfg = build_config(args)

    print("=" * 70)
    print(config.describe(cfg))
    print("=" * 70)

    clean_scene()

    ocean = ocean_generator.build(cfg.sea, cfg.scene)
    buoy_root = buoy_generator.build(cfg.buoy)
    # Start the buoy near the origin, slightly off the anchor to show tether.
    buoy_root.location = Vector((0.0, 0.0, 0.0))
    mooring = mooring_generator.build(cfg.mooring, Vector((0.0, 0.0, 0.0)))

    log = hydrodynamics.simulate(buoy_root, cfg.buoy, cfg.sea, cfg.scene,
                                 mooring, ocean)
    print("Motion baked:", log.stats())

    render_animation.setup_world(cfg.scene)
    render_animation.setup_camera(cfg.scene, buoy_root)

    if args.export_motion:
        _export_csv(log, args.export_motion)
        print("Motion log ->", args.export_motion)

    if args.save_blend:
        os.makedirs(os.path.dirname(os.path.abspath(args.save_blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=args.save_blend)
        print("Saved .blend ->", args.save_blend)

    if args.render:
        render_animation.render(cfg.scene, args.render, animation=True)
        print("Render ->", args.render)


def _export_csv(log: hydrodynamics.MotionLog, path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write("t,surge,sway,heave,roll_deg,pitch_deg,yaw_deg\n")
        import math
        for i in range(len(log.t)):
            f.write(f"{log.t[i]:.4f},{log.surge[i]:.4f},{log.sway[i]:.4f},"
                    f"{log.heave[i]:.4f},{math.degrees(log.roll[i]):.4f},"
                    f"{math.degrees(log.pitch[i]):.4f},"
                    f"{math.degrees(log.yaw[i]):.4f}\n")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    run(argv)
