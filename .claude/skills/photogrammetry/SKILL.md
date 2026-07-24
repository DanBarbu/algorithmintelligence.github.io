---
name: photogrammetry
description: >-
  Turn a set of overlapping photos of an object or scene into a textured 3D
  model (OBJ/FBX/STL) using free, open-source photogrammetry — the same
  Structure-from-Motion tech behind paid apps like Kiri Engine, but running
  locally with no cloud fees or watermarks. Use this whenever the user wants to
  make a 3D scan or 3D model from photos, mentions photogrammetry, Meshroom,
  COLMAP, RealityScan/Polycam, "photo to 3D", "scan an object", reconstructing
  geometry from images, or asks for a free alternative to Kiri Engine / paid
  3D-scanning apps — even if they don't say the word "photogrammetry." Also use
  it to diagnose failed or patchy scans and to plan a photo-capture session.
---

# Photogrammetry: photos → 3D model, free and open-source

Photogrammetry (specifically Structure-from-Motion, SfM) reconstructs 3D
geometry and texture from a set of overlapping 2D photos. Paid apps like Kiri
Engine wrap these same open-source algorithms in a phone UI and charge for
cloud GPU time. The free tools below do the identical work on the user's own
machine — no subscription, no watermark, full-resolution output.

Your job with this skill is usually one of three things:
1. **Recommend the right tool** for the user's hardware and comfort level.
2. **Plan a capture session** so the photos are actually reconstructable.
3. **Run/automate the pipeline** or diagnose why a scan came out patchy.

## Step 1 — Pick the tool (this decides everything downstream)

The single most important input is the user's GPU, because dense
reconstruction is CUDA-bound in the friendliest tool.

| User has… | Recommend | Why |
|---|---|---|
| NVIDIA GPU (CUDA) on Windows/Linux | **Meshroom** | Drag-drop, node graph runs the whole pipeline automatically. Closest to the Kiri experience. |
| AMD GPU, Intel integrated, or a Mac | **COLMAP** | CPU-capable, works everywhere. Gold-standard accuracy, steeper UI. |
| Only a phone, wants to stay mobile | **RealityScan** (Epic) or **Polycam** | Free tiers, cloud-processed, export OBJ/FBX. Fastest path to a first model. |

Don't push Meshroom at a Mac/AMD user — it will stall at dense reconstruction
with no CUDA device. When hardware is unknown, ask before recommending. Full
comparison, install notes, and links: `references/tools.md`.

## Step 2 — Capture the photos correctly

**This is where most scans fail, not in the software.** Open-source engines
reconstruct only surfaces they can actually see across multiple sharp,
overlapping frames — there is no AI inpainting to hide a gap, so a hole in
your coverage becomes a literal hole in the mesh. Before recommending any
processing, make sure the capture follows the rules in
`references/capture-guide.md`. The essentials:

- **≥70% overlap** between consecutive photos — every point should appear in
  several frames.
- **Tack-sharp focus.** Soft focus makes feature matching fail outright. No
  motion blur.
- **Full coverage, "orbit + poles":** rings of photos at eye level, plus
  angled shots looking down at the top and up toward the base. Don't just
  circle at one height.
- **Flat, diffuse light.** No on-camera flash. Overcast daylight or even
  ambient indoor light is ideal — moving shadows confuse matching.
- **More photos is safer.** 10 is the bare minimum and tends to give patchy
  results; 30–60 for a small object is far more reliable.

If the user is stuck with ~10 photos, read the "Minimal-photo strategy"
section of `references/capture-guide.md` and set expectations honestly rather
than promising a clean model.

## Step 3 — Triage the photos before processing

Bad frames waste a long reconstruction and can poison feature matching. Run
the bundled QA script to flag blurry, over/under-exposed, or too-similar
frames *before* the user commits to a multi-hour run:

```bash
python scripts/check_photos.py /path/to/photos
```

It reports a sharpness score (variance of Laplacian) and exposure per image,
sorts the worst offenders to the top, and warns if the set is small. It uses
only OpenCV + NumPy. Read the top of the script for thresholds you can tune.

## Step 4 — Run the pipeline

Both tools have full command-line interfaces, so a reconstruction can be
scripted and left to run unattended. Use the bundled wrappers as a starting
point and adapt paths/quality flags:

- **Meshroom (CUDA):** `scripts/run_meshroom.sh <images_dir> <output_dir>`
  wraps `meshroom_batch` to run the default pipeline headless and drop a
  textured OBJ in the output directory.
- **COLMAP (cross-platform):** `scripts/run_colmap.sh <images_dir> <workspace>`
  runs feature extraction → matching → sparse (`mapper`) → dense
  (`patch_match_stereo` + `stereo_fusion`) → `poisson_mesher`. It auto-selects
  a CPU or GPU path; comment the flags at the top of the file.

Both scripts print each stage so a failure is easy to localize. If a stage
fails, the usual cause is upstream: too few matched features from thin overlap
or soft focus — loop back to Step 2/3 rather than fighting the tool.

## Zero-token local workflow (the compute is free)

The reconstruction is compute-heavy, but that compute runs on the **user's own
machine** — it costs no API/LLM tokens. Tokens are only spent if the user asks
Claude to babysit each run. So the token-free pattern is: consult this skill
**once** to plan the shoot and pick a tool, then run everything locally and
offline from then on.

`scripts/run.sh <images_dir> <output_dir>` is the single-command path for
exactly this. It auto-detects hardware (NVIDIA→Meshroom, otherwise→COLMAP),
runs the photo QA, and launches the right engine — no network, no model calls,
repeatable for every future scan at zero token cost. Recommend it whenever the
user's concern is cost or repeat usage.

For truly zero *local* compute as well, the free mobile apps (RealityScan,
Polycam in `references/tools.md`) process in their own cloud for free — also no
Claude tokens involved.

## Output formats

All paths produce a textured mesh exportable to **OBJ / FBX / STL** (OBJ+PNG
texture is the safe interchange default). STL for 3D printing carries geometry
only — no color. Point the user to a mesh cleanup pass (Blender, MeshLab) to
close small holes and decimate before printing or game use.

## Quick reference of what each file is for

- `references/tools.md` — Meshroom vs COLMAP vs mobile: install, hardware,
  trade-offs, official GitHub links.
- `references/capture-guide.md` — how to shoot photos that reconstruct,
  including the minimal-photo (~10) strategy and a pre-shoot checklist.
- `scripts/run.sh` — one-command, offline, zero-token runner: QA + auto engine
  selection + reconstruction.
- `scripts/check_photos.py` — pre-flight QA: blur + exposure + set-size check.
- `scripts/run_colmap.sh` — headless COLMAP CLI pipeline.
- `scripts/run_meshroom.sh` — headless Meshroom (`meshroom_batch`) pipeline.
