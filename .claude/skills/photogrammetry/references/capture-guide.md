# Capture guide — shooting photos that actually reconstruct

Photogrammetry succeeds or fails at capture, not in the software. The engine
triangulates the 3D position of a surface point by seeing it in **several
sharp, overlapping photos from different angles**. Anything that breaks that —
blur, thin overlap, a face you never photographed, shifting shadows — turns
into missing or wrong geometry. Unlike AI-assisted phone apps (Kiri), the
open-source engines do **not** guess or inpaint what they couldn't see: a gap
in coverage is a literal hole in the mesh.

## The five rules

1. **Overlap ≥70%.** Each photo should share most of its content with the
   previous one. Move in small steps around the object; every surface point
   should land in at least 3–4 frames. Sparse, widely-spaced shots are the #1
   cause of failed reconstructions.

2. **Sharp focus, no motion blur.** Soft focus makes feature detection fail
   completely — the engine can't find the keypoints it matches between images.
   Use enough light for a fast shutter, brace or use a tripod, and check
   focus on the object (not the background). Run `scripts/check_photos.py` to
   catch soft frames before processing.

3. **Cover every surface — orbit plus poles.** Don't just walk a single circle
   at eye level. A reliable pattern for a tabletop object:
   - A ring at mid-height all the way around.
   - A higher ring angled **down** onto the top.
   - A lower ring angled **up** toward the base/underside.
   Rotate the object (or yourself) in small increments. Anything you never
   point the camera at won't exist in the model.

4. **Flat, diffuse lighting. No flash.** Even, shadow-free light (overcast
   sky, a brightly and evenly lit room, a light tent) is ideal. On-camera
   flash and hard directional light create shadows and specular hotspots that
   *move relative to the object* between shots, which confuses matching and
   bakes ugly lighting into the texture.

5. **More photos is cheaper than a failed scan.** Extra frames rarely hurt;
   too few reliably ruins the result. For a small object, 30–60 photos is a
   comfortable range. 10 is the bare minimum and usually looks patchy.

## Also helps

- **Matte, textured surfaces reconstruct best.** Shiny, transparent, or
  featureless surfaces (glass, chrome, a plain white mug) give the engine
  nothing to match. A dusting of matting spray or fine powder is a standard
  trick for difficult surfaces.
- **Keep the object still relative to its surroundings**, or use a plain
  turntable and mask the background. If both the object and background move
  between frames, alignment gets ambiguous.
- **Lock exposure/white balance** if your camera allows, so texture color is
  consistent across frames.
- **Shoot RAW or high-quality JPEG**; avoid heavy in-camera sharpening.

## Minimal-photo strategy (~10–15 photos)

If you truly can only get ~10 photos, maximize their value — and set
expectations that the result may still be incomplete:

1. **Overlap even more heavily** — aim well past 70%; each photo barely
   advances around the object.
2. **Zero tolerance for blur.** With so few frames, one soft photo is a large
   fraction of your data.
3. **The "north pole" spread:** e.g. ~4 photos around the middle, ~3 angled
   down at the top from different sides, ~3 angled up at the bottom. Spend your
   few frames on covering *all* faces rather than over-sampling one side.
4. **Diffuse light, no flash** — as above; with little data you can't afford
   shadow confusion.

Honest expectation: open-source tools need real visual coverage, so ~10 photos
tends to yield a patchy or holey model. If a clean result matters and you're
capped at ~10 photos, a mobile app with AI gap-filling (RealityScan) may do
better on that specific set than Meshroom/COLMAP.

## Pre-shoot checklist

- [ ] Object is matte / has surface texture (or has been matted).
- [ ] Lighting is even and diffuse; flash is OFF.
- [ ] Focus is locked and sharp on the object.
- [ ] Planned rings: mid, top-down, bottom-up.
- [ ] Small steps between shots → ≥70% overlap.
- [ ] Target photo count met (30–60 typical; 10 only if unavoidable).
- [ ] Exposure/white balance locked if possible.
