# Free & open-source photogrammetry tools

All of these are genuine free alternatives to paid apps like Kiri Engine.
Kiri and similar apps run open-source SfM algorithms on rented cloud GPUs and
charge for that time plus an AI "gap-filling" step. Running locally removes the
fees and the watermark; the trade-off is you supply the compute and, for
minimal photo sets, you don't get the AI inpainting that hides sparse coverage.

## 1. Meshroom — the closest drag-and-drop replacement

- **Project:** AliceVision. GitHub: https://github.com/alicevision/Meshroom
- **Backing:** consortium of French research institutes and VFX studios.
- **Workflow:** drop photos into the left panel, press *Start*. A node graph
  runs the full pipeline automatically: Feature Extraction → Image Matching →
  Feature Matching → Structure-from-Motion → Depth Maps → Meshing → Texturing.
- **Output:** high-quality textured mesh — OBJ, FBX, STL, plus the dense point
  cloud.
- **Hardware catch:** dense reconstruction (depth maps) requires an **NVIDIA
  GPU with CUDA**. On AMD/Intel/Mac it will run the sparse steps and then stall
  or error at Depth Maps. There is a slower experimental non-CUDA path, but
  don't rely on it — steer those users to COLMAP.
- **Best for:** Windows/Linux users with an NVIDIA card who want the Kiri-like
  "drop and wait ~20 min" experience.
- **CLI:** `meshroom_batch --input <dir> --output <dir>` runs headless. See
  `scripts/run_meshroom.sh`.

## 2. COLMAP — the cross-platform gold standard

- **Project:** GitHub: https://github.com/colmap/colmap
- **Reputation:** the reference implementation much other software (including
  parts of the wider ecosystem, and NeRF/Gaussian-Splatting pipelines) is
  built on top of. Extremely accurate.
- **Workflow:** has a GUI but it's step-by-step, not one-click — Feature
  extraction → Feature matching → Sparse reconstruction (mapper) → Dense
  (`patch_match_stereo` + `stereo_fusion`) → Mesh (`poisson_mesher` /
  `delaunay_mesher`). Every stage is also a CLI subcommand.
- **Hardware:** runs on **AMD, Intel integrated graphics, and Macs** — it
  leans on the CPU (dense stereo optionally uses CUDA if present). Works
  literally everywhere, just slower than Meshroom on comparable jobs.
- **Trade-off:** steeper learning curve, utilitarian UI, longer runtimes.
- **Best for:** anyone without an NVIDIA GPU, or anyone who wants maximum
  accuracy and scriptability.
- **CLI:** fully scriptable — see `scripts/run_colmap.sh`.

## 3. More free desktop tools (when Meshroom/COLMAP don't fit)

Open-source photogrammetry is a whole ecosystem — if the two above are too
heavy, too CUDA-dependent, or too bare-bones, these are proven free options:

- **Regard3D** — https://www.regard3d.org (open-source, Win/macOS/Linux). A
  lightweight, fully-GUI SfM tool that needs **no GPU** — it runs on the CPU,
  so it's a gentle middle ground between Meshroom's CUDA requirement and
  COLMAP's steep UI. Best for smaller datasets on modest hardware.
- **3DF Zephyr Free** — https://www.3dflow.net/3df-zephyr-free/ (closed-source
  but genuinely free, Windows). Polished, friendly UI and often better
  out-of-the-box quality than the open-source tools. **Caps: 50 photos per
  project and a single GPU.** Great for small objects; the photo cap rules out
  large captures. Works with NVIDIA/AMD/Intel GPUs.
- **OpenDroneMap (ODM/WebODM)** — https://github.com/OpenDroneMap/ODM
  (open-source). The go-to for **aerial/drone and large-area** captures rather
  than tabletop objects; runs as a local web app.
- **OpenMVG** + **OpenMVS**, and **MicMac** (IGN) — open-source, advanced,
  scriptable toolchains. Powerful but command-line-heavy; reach for these only
  if COLMAP isn't giving you the control you need.

## 4. Mobile apps — stay on the phone (free tiers, know the catch)

Convenient for a first scan or a small portable object; processing happens in
the vendor's cloud, so no local compute. These are **not** open-source, and
their free tiers each have a real catch — check reviews before committing a
whole project to one.

- **KIRI Engine** (iOS/Android/web): despite being the paid app this workflow
  set out to replace, its **free tier is now unusually generous** — advertised
  unlimited scans and unlimited exports, no ads or output paywall. If you were
  avoiding it purely on cost, the free tier may already be enough. Cloud
  quotas/queue times can still apply at busy times.
- **Polycam** (iOS/Android/web): free plan is usable indefinitely but **caps
  each model at ~150 images, exports only `.gltf`, and share links are
  public-only.** Often beats other apps on small objects. Upgrade unlocks other
  formats (OBJ/FBX/STL).
- **RealityScan** (Epic Games, iOS/Android): free, no watermark — but **vet it
  first.** App-store rating sits around **2.66/5**, with recurring complaints
  of an **Epic-account login loop** (app bounces back to the sign-in screen),
  **cropping that forces the ground into the scan**, and **weaker results than
  rivals on the same photos** — exactly the "MVP without the workload" feel.
  Epic is actively patching it, so it's improving, but treat it as a
  try-before-you-rely option, not a default.

## Choosing quickly

- NVIDIA PC, want one-click → **Meshroom**.
- Mac / AMD / Intel-only, or maximum accuracy → **COLMAP**.
- Modest CPU-only machine, want a simple GUI → **Regard3D**.
- Windows, want polish and ≤50 photos → **3DF Zephyr Free**.
- Drone / large aerial area → **OpenDroneMap / WebODM**.
- Phone-only, want a generous free cloud tier → **KIRI Engine free tier**;
  **Polycam** for small objects (mind the `.gltf`-only export).
- Avoid depending on **RealityScan** until you've confirmed it works for you.

## After reconstruction

Clean up the mesh in **Blender** or **MeshLab** (both free): close small
holes, remove floating islands, decimate the triangle count, and re-bake or
re-project texture if needed. Export OBJ+PNG for interchange, FBX for game
engines, STL for 3D printing (geometry only, no color).
