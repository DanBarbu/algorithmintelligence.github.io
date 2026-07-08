#!/usr/bin/env python3
"""Propose a placeholder -> extracted-image mapping for manual review.

Default strategy is strict positional pairing: the Nth placeholder (in
document reading order) gets the Nth image (in PDF page order). This is
the right default when the images PDF was assembled in the same order as
the catalog manuscript, which is the common case for these workflows.

For every pair we also compute a fuzzy text-similarity score between the
placeholder's description and any text found on the source PDF page, as a
sanity check. Low scores don't necessarily mean a wrong pairing (the PDF
page may simply have no printed caption), but a low score is worth a human
glance before the final assembly step.

Writes a CSV that a human can hand-edit (to fix the `image_file` column)
before running assemble_catalog.py.

Usage:
    python build_mapping.py placeholders.json pdf_manifest.json mapping.csv
"""
import argparse
import csv
import json
from difflib import SequenceMatcher


def similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("placeholders_json")
    ap.add_argument("pdf_manifest_json")
    ap.add_argument("out_csv")
    args = ap.parse_args()

    placeholders = json.load(open(args.placeholders_json, encoding="utf-8"))
    images = json.load(open(args.pdf_manifest_json, encoding="utf-8"))

    n_ph, n_img = len(placeholders), len(images)
    if n_ph != n_img:
        print(f"WARNING: {n_ph} placeholders but {n_img} extracted images. "
              f"Positional pairing will be misaligned past the shorter list "
              f"-- resolve the count mismatch (missing/extra page in the PDF?) "
              f"and/or hand-edit the CSV before assembling.")

    rows = []
    n = min(n_ph, n_img)
    for i in range(n):
        ph = placeholders[i]
        img = images[i]
        score = similarity(ph["description"], img.get("page_text", ""))
        rows.append({
            "seq": ph["seq"],
            "description": ph["description"],
            "image_file": img["file"],
            "source_page": img["source_page"],
            "confidence": round(score, 2),
            "flag": "LOW_CONFIDENCE" if score < 0.15 and img.get("page_text") else "",
        })

    # anything left over on either side, surfaced so nothing silently drops
    for ph in placeholders[n:]:
        rows.append({
            "seq": ph["seq"], "description": ph["description"],
            "image_file": "", "source_page": "", "confidence": "",
            "flag": "UNMATCHED_PLACEHOLDER",
        })
    for img in images[n:]:
        rows.append({
            "seq": "", "description": "", "image_file": img["file"],
            "source_page": img["source_page"], "confidence": "",
            "flag": "UNUSED_IMAGE",
        })

    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "seq", "description", "image_file", "source_page", "confidence", "flag"])
        writer.writeheader()
        writer.writerows(rows)

    n_flagged = sum(1 for r in rows if r["flag"])
    print(f"Wrote {len(rows)} rows -> {args.out_csv} ({n_flagged} flagged for review)")


if __name__ == "__main__":
    main()
