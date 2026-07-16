"""
config.py — Digital-twin parameter definitions for the buoy simulation.

Everything the other modules need is described here as plain dataclasses so a
buoy concept is fully defined by data, not code. Swap a hull, ballast layout,
sensor payload, mooring or sea state by editing (or programmatically building)
these objects — the generators read them and rebuild the scene.

These modules are meant to be run *inside* Blender (`import bpy`), but this
file has no Blender dependency so it can be imported, tested and diffed on a
plain Python interpreter too.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

GRAVITY = 9.81           # m/s^2
WATER_DENSITY = 1025.0   # kg/m^3 (seawater)


# ---------------------------------------------------------------------------
# Sea states (WMO / Douglas scale, approximated for animation)
# ---------------------------------------------------------------------------
@dataclass
class SeaState:
    """A single sea-state preset.

    hs is the significant wave height (m); tp the peak (dominant) wave period
    (s); wind_dir_deg the mean wave heading in the XY plane. `gamma` is the
    JONSWAP peak-enhancement factor used by the analytic spectrum.
    """
    index: int
    name: str
    hs: float
    tp: float
    wind_dir_deg: float = 0.0
    gamma: float = 3.3
    choppiness: float = 1.0   # visual only: Ocean-modifier horizontal displacement

    @property
    def peak_frequency(self) -> float:
        return 1.0 / self.tp if self.tp > 0 else 0.0

    @property
    def peak_wavelength(self) -> float:
        # Deep-water dispersion: L = g * T^2 / (2*pi)
        return GRAVITY * self.tp * self.tp / (2.0 * 3.141592653589793)


# Presets keyed by integer sea state. Values follow the table in the brief
# (Douglas scale) with representative periods; states 4-6 extend the range.
SEA_STATES: Dict[int, SeaState] = {
    0: SeaState(0, "Calm (glassy)",      hs=0.05, tp=2.0, gamma=1.0, choppiness=0.2),
    1: SeaState(1, "Calm (rippled)",     hs=0.35, tp=4.0, gamma=1.5, choppiness=0.4),
    2: SeaState(2, "Smooth",             hs=0.85, tp=5.5, gamma=2.0, choppiness=0.7),
    3: SeaState(3, "Slight",             hs=1.80, tp=6.5, gamma=3.3, choppiness=1.0),
    4: SeaState(4, "Moderate",           hs=2.75, tp=7.5, gamma=3.3, choppiness=1.3),
    5: SeaState(5, "Rough",              hs=3.75, tp=8.5, gamma=3.3, choppiness=1.6),
    6: SeaState(6, "Very rough",         hs=5.25, tp=9.5, gamma=3.3, choppiness=1.8),
}


def sea_state(index: int, hs: Optional[float] = None,
              tp: Optional[float] = None,
              wind_dir_deg: Optional[float] = None) -> SeaState:
    """Return a preset, optionally overriding Hs / Tp / heading.

    Lets a natural-language request like "Sea State 3 with 1.8 m and 7 s"
    become ``sea_state(3, hs=1.8, tp=7.0)``.
    """
    base = SEA_STATES[index]
    overrides = {}
    if hs is not None:
        overrides["hs"] = hs
    if tp is not None:
        overrides["tp"] = tp
    if wind_dir_deg is not None:
        overrides["wind_dir_deg"] = wind_dir_deg
    return replace(base, **overrides) if overrides else base


# ---------------------------------------------------------------------------
# Buoy geometry + mass properties
# ---------------------------------------------------------------------------
@dataclass
class BuoySection:
    """One stacked, revolved section of the hull (bottom-up).

    `z` is the height of the section's bottom rim above the keel; `radius` the
    outer radius at that rim. The hull lofts a smooth surface through the rims.
    """
    z: float
    radius: float
    name: str = ""


@dataclass
class BuoyParams:
    """Full parametric description of a buoy.

    The default describes the commercial-style baseline inferred from the
    screenshots: a teardrop lower hull, a wider electronics collar, a low CG
    from batteries/ballast and a short steel keel weight.
    """
    name: str = "baseline"

    # Revolved hull profile (keel at z=0, mast tip at top), bottom to top.
    sections: List[BuoySection] = field(default_factory=lambda: [
        BuoySection(0.00, 0.02, "keel"),
        BuoySection(0.08, 0.18, "lower_hull"),
        BuoySection(0.30, 0.32, "max_beam"),      # widest submerged body
        BuoySection(0.55, 0.30, "shoulder"),
        BuoySection(0.70, 0.34, "collar"),        # reserve-buoyancy electronics collar
        BuoySection(0.90, 0.30, "housing_top"),
        BuoySection(1.05, 0.05, "mast_base"),
        BuoySection(1.55, 0.03, "mast_tip"),      # antenna / light mast
    ])

    revolve_segments: int = 48

    # Mass budget (kg) with each item's height above keel (m). Used to derive
    # total mass and the vertical centre of gravity.
    # Tuned so the CG (~0.23 m) sits well below the centre of buoyancy, giving a
    # positive metacentric height (GM ~ +0.09 m) and a ~5 s roll period.
    mass_items: List[Tuple[str, float, float]] = field(default_factory=lambda: [
        ("steel_keel_weight", 32.0, 0.03),
        ("ballast",           20.0, 0.10),
        ("batteries",         20.0, 0.15),
        ("sensors",            4.0, 0.40),
        ("foam_chamber",       6.0, 0.55),   # positive reserve buoyancy, low mass
        ("electronics",        5.0, 0.78),
        ("housing_shell",      7.0, 0.85),
        ("mast_and_antenna",   1.2, 1.30),
    ])

    # Hydrostatics. If waterline_z is None it is solved from displacement.
    waterline_z: Optional[float] = None
    # Extra metacentric height (m) added to the geometric estimate; captures
    # form stability that the simplified revolve does not resolve.
    gm_bonus: float = 0.05

    # ---- derived quantities -------------------------------------------------
    @property
    def total_mass(self) -> float:
        return sum(m for _, m, _ in self.mass_items)

    @property
    def cg_height(self) -> float:
        """Vertical centre of gravity above keel (m)."""
        total = self.total_mass
        if total <= 0:
            return 0.0
        return sum(m * z for _, m, z in self.mass_items) / total

    @property
    def max_radius(self) -> float:
        return max(s.radius for s in self.sections)

    @property
    def height(self) -> float:
        return max(s.z for s in self.sections)

    def radius_at(self, z: float) -> float:
        """Linear-interpolated outer radius at height z (for volume integ.)."""
        secs = self.sections
        if z <= secs[0].z:
            return secs[0].radius
        if z >= secs[-1].z:
            return secs[-1].radius
        for a, b in zip(secs, secs[1:]):
            if a.z <= z <= b.z:
                t = (z - a.z) / (b.z - a.z) if b.z > a.z else 0.0
                return a.radius + t * (b.radius - a.radius)
        return secs[-1].radius


# ---------------------------------------------------------------------------
# Mooring
# ---------------------------------------------------------------------------
@dataclass
class MooringParams:
    """Mooring / deployment configuration.

    mode is "free", "drifting" or "anchored".
      * free      — no mooring, pure wave-following (open-loop drift).
      * drifting  — short chain to a drogue weight below the buoy.
      * anchored  — elastic tether to a seabed anchor (single-point mooring).
    """
    mode: str = "anchored"

    depth: float = 30.0            # water depth (m), anchored mode
    tether_length: float = 34.0    # m; slight scope > depth for anchored mode
    stiffness: float = 400.0       # N/m of the elastic tether / chain
    damping: float = 120.0         # N*s/m along the mooring line

    chain_length: float = 3.0      # m; drifting-mode chain to drogue
    drogue_mass: float = 8.0       # kg
    anchor_offset: Tuple[float, float] = (0.0, 0.0)  # anchor XY vs buoy start


# ---------------------------------------------------------------------------
# Scene / render
# ---------------------------------------------------------------------------
@dataclass
class SceneParams:
    ocean_size: float = 500.0      # m, extent of the ocean plane
    ocean_resolution: int = 7      # Ocean-modifier resolution (2^n grid)
    ocean_spatial: float = 60.0    # m, repeat tile size of the Ocean modifier
    fps: int = 30
    duration_s: float = 60.0
    seed: int = 12345

    camera: str = "chase"          # "chase", "underwater", "orbit", "static"
    use_hdri: bool = True
    hdri_path: Optional[str] = None
    engine: str = "BLENDER_EEVEE"  # or "CYCLES"
    samples: int = 64
    resolution_x: int = 1920
    resolution_y: int = 1080

    @property
    def frame_end(self) -> int:
        return max(1, int(round(self.duration_s * self.fps)))


@dataclass
class SimConfig:
    """Top-level bundle passed around the pipeline."""
    buoy: BuoyParams = field(default_factory=BuoyParams)
    mooring: MooringParams = field(default_factory=MooringParams)
    sea: SeaState = field(default_factory=lambda: SEA_STATES[3])
    scene: SceneParams = field(default_factory=SceneParams)


def describe(cfg: SimConfig) -> str:
    """Human-readable one-screen summary of a configuration."""
    b, s, m, sc = cfg.buoy, cfg.sea, cfg.mooring, cfg.scene
    return (
        f"Buoy '{b.name}': mass={b.total_mass:.1f} kg, CG={b.cg_height:.3f} m, "
        f"beam={2*b.max_radius:.2f} m, height={b.height:.2f} m\n"
        f"Sea state {s.index} ({s.name}): Hs={s.hs:.2f} m, Tp={s.tp:.1f} s, "
        f"heading={s.wind_dir_deg:.0f} deg, L_peak={s.peak_wavelength:.1f} m\n"
        f"Mooring: {m.mode} (k={m.stiffness:.0f} N/m)\n"
        f"Scene: {sc.duration_s:.0f} s @ {sc.fps} fps ({sc.frame_end} frames), "
        f"camera={sc.camera}"
    )
