# Buoy Sea-State Simulation — Blender Digital-Twin Framework

A parametric, data-driven Blender toolkit for previsualising how a wave-measurement
buoy behaves across sea states. It is built as a **digital-twin framework**, not a
single fixed model: hulls, ballast layouts, sensor payloads, moorings and sea
states are all defined as plain data in `config.py`, so you can regenerate the
geometry and re-run the animation from a one-line command or a natural-language
request.

> **Fidelity note.** This is a *previsualisation / design-iteration* tool. The
> hydrodynamics module is a simplified 6-DOF rigid-body model (buoyancy spring +
> slope-following + damping), not a boundary-element or CFD solver. It is tuned to
> look and behave plausibly for comparing concepts. For quantitative radiation /
> diffraction results, export the motion log and validate against
> [Capytaine](https://github.com/capytaine/capytaine),
> [WEC-Sim](https://wec-sim.github.io/WEC-Sim/) or OpenFOAM.

## Files

| Module | Role |
|--------|------|
| `config.py` | All parameters as dataclasses: sea states, buoy geometry + mass budget, mooring, scene/render. No Blender dependency — importable/testable in plain Python. |
| `buoy_generator.py` | Revolved parametric hull from a stacked section profile, plus payload proxies. Returns a single `Buoy_*` empty at the centre of gravity. |
| `ocean_generator.py` | Configurable Sea State 0–6 ocean plane driven by Blender's Ocean modifier, mapped from Hs/Tp/heading and animated from the frame. |
| `mooring_generator.py` | Drifting (chain + drogue) and anchored (elastic tether + seabed anchor) configurations, plus a `MooringState` the physics reads. |
| `hydrodynamics.py` | Simplified 6-DOF model. Raycasts the buoy waterplane against the *evaluated* ocean surface each frame so the buoy stays glued to the visible waves; bakes motion to keyframes. |
| `render_animation.py` | World lighting (HDRI or procedural sky), cameras (chase / underwater / orbit / static), MP4 render. |
| `main.py` | CLI orchestrator: parse flags → build → bake → render. |

## Requirements

- **Blender 3.6+ or 4.x** (uses the Ocean modifier, EEVEE/Cycles, `bpy`, `bmesh`).
  No external Python packages are needed — everything runs in Blender's bundled Python.
- `config.py` and its derived quantities can be checked with a plain
  `python3 -c "import config; print(config.describe(config.SimConfig()))"`.

## Usage

Run inside Blender in background mode. Everything after `--` is passed to the script.

```bash
# Sea State 3, 1.8 m significant wave height, 7 s period, chase camera, anchored
blender --background --python buoy_sim/main.py -- \
    --sea 3 --hs 1.8 --tp 7.0 --duration 60 --camera chase \
    --mooring anchored --render out/sea3.mp4 --export-motion out/sea3.csv

# Just build and save the .blend for interactive inspection (no render)
blender --background --python buoy_sim/main.py -- \
    --sea 2 --camera orbit --save-blend out/sea2.blend
```

### Natural-language → flags

The brief's example prompts map directly onto CLI flags:

> "Simulate the buoy in Sea State 3 with 1.8 m significant wave height and a 7-second wave period."

```bash
--sea 3 --hs 1.8 --tp 7.0
```

> "Increase the ballast by 15%, reduce the upper housing diameter by 10%, and compare roll amplitude over 60 seconds."

```bash
--ballast-scale 1.15 --housing-scale 0.9 --duration 60 --export-motion out/variant.csv
```

The exported CSV has columns `t, surge, sway, heave, roll_deg, pitch_deg, yaw_deg`
so two variants can be compared under identical seas.

## Sea-state presets

| State | Name | Hs (m) | Tp (s) |
|:---:|---|---|---|
| 0 | Calm (glassy) | 0.05 | 2.0 |
| 1 | Calm (rippled) | 0.35 | 4.0 |
| 2 | Smooth | 0.85 | 5.5 |
| **3** | **Slight** | **1.80** | **6.5** |
| 4 | Moderate | 2.75 | 7.5 |
| 5 | Rough | 3.75 | 8.5 |
| 6 | Very rough | 5.25 | 9.5 |

Any preset can be overridden per-run with `--hs` / `--tp` / `--heading`.

## Baseline buoy (inferred from the screenshots)

A near-axisymmetric teardrop lower hull, a wider electronics collar for reserve
buoyancy, and a low CG from batteries + ballast + a steel keel weight:

```
          Antenna / light mast
        ┌──────────────┐
        │ Electronics  │
════════╪══════════════╪════ Waterline  (draft ≈ 0.45 m)
        │ Collar       │  reserve buoyancy
        │ Foam chamber │
        │ Batteries    │
        │ Ballast      │
        │   • CG ≈ 0.23 m  (well below CB → GM ≈ +0.09 m)
        └ Steel keel ──┘
```

Derived from the default `config.py`: mass ≈ 95 kg, beam ≈ 0.68 m, height ≈ 1.55 m,
heave natural period ≈ 1.3 s (well below wave periods → heave RAO near 1, i.e. good
heave tracking), roll period ≈ 5 s.

## Building next-generation concepts

Because a buoy is fully described by data, you can define new concepts as
alternative `BuoyParams` (new section profile, new mass budget) and compare them
against the commercial-style baseline under identical seas. The framework is the
place to prototype modular payloads — HaLow WiFi gateway, LoRa mesh, GNSS wave
sensor, AI edge processor, floating solar ring, retractable hydrophone,
water-quality package, expandable battery bay — before committing to hydrodynamic
analysis.

## Roadmap / next steps

1. Swap in real reference screenshots as an HDRI backplate for the chase camera.
2. Add a `variants.py` describing several concept buoys and a batch runner that
   renders them side-by-side across Sea States 0–6.
3. Export the 6-DOF logs to a hydrodynamic pipeline (Capytaine mesh + WEC-Sim) to
   replace the simplified model with validated RAOs where accuracy matters.
