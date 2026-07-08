---
name: art-catalog-assembler
description: "Use this skill when assembling an art/artefact catalog from two source files: a Word document (.docx) containing the catalog text with image insertion points marked by a caption like 'Figure Placeholder: <description>', and a PDF containing the actual artefact/artwork images (typically one image per page) to be dropped into those insertion points. Triggers include: 'insert these images into the catalog', 'match the PDF images to the placeholders', 'assemble the catalog', or any request to merge a manuscript with figure placeholders and a PDF of photographs into a finished, print-ready document. Do NOT use for generic docx editing unrelated to image placeholders, or for PDFs that aren't a source of images to insert."
license: Proprietary. LICENSE.txt has complete terms
---

# Art Catalog Assembler

Merges a catalog manuscript (.docx, with image insertion points) and a PDF of
artefact photographs into a finished .docx with the real images inserted in
place of the placeholders.

## When the source docx looks like this

Each insertion point is two adjacent paragraphs:

```
[paragraph with one inline picture — the placeholder graphic]
[paragraph whose text starts with "Figure Placeholder: <description>"]
```

Often followed by a `Catalog Entry: ...` paragraph with medium/provenance —
leave that alone, it's real content, not a marker.

If your document uses a different marker phrase, pass `--marker "..."` to
every script below (must match exactly, including trailing colon).

## Pipeline

Run from this skill's `scripts/` directory (or reference full paths). Work
in a scratch directory — nothing here needs to touch the repo.

```bash
pip install -r ../requirements.txt   # python-docx, pymupdf — install once

# 1. List every insertion point in the manuscript, in reading order
python extract_placeholders.py catalog.docx placeholders.json

# 2. Extract one image per PDF page (largest embedded raster, or a full-page
#    render if the page has no embedded raster), in page order
python extract_pdf_images.py images.pdf extracted_images/ pdf_manifest.json

# 3. Propose a mapping: Nth placeholder <-> Nth image, by document/page order,
#    with a fuzzy-match confidence score against any text found on each PDF page
python build_mapping.py placeholders.json pdf_manifest.json mapping.csv

# 4. REVIEW mapping.csv before proceeding (see below) — then assemble
python assemble_catalog.py catalog.docx placeholders.json mapping.csv \
    extracted_images/ assembled_catalog.docx
```

## Always review `mapping.csv` before assembling

The default mapping is **strict positional pairing**: placeholder #N gets
image #N, assuming the PDF's page order matches the manuscript's insertion
order. This is usually correct for these workflows, but is a *guess* — it
is not verified against image content. Before running step 4:

1. Open `mapping.csv`. Check the `flag` column:
   - `UNMATCHED_PLACEHOLDER` / `UNUSED_IMAGE` — placeholder count and PDF
     page count didn't match. Resolve this first (a page is missing/extra
     in the PDF, or a placeholder in the manuscript has no photo yet) —
     don't just let positional pairing silently drift out of alignment
     past the mismatch point.
   - `LOW_CONFIDENCE` — the PDF page's text didn't resemble the placeholder
     description. Often harmless (the PDF page has no printed caption at
     all), but worth a manual look.
2. Spot-check a handful of `extracted_images/img_NNNN.*` files against
   their paired `description` — open a few images and read the text.
3. Hand-edit the `image_file` column for any row that's wrong (values must
   be filenames that exist in `extracted_images/`), or blank it out to
   leave that placeholder unfilled rather than wrong.

This matters more than usual for cultural-heritage / provenance catalogs:
a positionally-plausible but wrong pairing (e.g. one artist's work
captioned under another's) is a real attribution error, not just a cosmetic
one.

## What assembly does and doesn't touch

- Replaces only the placeholder picture's image data and resizes it to fit
  a bounding box (`--max-width-in` / `--max-height-in`, default 6"×8")
  while preserving the image's own aspect ratio (no stretching/distortion).
- Strips the `Figure Placeholder: ` prefix from the caption paragraph,
  leaving the description as a clean caption — all other text, styles,
  headings, and page setup in the manuscript are left completely alone
  (this is an in-place XML edit, not a document rebuild).
- Rows without a mapped image are left as the original grey placeholder box
  so unresolved gaps stay visible rather than silently vanishing.

## Verify the output

Preferred: render to PDF and look at it, same as the general docx skill —
```bash
soffice --headless --convert-to pdf assembled_catalog.docx
pdftoppm -jpeg -r 100 assembled_catalog.pdf page
```
then read a few `page-*.jpg` files.

If `soffice` isn't usable in the current sandbox (conversion fails even on
an untouched docx — check that first to confirm it's an environment issue
and not something this skill broke), fall back to inspecting the embedded
images directly: `unzip assembled_catalog.docx -d check/` and view
`check/word/media/*` for the ones that changed, or diff `document.xml`'s
`<wp:extent>`/`<a:blip r:embed>` values before/after.

## Notes on the extraction heuristics

- `extract_pdf_images.py` picks the **largest embedded raster image** on
  each page by pixel area, not necessarily the first one — handles pages
  with a small logo/watermark alongside the main photo. If a page has no
  embedded raster (vector art, or a flattened/scanned page with text baked
  in), it falls back to rendering the whole page at `--dpi` (default 300).
- Matching by fuzzy text similarity only works if the PDF pages actually
  have extractable caption text near the image — a pure photo scan with no
  text layer will score 0 on every row and that's expected, not a bug.
