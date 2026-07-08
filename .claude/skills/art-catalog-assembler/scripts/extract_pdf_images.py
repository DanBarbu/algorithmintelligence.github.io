#!/usr/bin/env python3
"""Extract one artefact image per page from a PDF, in page order.

For each page: prefer the largest embedded raster image (by pixel area).
If a page has no embedded raster image (e.g. it's a vector drawing or the
photo was flattened into the page content), fall back to rendering the
whole page to a PNG at the given DPI.

Writes images to out_dir/img_0001.png, img_0002.png, ... and a manifest
mapping each image to its source page and any text found on that page
(useful later for fuzzy-matching against catalog captions).

Usage:
    python extract_pdf_images.py images.pdf out_dir manifest.json [--dpi 300]
"""
import argparse
import json
import os

import fitz  # PyMuPDF


def extract(pdf_path, out_dir, dpi):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    manifest = []

    for page_index, page in enumerate(doc):
        images = page.get_images(full=True)
        chosen_pixmap = None

        if images:
            # pick the largest embedded image on the page by pixel area
            best = None
            best_area = -1
            for img in images:
                xref = img[0]
                info = doc.extract_image(xref)
                area = info["width"] * info["height"]
                if area > best_area:
                    best_area = area
                    best = info
            pix = fitz.Pixmap(best["image"])
            ext = best["ext"]
            raw_bytes = best["image"]
        else:
            pix = page.get_pixmap(dpi=dpi)
            ext = "png"
            raw_bytes = pix.tobytes("png")

        seq = len(manifest)
        out_name = f"img_{seq:04d}.{ext}"
        out_path = os.path.join(out_dir, out_name)
        with open(out_path, "wb") as f:
            f.write(raw_bytes)

        page_text = page.get_text().strip()

        manifest.append({
            "seq": seq,
            "source_page": page_index,  # 0-based
            "file": out_name,
            "width": pix.width,
            "height": pix.height,
            "page_text": page_text,
        })

    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("out_dir")
    ap.add_argument("manifest_json")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()

    manifest = extract(args.pdf_path, args.out_dir, args.dpi)

    with open(args.manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(manifest)} images -> {args.out_dir} "
          f"(manifest: {args.manifest_json})")


if __name__ == "__main__":
    main()
