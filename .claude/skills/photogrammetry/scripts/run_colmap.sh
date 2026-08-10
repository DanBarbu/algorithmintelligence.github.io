#!/usr/bin/env bash
# Headless COLMAP photogrammetry pipeline: photos -> textured/poisson mesh.
#
# COLMAP works cross-platform (AMD, Intel, Mac; dense stereo optionally uses
# CUDA if present), which makes it the go-to when Meshroom's CUDA requirement
# is a problem. Each stage is printed so a failure is easy to localize; the
# usual root cause of a failed stage is upstream — too few matched features
# from thin overlap or soft focus — so revisit capture rather than the flags.
#
# Usage:
#   ./run_colmap.sh <images_dir> <workspace_dir>
#
# Requires COLMAP on PATH: https://github.com/colmap/colmap
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <images_dir> <workspace_dir>" >&2
  exit 1
fi

IMAGES="$1"
WORK="$2"

# ---- Tunables -------------------------------------------------------------
# GPU=1 uses CUDA for SIFT + dense stereo (much faster, NVIDIA only).
# GPU=0 forces CPU — set this on Mac/AMD/Intel-only machines.
GPU="${GPU:-1}"
# SINGLE_CAMERA=1 assumes every photo came from the same camera/lens (typical
# for one phone/DSLR); it stabilizes intrinsics estimation.
SINGLE_CAMERA="${SINGLE_CAMERA:-1}"
# --------------------------------------------------------------------------

command -v colmap >/dev/null 2>&1 || { echo "colmap not found on PATH" >&2; exit 1; }
[ -d "$IMAGES" ] || { echo "images dir not found: $IMAGES" >&2; exit 1; }

DB="$WORK/database.db"
SPARSE="$WORK/sparse"
DENSE="$WORK/dense"
mkdir -p "$WORK" "$SPARSE" "$DENSE"

echo "==> [1/6] Feature extraction"
colmap feature_extractor \
  --database_path "$DB" \
  --image_path "$IMAGES" \
  --ImageReader.single_camera "$SINGLE_CAMERA" \
  --SiftExtraction.use_gpu "$GPU"

echo "==> [2/6] Feature matching (exhaustive)"
colmap exhaustive_matcher \
  --database_path "$DB" \
  --SiftMatching.use_gpu "$GPU"

echo "==> [3/6] Sparse reconstruction (mapper)"
colmap mapper \
  --database_path "$DB" \
  --image_path "$IMAGES" \
  --output_path "$SPARSE"

# mapper writes model(s) to sparse/0, sparse/1, ... Use the first.
MODEL="$SPARSE/0"
[ -d "$MODEL" ] || { echo "No sparse model produced — likely too little overlap or soft focus. Revisit capture." >&2; exit 2; }

echo "==> [4/6] Undistort images for dense stereo"
colmap image_undistorter \
  --image_path "$IMAGES" \
  --input_path "$MODEL" \
  --output_path "$DENSE" \
  --output_type COLMAP

echo "==> [5/6] Dense stereo + fusion"
colmap patch_match_stereo \
  --workspace_path "$DENSE" \
  --workspace_format COLMAP \
  --PatchMatchStereo.geom_consistency true
colmap stereo_fusion \
  --workspace_path "$DENSE" \
  --workspace_format COLMAP \
  --input_type geometric \
  --output_path "$DENSE/fused.ply"

echo "==> [6/6] Meshing (Poisson)"
colmap poisson_mesher \
  --input_path "$DENSE/fused.ply" \
  --output_path "$DENSE/meshed-poisson.ply"

echo
echo "Done."
echo "  Dense point cloud : $DENSE/fused.ply"
echo "  Mesh              : $DENSE/meshed-poisson.ply"
echo "Open in MeshLab/Blender to clean up, then export OBJ/FBX/STL."
