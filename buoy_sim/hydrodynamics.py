"""
hydrodynamics.py — Simplified 6-DOF buoyancy + damping model for animation.

This is a previsualisation-grade rigid-body model, not a boundary-element
solver. It bakes believable buoy motion by:

  1. Raycasting the buoy's waterplane against the *evaluated* Ocean-modifier
     surface each frame to read the true water elevation and local slope, so
     the buoy stays glued to the visible waves.
  2. Driving heave as a damped spring toward that elevation — which naturally
     reproduces a heave RAO near 1 for long waves and attenuation for short,
     steep waves (the "heave tracking" behaviour of a wave buoy).
  3. Driving roll/pitch toward the local wave slope, reduced by a metacentric
     righting term (low CG -> strong righting -> partial slope following).
  4. Adding slow yaw weathervaning and small surge/sway orbital motion, with a
     mooring spring-damper pulling the buoy back toward its anchor.

Motion is baked to keyframes so the result renders deterministically and can be
inspected in the timeline. For quantitative work, export the logged time series
and validate against Capytaine / WEC-Sim — this model is for design iteration
and visualisation, and it says so.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import bpy
from mathutils import Vector

from config import (BuoyParams, SeaState, SceneParams, GRAVITY, WATER_DENSITY)
from mooring_generator import MooringState, update_line


# ---------------------------------------------------------------------------
# Derived rigid-body properties
# ---------------------------------------------------------------------------
@dataclass
class Dynamics:
    displaced_volume: float
    waterplane_radius: float
    gm: float                 # metacentric height (m)
    wn_heave: float           # rad/s
    wn_roll: float            # rad/s
    zeta_heave: float
    zeta_roll: float
    equilibrium_offset: float # CG height relative to still-water surface (<0)
    slope_follow: float       # fraction of wave slope the buoy assumes


def derive_dynamics(buoy: BuoyParams) -> Dynamics:
    """Compute natural frequencies / damping from geometry + mass budget."""
    mass = buoy.total_mass

    # Solve draft: integrate submerged volume from the keel up until the
    # displaced seawater mass equals the buoy mass.
    n = 200
    top = buoy.height
    dz = top / n
    vol = 0.0
    draft = top
    target = mass / WATER_DENSITY
    for i in range(n):
        z = (i + 0.5) * dz
        r = buoy.radius_at(z)
        vol += math.pi * r * r * dz
        if vol >= target:
            draft = z
            break
    disp_vol = max(vol, target)

    r_wl = buoy.radius_at(draft)
    aw = math.pi * r_wl * r_wl                       # waterplane area
    kb = draft * 0.45                                # centre of buoyancy height
    i_wp = math.pi * r_wl ** 4 / 4.0                 # waterplane 2nd moment
    bm = i_wp / max(disp_vol, 1e-6)
    kg = buoy.cg_height
    gm = max(0.02, kb + bm - kg + buoy.gm_bonus)

    # Heave: k = rho*g*Aw ; add ~ 60% added mass.
    k_heave = WATER_DENSITY * GRAVITY * aw
    m_heave = mass * 1.6
    wn_heave = math.sqrt(k_heave / m_heave)

    # Roll: k = rho*g*V*GM ; I about CG ~ m * kr^2, kr ~ 0.42 * height.
    kr = 0.42 * buoy.height
    inertia = mass * kr * kr
    added_inertia = inertia * 0.4
    k_roll = WATER_DENSITY * GRAVITY * disp_vol * gm
    wn_roll = math.sqrt(k_roll / (inertia + added_inertia))

    # Equilibrium CG position relative to still water surface (negative => CG
    # sits below the waterline).
    equilibrium_offset = kg - draft

    # A stiff, low-CG buoy follows perhaps 55-75% of the local slope.
    slope_follow = max(0.3, min(0.85, 0.9 - 0.25 * gm))

    return Dynamics(disp_vol, r_wl, gm, wn_heave, wn_roll,
                    zeta_heave=0.16, zeta_roll=0.12,
                    equilibrium_offset=equilibrium_offset,
                    slope_follow=slope_follow)


# ---------------------------------------------------------------------------
# Ocean surface sampling
# ---------------------------------------------------------------------------
def _raycast_z(ocean_eval, world_x: float, world_y: float) -> Optional[float]:
    """Return world-space water elevation at (x, y), or None on a miss."""
    mw = ocean_eval.matrix_world
    inv = mw.inverted()
    origin = inv @ Vector((world_x, world_y, 50.0))
    direction = (inv.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    hit, loc, normal, idx = ocean_eval.ray_cast(origin, direction)
    if not hit:
        return None
    return (mw @ loc).z


def sample_surface(ocean_eval, x: float, y: float, base: float = 0.8
                   ) -> Tuple[float, float, float]:
    """Return (elevation, slope_x, slope_y) at (x, y).

    Slopes are measured over a buoy-scale baseline so single coarse ocean
    faces don't produce jittery tilt.
    """
    z0 = _raycast_z(ocean_eval, x, y)
    if z0 is None:
        return 0.0, 0.0, 0.0
    zx = _raycast_z(ocean_eval, x + base, y)
    zxm = _raycast_z(ocean_eval, x - base, y)
    zy = _raycast_z(ocean_eval, x, y + base)
    zym = _raycast_z(ocean_eval, x, y - base)
    sx = ((zx if zx is not None else z0) - (zxm if zxm is not None else z0)) / (2 * base)
    sy = ((zy if zy is not None else z0) - (zym if zym is not None else z0)) / (2 * base)
    return z0, sx, sy


# ---------------------------------------------------------------------------
# 6-DOF integrator state
# ---------------------------------------------------------------------------
@dataclass
class MotionLog:
    """Per-frame time series (seconds and the six DOFs)."""
    t: List[float] = field(default_factory=list)
    surge: List[float] = field(default_factory=list)
    sway: List[float] = field(default_factory=list)
    heave: List[float] = field(default_factory=list)
    roll: List[float] = field(default_factory=list)
    pitch: List[float] = field(default_factory=list)
    yaw: List[float] = field(default_factory=list)

    def stats(self) -> str:
        def amp(v):
            return (max(v) - min(v)) if v else 0.0
        return (f"heave {amp(self.heave):.2f} m p-p, "
                f"roll {math.degrees(amp(self.roll)):.1f} deg p-p, "
                f"pitch {math.degrees(amp(self.pitch)):.1f} deg p-p, "
                f"yaw {math.degrees(amp(self.yaw)):.1f} deg p-p")


def simulate(root: bpy.types.Object, buoy: BuoyParams, sea: SeaState,
             scene: SceneParams, mooring: MooringState,
             ocean_obj: bpy.types.Object) -> MotionLog:
    """Bake 6-DOF motion onto the buoy root empty; return the motion log."""
    dyn = derive_dynamics(buoy)
    ctx = bpy.context
    scn = ctx.scene
    rng = random.Random(scene.seed)

    fps = scene.fps
    dt_frame = 1.0 / fps
    n_sub = 4
    dt = dt_frame / n_sub
    frame_end = scene.frame_end

    # State: position of the CG (world) and orientation (roll, pitch, yaw).
    still_z = dyn.equilibrium_offset       # start at still-water equilibrium
    pos = Vector((root.location.x, root.location.y, still_z))
    vel = Vector((0.0, 0.0, 0.0))
    ang = Vector((0.0, 0.0, 0.0))          # roll(x), pitch(y), yaw(z)
    ang_vel = Vector((0.0, 0.0, 0.0))

    heading = math.radians(sea.wind_dir_deg)
    yaw_target = heading                    # weathervane toward wave heading
    mass = buoy.total_mass

    log = MotionLog()

    for frame in range(1, frame_end + 1):
        scn.frame_set(frame)               # updates ocean driver + modifier
        depsgraph = ctx.evaluated_depsgraph_get()
        ocean_eval = ocean_obj.evaluated_get(depsgraph)

        for _ in range(n_sub):
            z_surf, sx, sy = sample_surface(ocean_eval, pos.x, pos.y)

            # --- Heave: damped spring toward (surface + equilibrium offset) ---
            z_target = z_surf + dyn.equilibrium_offset
            az = (dyn.wn_heave ** 2) * (z_target - pos.z) \
                - 2.0 * dyn.zeta_heave * dyn.wn_heave * vel.z
            vel.z += az * dt
            pos.z += vel.z * dt

            # --- Roll / pitch: follow local slope, reduced by righting ------
            # slope_x tilts about Y (pitch); slope_y tilts about X (roll).
            pitch_target = -math.atan(sx) * dyn.slope_follow
            roll_target = math.atan(sy) * dyn.slope_follow
            a_roll = (dyn.wn_roll ** 2) * (roll_target - ang.x) \
                - 2.0 * dyn.zeta_roll * dyn.wn_roll * ang_vel.x
            a_pitch = (dyn.wn_roll ** 2) * (pitch_target - ang.y) \
                - 2.0 * dyn.zeta_roll * dyn.wn_roll * ang_vel.y
            ang_vel.x += a_roll * dt
            ang_vel.y += a_pitch * dt
            ang.x += ang_vel.x * dt
            ang.y += ang_vel.y * dt

            # --- Surge / sway: small wave orbital drift + mooring restore ---
            orbit = 0.15 * sea.hs
            wx = orbit * math.cos(2 * math.pi * sea.peak_frequency
                                  * frame * dt_frame) * math.cos(heading)
            wy = orbit * math.cos(2 * math.pi * sea.peak_frequency
                                  * frame * dt_frame) * math.sin(heading)
            # Mooring: spring-damper once beyond rest length toward anchor.
            fx = fy = 0.0
            if mooring.stiffness > 0.0:
                to_anchor = mooring.anchor_pos - pos
                dist = to_anchor.length
                if dist > mooring.rest_length:
                    stretch = dist - mooring.rest_length
                    dirn = to_anchor.normalized()
                    f = mooring.stiffness * stretch
                    fx = (f * dirn.x - mooring.damping * vel.x) / mass
                    fy = (f * dirn.y - mooring.damping * vel.y) / mass
            # Gentle restoring toward orbital target keeps free buoys bounded.
            ax = 0.8 * (wx - (pos.x - root.location.x)) + fx
            ay = 0.8 * (wy - (pos.y - root.location.y)) + fy
            vel.x += ax * dt
            vel.y += ay * dt
            pos.x += vel.x * dt
            pos.y += vel.y * dt

            # --- Yaw: slow weathervane + low-amplitude wander --------------
            yaw_target += rng.uniform(-0.02, 0.02) * dt
            a_yaw = 1.5 * (yaw_target - ang.z) - 0.9 * ang_vel.z
            ang_vel.z += a_yaw * dt
            ang.z += ang_vel.z * dt

        # Write transform + keyframes once per frame.
        root.location = pos
        root.rotation_euler = (ang.x, ang.y, ang.z)
        root.keyframe_insert("location", frame=frame)
        root.keyframe_insert("rotation_euler", frame=frame)
        update_line(mooring, pos)
        if mooring.line_obj is not None:
            mooring.line_obj.keyframe_insert("location", frame=frame)
            mooring.line_obj.keyframe_insert("rotation_quaternion", frame=frame)
            mooring.line_obj.keyframe_insert("scale", frame=frame)

        t = frame * dt_frame
        log.t.append(t)
        log.surge.append(pos.x)
        log.sway.append(pos.y)
        log.heave.append(pos.z - still_z)
        log.roll.append(ang.x)
        log.pitch.append(ang.y)
        log.yaw.append(ang.z)

    # Smooth interpolation on the baked curves.
    if root.animation_data and root.animation_data.action:
        for fc in root.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'

    return log
