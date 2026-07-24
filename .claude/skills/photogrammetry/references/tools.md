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

## 3. Mobile apps — stay on the phone

Good for a first scan or when the object is small and portable. Not
open-source, but free-tier and no local compute needed.

- **RealityScan** (by Epic Games, iOS/Android): completely free, no watermark.
  Walk around the object, it processes in the cloud, export the model to
  Sketchfab or to your computer. The most polished free rival to Kiri right
  now.
- **Polycam** (iOS/Android): has a paid Pro tier, but the free tier is
  generous and often beats Kiri on small objects.

## Choosing quickly

- NVIDIA PC → **Meshroom**.
- Mac / AMD / Intel-only → **COLMAP**.
- Phone-only or want the fastest first result → **RealityScan**.

## After reconstruction

Clean up the mesh in **Blender** or **MeshLab** (both free): close small
holes, remove floating islands, decimate the triangle count, and re-bake or
re-project texture if needed. Export OBJ+PNG for interchange, FBX for game
engines, STL for 3D printing (geometry only, no color).
