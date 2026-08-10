#!/usr/bin/env bash
# One-command, fully-local photogrammetry: photos -> textured 3D model.
#
# WHY THIS EXISTS: the reconstruction is compute-heavy but it runs entirely on
# YOUR machine (Meshroom/COLMAP) — it costs zero API/LLM tokens. Tokens are
# only spent if you ask Claude to drive each run. This script removes Claude
# from the loop: once you've picked your approach, run this and every future
# scan is free and offline. No network, no model calls.
#
# It auto-detects your hardware, runs the pre-flight photo QA, then launches
# the right engine:
#   - NVIDIA GPU with CUDA detected -> Meshroom (fast, drag-drop-equivalent)
#   - otherwise                     -> COLMAP  (cross-platform: Mac/AMD/Intel)
#
# Usage:
#   ./run.sh <images_dir> <output_dir>
#
# Env overrides:
#   ENGINE=meshroom|colmap   force a specific engine
#   SKIP_QA=1                skip the blur/exposure pre-check
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <images_dir> <output_dir>" >&2
  exit 1
fi
IMAGES="$1"
OUT="$2"
[ -d "$IMAGES" ] || { echo "images dir not found: $IMAGES" >&2; exit 1; }
mkdir -p "$OUT"

# ---- 1. Pre-flight QA (local, instant, no tokens) -------------------------
if [ "${SKIP_QA:-0}" != "1" ]; then
  if command -v python3 >/dev/null 2>&1; then
    echo "==> Pre-flight photo QA"
    # QA is advisory: a non-zero exit just means some frames look risky.
    python3 "$HERE/check_photos.py" "$IMAGES" || \
      echo "    (QA flagged issues above — review, then continue.)"
  else
    echo "==> Skipping QA (python3 not found)"
  fi
fi

# ---- 2. Choose engine -----------------------------------------------------
ENGINE="${ENGINE:-}"
if [ -z "$ENGINE" ]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    ENGINE="meshroom"
    echo "==> NVIDIA GPU detected -> using Meshroom"
  else
    ENGINE="colmap"
    echo "==> No CUDA GPU detected -> using COLMAP (cross-platform)"
  fi
fi

# ---- 3. Run the pipeline --------------------------------------------------
case "$ENGINE" in
  meshroom)
    exec "$HERE/run_meshroom.sh" "$IMAGES" "$OUT"
    ;;
  colmap)
    exec "$HERE/run_colmap.sh" "$IMAGES" "$OUT"
    ;;
  *)
    echo "Unknown ENGINE='$ENGINE' (use meshroom or colmap)" >&2
    exit 1
    ;;
esac
