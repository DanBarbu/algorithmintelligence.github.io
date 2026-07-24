#!/usr/bin/env python3
"""Pre-flight quality check for a photogrammetry photo set.

Photogrammetry reconstructions can take hours, and a handful of blurry or
badly exposed frames can quietly wreck feature matching. This script flags the
likely-bad frames *before* you commit to a run, so you can reshoot or drop
them.

For each image it reports:
  - sharpness  : variance of the Laplacian. Higher = sharper. Low values mean
                 soft focus or motion blur, which breaks feature detection.
  - brightness : mean luminance (0-255). Very low/high = under/over-exposed,
                 where texture detail is crushed.

Worst (blurriest) images are listed first. It also warns if the set is small,
since 10 photos is the bare minimum for a usable model.

Usage:
    python check_photos.py /path/to/photos [--blur-threshold 100]

Dependencies: opencv-python, numpy   (pip install opencv-python numpy)
"""
import argparse
import os
import sys

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit(
        "This script needs OpenCV and NumPy:\n"
        "    pip install opencv-python numpy"
    )

# Tune these to taste. Sharpness scale depends on resolution and content, so
# treat the threshold as relative: sort the list and look for the cliff.
DEFAULT_BLUR_THRESHOLD = 100.0   # variance-of-Laplacian below this = suspect
DARK_THRESHOLD = 40              # mean luminance below this = underexposed
BRIGHT_THRESHOLD = 220           # mean luminance above this = overexposed
MIN_RECOMMENDED = 20             # fewer than this tends to give patchy models

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def sharpness(gray):
    """Variance of the Laplacian — a standard, cheap focus measure."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def analyze(path):
    img = cv2.imread(path)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return {
        "path": path,
        "sharpness": sharpness(gray),
        "brightness": float(np.mean(gray)),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directory", help="folder containing the photos")
    ap.add_argument("--blur-threshold", type=float,
                    default=DEFAULT_BLUR_THRESHOLD,
                    help=f"sharpness below this is flagged (default {DEFAULT_BLUR_THRESHOLD})")
    args = ap.parse_args()

    if not os.path.isdir(args.directory):
        sys.exit(f"Not a directory: {args.directory}")

    files = sorted(
        os.path.join(args.directory, f)
        for f in os.listdir(args.directory)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )
    if not files:
        sys.exit(f"No images found in {args.directory}")

    results = [r for r in (analyze(f) for f in files) if r is not None]
    results.sort(key=lambda r: r["sharpness"])  # blurriest first

    print(f"\nAnalyzed {len(results)} image(s) in {args.directory}\n")
    print(f"{'sharpness':>10}  {'bright':>7}  flags  file")
    print("-" * 70)

    blurry = dark = bright = 0
    for r in results:
        flags = []
        if r["sharpness"] < args.blur_threshold:
            flags.append("BLUR")
            blurry += 1
        if r["brightness"] < DARK_THRESHOLD:
            flags.append("DARK")
            dark += 1
        if r["brightness"] > BRIGHT_THRESHOLD:
            flags.append("BRIGHT")
            bright += 1
        print(f"{r['sharpness']:10.1f}  {r['brightness']:7.1f}  "
              f"{','.join(flags) if flags else '-':6}  {os.path.basename(r['path'])}")

    print("\nSummary")
    print("-------")
    print(f"  total images : {len(results)}")
    print(f"  soft/blurry  : {blurry}  (below sharpness {args.blur_threshold})")
    print(f"  underexposed : {dark}")
    print(f"  overexposed  : {bright}")

    if len(results) < MIN_RECOMMENDED:
        print(f"\n  WARNING: only {len(results)} photos. 10 is the bare minimum "
              f"and usually gives a patchy model; {MIN_RECOMMENDED}+ is much safer.")
    if blurry:
        print("\n  Consider reshooting or removing the BLUR-flagged frames — "
              "soft focus breaks feature matching.")

    # Non-zero exit if anything looks bad, so this can gate a pipeline.
    sys.exit(1 if (blurry or dark or bright or len(results) < MIN_RECOMMENDED) else 0)


if __name__ == "__main__":
    main()
