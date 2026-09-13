"""Shared Sentinel-2 compositing: AOI loading, cloud masking, gap-checked composite build.
Single source for what was duplicated across 04_build_s2_composites.py, 08_assemble_dataset.py,
06_align_3x3_patches.py, and 13_visualize_classification_map.py."""

import json
from pathlib import Path

import ee

REPO_ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = REPO_ROOT / "data" / "study_area" / "aoi.geojson"

S2_BANDS = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B9", "B11", "B12"]
CLOUD_FREE_SCL = [4, 5, 6, 7, 11]
MAX_GAP_FRACTION = 0.05


def load_aoi():
    geojson = json.loads(AOI_PATH.read_text())
    return ee.Geometry(geojson["features"][0]["geometry"])


def mask_clouds(image):
    scl = image.select("SCL")
    clear = scl.remap(CLOUD_FREE_SCL, [1] * len(CLOUD_FREE_SCL), 0)
    return image.updateMask(clear)


def gap_fraction(composite, region, band="B4"):
    """Fraction of the region with no valid pixel in `band`. Returns 1.0 (fully gapped), not
    None, when reduceRegion can't compute a mean at all (e.g. the region has zero valid data) —
    a raw None would blow up any `gap > threshold` comparison with a TypeError instead of the
    intended refusal (found via code review 2026-09-04)."""
    stats = (
        composite.select(band).mask().Not()
        .reduceRegion(reducer=ee.Reducer.mean(), geometry=region, scale=30, bestEffort=True, maxPixels=1e9)
        .getInfo()
    )
    value = stats.get(band)
    return 1.0 if value is None else value


def build_s2_composite(region, start, end, add_ndvi=True, raise_on_gap=False, reproject=True, clip=False):
    """Cloud-masked median composite. reproject=True snaps the composite onto S2's own native
    grid (needed for scale-dependent ops like sampleRectangle/reduceRegion on a single-tile
    region to behave correctly) — only valid when region sits within one UTM zone. For a region
    spanning multiple zones (e.g. the multi-department sampling footprint, or the Filadelfia
    held-out box which straddles UTM 20S/21S at -60 degrees), pass reproject=False: forcing the
    whole area onto one arbitrary scene's zone distorts points outside it (found via code review
    2026-09-03 for the sampling footprint, and again 2026-09-11 for Filadelfia — the same bug
    recurring because a new caller didn't carry the reasoning forward). sampleRegions() with an
    explicit scale still extracts pixels correctly either way, since scale is explicit there
    regardless of the composite's own declared projection metadata.
    clip=True masks the composite to region's exact geometry, not just whichever scenes
    intersect it. Needed whenever region has a carved-out hole (e.g. 08_assemble_dataset.py's
    sampling footprint with the Filadelfia rectangle excluded via .difference()) — without it, a
    sample point's 33x33 extraction window can reach past the hole's boundary and pull real,
    unmasked pixels from inside the excluded area, since region on its own only ever constrains
    which scenes get pulled in (.filterBounds) and where sample point centers may fall
    (stratifiedSample(region=...)), never which pixels the composite itself contains (found via
    code review 2026-09-11 — a plain .clip(region) that existed before this function was
    consolidated out of 4 duplicated call sites on 2026-09-03 was dropped in that merge). Off by
    default: several callers already clip externally right after this call, and a plain
    rectangle with no hole doesn't need it.
    raise_on_gap: refuse to return a composite with real cloud gaps instead of silently letting
    callers classify zero-filled/fabricated pixels — only meaningful for a small region where an
    averaged gap fraction isn't diluted into meaninglessness by a huge area."""
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start, end)
        .map(mask_clouds)
    )
    composite = collection.select(S2_BANDS).median()
    if reproject:
        s2_projection = collection.first().select("B4").projection()
        composite = composite.reproject(s2_projection)
    if clip:
        composite = composite.clip(region)

    if raise_on_gap:
        gap = gap_fraction(composite, region)
        if gap > MAX_GAP_FRACTION:
            raise RuntimeError(
                f"Composite has {gap:.1%} residual no-data gap over the region "
                f"(threshold {MAX_GAP_FRACTION:.0%}) — refusing to classify fabricated pixels."
            )

    if add_ndvi:
        ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
        composite = composite.addBands(ndvi)
    return composite
