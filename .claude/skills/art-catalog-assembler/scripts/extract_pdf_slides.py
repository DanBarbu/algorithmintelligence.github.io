#!/usr/bin/env python3
"""Extract image + caption text + hyperlink(s) from a "slide deck" PDF.

Unlike a plain photo-scan PDF, some source PDFs are exports of a slide deck
(e.g. one slide per artefact: a region label, an artwork title/artist, the
photo, and a hyperlink to a source/provenance page). This script extracts
all three per page, which enables much higher-confidence text-based
matching (see match_by_text.py) instead of position-based guessing, and
lets hyperlinks be carried into the assembled catalog as source citations.

If a page has more than one embedded image (e.g. a wide exhibition-room
shot with several sub-photos, or two related items on one slide), all of
them are extracted -- not just the largest -- since any one of them might
be the one that actually matches a given placeholder. See --help output of
match_by_text.py for how multi-image pages are handled.

Usage:
    python extract_pdf_slides.py deck.pdf out_dir manifest.json
"""
import argparse
import json
import os

import fitz  # PyMuPDF


def extract(pdf_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    manifest = []

    for page_index, page in enumerate(doc):
        text = page.get_text().strip()

        urls = []
        for link in page.get_links():
            uri = link.get("uri")
            if uri and uri not in urls:
                urls.append(uri)

        images = page.get_images(full=True)
        files = []
        for img_index, img in enumerate(images):
            xref = img[0]
            info = doc.extract_image(xref)
            fname = f"slide_{page_index:04d}_{img_index}.{info['ext']}"
            with open(os.path.join(out_dir, fname), "wb") as f:
                f.write(info["image"])
            files.append({"file": fname, "width": info["width"], "height": info["height"]})

        manifest.append({
            "page": page_index,
            "text": text,
            "urls": urls,
            "images": files,
        })

    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("out_dir")
    ap.add_argument("manifest_json")
    args = ap.parse_args()

    manifest = extract(args.pdf_path, args.out_dir)

    with open(args.manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    n_multi = sum(1 for m in manifest if len(m["images"]) > 1)
    n_links = sum(1 for m in manifest if m["urls"])
    print(f"Extracted {len(manifest)} slides -> {args.out_dir} "
          f"({n_multi} slides with >1 image, {n_links} slides with a hyperlink)")


if __name__ == "__main__":
    main()
