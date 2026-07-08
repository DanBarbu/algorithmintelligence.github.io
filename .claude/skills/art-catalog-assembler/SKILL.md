---
name: art-catalog-assembler
description: "Use this skill when assembling an art/artefact catalog from two source files: a Word document (.docx) containing the catalog text with image insertion points marked by a caption like 'Figure Placeholder: <description>', and a PDF containing the actual artefact/artwork images to be dropped into those insertion points (either a plain photo-per-page PDF, or a slide-deck export with per-item caption text and source hyperlinks). Triggers include: 'insert these images into the catalog', 'match the PDF images to the placeholders', 'assemble the catalog', 'add the source/hyperlink under each image', or any request to merge a manuscript with figure placeholders and a PDF of photographs into a finished, print-ready document. Do NOT use for generic docx editing unrelated to image placeholders, or for PDFs that aren't a source of images to insert."
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

## Two source-PDF shapes, two matching strategies

**Plain photo scan** (one photo per page, no text layer): use
`extract_pdf_images.py` + `build_mapping.py`, which default to strict
positional pairing (placeholder #N ↔ image #N). This only works if the PDF
happens to be in manuscript order — often it isn't (a curator's working
photo dump rarely matches chapter order), so treat the output as a
starting guess, not an answer.

**Slide-deck export** (one slide per artefact, with a caption / title /
region label, and sometimes a source hyperlink — e.g. exported from
PowerPoint/Keynote research slides): use `extract_pdf_slides.py` +
`match_by_text.py` instead. This matches by comparing each placeholder's
description text against each slide's caption text, independent of page
order — dramatically higher confidence than position when the deck isn't
already in manuscript order, and it carries any hyperlink through to the
final CSV so it can be inserted as a source citation.

If you have **both** kinds of PDF for the same catalog, prefer the
slide-deck one — its image and caption are guaranteed paired 1:1 on the
same page, which the plain photo scan can't offer.

```bash
pip install -r ../requirements.txt   # python-docx, pymupdf — install once

# 1. List every insertion point in the manuscript, in reading order
python extract_placeholders.py catalog.docx placeholders.json

# 2a. Plain photo-per-page PDF:
python extract_pdf_images.py images.pdf extracted_images/ pdf_manifest.json
python build_mapping.py placeholders.json pdf_manifest.json mapping.csv

# 2b. OR a slide-deck PDF with per-item captions/hyperlinks:
python extract_pdf_slides.py deck.pdf slides/ slides_manifest.json
python match_by_text.py placeholders.json slides_manifest.json mapping.csv

# 3. REVIEW mapping.csv before proceeding (see below) — then assemble
python assemble_catalog.py catalog.docx placeholders.json mapping.csv \
    extracted_images/ assembled_catalog.docx   # or slides/ for the 2b path
```

## Always review `mapping.csv` before assembling

Whichever matcher you used, its output is a *proposal*, not verified
ground truth. Before running the assemble step:

1. Open `mapping.csv`. Check the `flag` column:
   - `UNMATCHED_PLACEHOLDER` / `UNUSED_IMAGE` / `UNUSED_SLIDE` — counts
     didn't match on one side. Resolve this first — don't let pairing
     silently drift out of alignment past the mismatch point.
   - `LOW_CONFIDENCE` (from `build_mapping.py`) / `REVIEW_LOW_SCORE` (from
     `match_by_text.py`) — worth a manual look, but **not automatically
     wrong**. A low text-similarity score is also what a *genuine* match
     looks like when the slide caption has a lot of extra prose (gift/
     provenance details) diluting the ratio, or when both strings are very
     short. Read the actual text/image before discarding a flagged row.
   - Rows can also be **wrong despite a decent score**: `match_by_text.py`
     assigns greedily (highest-scoring pairs first), so a placeholder can
     have its true match "stolen" by another placeholder that scored
     slightly higher against the same slide, and gets shunted onto a bad
     leftover instead. This tends to cluster a few genuinely-wrong rows
     next to genuinely-right-but-low-scoring ones — same-looking numbers,
     different cause. Spot check, don't just threshold on the score.
   - `multi_image_page` = True means that PDF page had more than one
     embedded image (a wide exhibition shot with several sub-photos, or
     two related items captioned on one slide). Only the first image was
     auto-picked; check `slides_manifest.json`'s `images` list for that
     page and fix the `image_file` column by hand if a different one (or
     more than one placeholder reusing the same one) is correct.
2. Spot-check a handful of extracted image files against their paired
   `description` — open a few and read them.
3. Hand-edit the `image_file` column for any row that's wrong, or blank it
   out to leave that placeholder unfilled rather than wrong. The same
   image file can legitimately be reused across multiple rows (e.g. one
   photo showing two objects that the manuscript describes as separate
   placeholders).

This matters more than usual for cultural-heritage / provenance catalogs:
a plausible-looking but wrong pairing (e.g. one artist's work captioned
under another's, or a Fijian object mislabeled as Solomon Islands) is a
real attribution error, not just a cosmetic one.

## What assembly does and doesn't touch

- Replaces only the placeholder picture's image data and resizes it to fit
  a bounding box (`--max-width-in` / `--max-height-in`, default 6"×8")
  while preserving the image's own aspect ratio (no stretching/distortion).
- Strips the `Figure Placeholder: ` prefix from the caption paragraph,
  leaving the description as a clean caption — all other text, styles,
  headings, and page setup in the manuscript are left completely alone
  (this is an in-place XML edit, not a document rebuild).
- If a row has a non-empty `hyperlink` column, inserts a new paragraph
  right after the caption with a clickable "Source: <url>" link (real
  `w:hyperlink` + external relationship, not just plain text) — useful for
  carrying provenance/auction-listing links from a slide deck into the
  final catalog. This step runs as a second pass in descending paragraph-
  index order (it changes paragraph *count*, unlike the image/caption
  edits, so order matters — see the comment in `insert_source_line()` if
  modifying this).
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
