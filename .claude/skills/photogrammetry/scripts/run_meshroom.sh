#!/usr/bin/env bash
# Headless Meshroom photogrammetry pipeline: photos -> textured mesh (OBJ).
#
# Meshroom (AliceVision) runs the whole default node graph — Feature
# Extraction, Matching, Structure-from-Motion, Depth Maps, Meshing, Texturing —
# in one command via meshroom_batch. This is the closest thing to the Kiri
# "drop photos, wait ~20 min, get a textured model" experience.
#
# HARDWARE: dense reconstruction (Depth Maps) needs an NVIDIA GPU with CUDA.
# On AMD/Intel/Mac this will run the sparse steps and then stall/error at
# depth maps — use COLMAP (scripts/run_colmap.sh) on those machines instead.
#
# Usage:
#   ./run_meshroom.sh <images_dir> <output_dir> [cache_dir]
#
# Requires Meshroom: https://github.com/alicevision/Meshroom
# meshroom_batch ships inside the Meshroom download; put it on PATH or set
# MESHROOM_BATCH to its full path.
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <images_dir> <output_dir> [cache_dir]" >&2
  exit 1
fi

IMAGES="$1"
OUT="$2"
CACHE="${3:-$OUT/cache}"

MESHROOM_BATCH="${MESHROOM_BATCH:-meshroom_batch}"

command -v "$MESHROOM_BATCH" >/dev/null 2>&1 || {
  echo "meshroom_batch not found. Put it on PATH or set MESHROOM_BATCH to its full path." >&2
  echo "It ships inside the Meshroom download from https://github.com/alicevision/Meshroom" >&2
  exit 1
}
[ -d "$IMAGES" ] || { echo "images dir not found: $IMAGES" >&2; exit 1; }
mkdir -p "$OUT" "$CACHE"

echo "==> Running Meshroom default pipeline (this can take 15+ minutes)…"
echo "    images : $IMAGES"
echo "    output : $OUT"
echo "    cache  : $CACHE"

# --input      : folder of photos
# --output     : where the final textured mesh (OBJ + texture) is written
# --cache      : intermediate node outputs (reuse to resume/inspect)
"$MESHROOM_BATCH" \
  --input "$IMAGES" \
  --output "$OUT" \
  --cache "$CACHE"

echo
echo "Done. Textured model (OBJ + texture) is in: $OUT"
echo "If it stalled at Depth Maps, your GPU likely lacks CUDA — use run_colmap.sh instead."
echo "Clean up in MeshLab/Blender, then export OBJ/FBX/STL as needed."
