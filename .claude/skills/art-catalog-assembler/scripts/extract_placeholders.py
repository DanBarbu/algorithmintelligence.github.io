#!/usr/bin/env python3
"""Scan a catalog .docx and list every image insertion point in document order.

An insertion point is a paragraph containing a single inline picture, whose
*next* sibling paragraph's text starts with a marker prefix (default
"Figure Placeholder:"). The text after the marker is the artwork
description used later for caption text and fuzzy matching.

Usage:
    python extract_placeholders.py catalog.docx placeholders.json [--marker "Figure Placeholder:"]
"""
import argparse
import json
import sys

from docx import Document

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def find_placeholders(doc, marker):
    paras = doc.paragraphs
    results = []
    seq = 0
    for i, p in enumerate(paras):
        text = p.text.strip()
        if not text.startswith(marker):
            continue
        description = text[len(marker):].strip()

        # The picture lives in the nearest preceding paragraph that contains
        # exactly one drawing. Usually that's the immediately previous paragraph.
        picture_para_index = None
        for j in range(i - 1, max(i - 4, -1), -1):
            n_drawings = len(paras[j]._p.findall(f".//{{{W_NS}}}drawing"))
            if n_drawings >= 1:
                picture_para_index = j
                break
            if paras[j].text.strip():
                break  # hit real content without a drawing; stop looking

        if picture_para_index is None:
            print(f"WARNING: no picture paragraph found for placeholder at "
                  f"paragraph {i}: {description!r}", file=sys.stderr)
            continue

        results.append({
            "seq": seq,
            "caption_paragraph_index": i,
            "picture_paragraph_index": picture_para_index,
            "description": description,
        })
        seq += 1
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx_path")
    ap.add_argument("out_json")
    ap.add_argument("--marker", default="Figure Placeholder:")
    args = ap.parse_args()

    doc = Document(args.docx_path)
    placeholders = find_placeholders(doc, args.marker)

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(placeholders, f, indent=2, ensure_ascii=False)

    print(f"Found {len(placeholders)} image insertion points -> {args.out_json}")


if __name__ == "__main__":
    main()
