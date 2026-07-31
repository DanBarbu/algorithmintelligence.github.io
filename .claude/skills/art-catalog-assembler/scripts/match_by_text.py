#!/usr/bin/env python3
"""Match placeholders to slides by caption-text similarity (not position).

Use this instead of build_mapping.py when the images PDF was extracted with
extract_pdf_slides.py (i.e. it has real per-slide caption text). Text
matching is far more reliable than position when the slide deck isn't in
manuscript order -- which is the common case for a curator's working deck.

Algorithm: score every (placeholder, slide) pair by normalized text
similarity, then greedily assign highest-scoring pairs first, each side
used at most once. A pair below --min-score is never assigned.

Caveats worth knowing before trusting the output blindly:
  - Greedy assignment is not globally optimal: a slide can get "stolen" by
    a mediocre match before the placeholder it actually belongs to gets a
    turn, forcing that placeholder onto a worse leftover. This shows up as
    a cluster of low-score rows that are actually wrong, sitting next to a
    cluster of low-score rows that are actually right (just diluted by
    extra prose in the slide caption, e.g. gift/provenance details). Both
    look the same from the score alone -- read the flagged rows.
  - Slides with more than one embedded image (see extract_pdf_slides.py)
    are matched using their first image only. If a placeholder's real match
    is the *second* image on a slide already claimed by another
    placeholder via its first image, this script will not find it --
    resolve those by hand (check the manifest's "images" list for that
    page and edit the CSV's image_file column).

Usage:
    python match_by_text.py placeholders.json slides_manifest.json mapping.csv \
        [--min-score 0.3] [--review-below 0.5]
"""
import argparse
import csv
import json
import re
from difflib import SequenceMatcher


def normalize(s):
    s = s.replace("\n", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("placeholders_json")
    ap.add_argument("slides_manifest_json")
    ap.add_argument("out_csv")
    ap.add_argument("--min-score", type=float, default=0.30)
    ap.add_argument("--review-below", type=float, default=0.55)
    args = ap.parse_args()

    placeholders = json.load(open(args.placeholders_json, encoding="utf-8"))
    slides = json.load(open(args.slides_manifest_json, encoding="utf-8"))

    pairs = []
    for ph in placeholders:
        pn = normalize(ph["description"])
        for sl in slides:
            if not sl["images"]:
                continue
            sn = normalize(sl["text"])
            score = SequenceMatcher(None, pn, sn).ratio()
            pairs.append((score, ph["seq"], sl["page"]))
    pairs.sort(key=lambda x: -x[0])

    used_ph, used_sl = set(), set()
    assigned = {}
    for score, ph_seq, sl_page in pairs:
        if ph_seq in used_ph or sl_page in used_sl or score < args.min_score:
            continue
        used_ph.add(ph_seq)
        used_sl.add(sl_page)
        assigned[ph_seq] = (sl_page, score)

    slides_by_page = {s["page"]: s for s in slides}
    rows = []
    for ph in placeholders:
        seq = ph["seq"]
        if seq in assigned:
            sl_page, score = assigned[seq]
            slide = slides_by_page[sl_page]
            rows.append({
                "seq": seq, "description": ph["description"],
                "image_file": slide["images"][0]["file"],
                "source_page": sl_page,
                "confidence": round(score, 2),
                "flag": "REVIEW_LOW_SCORE" if score < args.review_below else "",
                "hyperlink": slide["urls"][0] if slide["urls"] else "",
                "multi_image_page": len(slide["images"]) > 1,
            })
        else:
            rows.append({
                "seq": seq, "description": ph["description"], "image_file": "",
                "source_page": "", "confidence": "", "flag": "UNMATCHED_PLACEHOLDER",
                "hyperlink": "", "multi_image_page": False,
            })

    for sl in slides:
        if sl["page"] not in used_sl and sl["images"]:
            rows.append({
                "seq": "", "description": "", "image_file": sl["images"][0]["file"],
                "source_page": sl["page"], "confidence": "", "flag": "UNUSED_SLIDE",
                "hyperlink": sl["urls"][0] if sl["urls"] else "",
                "multi_image_page": len(sl["images"]) > 1,
            })

    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["seq", "description", "image_file", "source_page",
                                           "confidence", "flag", "hyperlink", "multi_image_page"])
        w.writeheader()
        w.writerows(rows)

    n_ok = sum(1 for r in rows if r["confidence"] != "" and not r["flag"])
    n_review = sum(1 for r in rows if r["flag"] == "REVIEW_LOW_SCORE")
    n_unmatched = sum(1 for r in rows if r["flag"] == "UNMATCHED_PLACEHOLDER")
    n_unused = sum(1 for r in rows if r["flag"] == "UNUSED_SLIDE")
    n_multi = sum(1 for r in rows if r["multi_image_page"])
    print(f"Wrote {len(rows)} rows -> {args.out_csv}: {n_ok} confident, {n_review} to review, "
          f"{n_unmatched} unmatched placeholders, {n_unused} unused slides, "
          f"{n_multi} rows on a multi-image page (check the manifest by hand)")


if __name__ == "__main__":
    main()
