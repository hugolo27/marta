"""Sentinel-2 cloud-free composites, phase1-dataset-build 3.1-3.4. Dry-season 2019+2023: 2018
dropped after a real scene-count check found only 14 L2A scenes that year vs. 73 in 2019 (usable
archive for this tile starts later than assumed). Cloud mask via SCL, per-pixel not per-scene.

Usage: .venv/bin/python scripts/build_s2_composites.py -> writes
data/study_area/composite_<period>.png (not versioned)."""

import json
import urllib.request
from pathlib import Path

import ee

import gee_session

AOI_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "aoi.geojson"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"

PERIODS = {
    "2019": ("2019-06-01", "2019-09-30"),  # dry season
    "2023": ("2023-06-01", "2023-09-30"),
}

S2_BANDS = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B9", "B11", "B12"]
CLOUD_FREE_SCL = [4, 5, 6, 7, 11]  # vegetation, bare soil, water, unclassified, snow
MAX_GAP_FRACTION = 0.05  # residual no-data after compositing, above this = real gap


def load_aoi():
    geojson = json.loads(AOI_PATH.read_text())
    return ee.Geometry(geojson["features"][0]["geometry"])


def mask_clouds(image):
    scl = image.select("SCL")
    clear = scl.remap(CLOUD_FREE_SCL, [1] * len(CLOUD_FREE_SCL), 0)
    return image.updateMask(clear)


def add_ndvi(image):
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    return image.addBands(ndvi)


def build_composite(aoi, start, end):
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start, end)
    )
    n_scenes = collection.size().getInfo()
    avg_cloud_pct = collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo()

    masked = collection.map(mask_clouds)
    composite = masked.select(S2_BANDS).median().clip(aoi)
    composite = add_ndvi(composite)

    gap_stats = (
        composite.select("B4")
        .mask()
        .Not()
        .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=30, bestEffort=True, maxPixels=1e9)
        .getInfo()
    )
    gap_fraction = gap_stats.get("B4", 0)

    return composite, n_scenes, avg_cloud_pct, gap_fraction


def main():
    gee_session.init()
    aoi = load_aoi()

    for period, (start, end) in PERIODS.items():
        composite, n_scenes, avg_cloud_pct, gap_fraction = build_composite(aoi, start, end)
        print(f"\n{period} ({start} to {end}):")
        print(f"  scenes considered: {n_scenes}")
        print(f"  avg scene-level cloud %: {avg_cloud_pct:.1f}" if avg_cloud_pct is not None else "  avg scene-level cloud %: n/a")
        print(f"  residual no-data gap over AOI after compositing: {gap_fraction:.2%}")

        if gap_fraction > MAX_GAP_FRACTION:
            print(f"  FLAG: gap exceeds {MAX_GAP_FRACTION:.0%} threshold — may need SAR or a wider date window")
        else:
            print(f"  OK: gap under {MAX_GAP_FRACTION:.0%} threshold")

        thumb_url = composite.getThumbUrl({
            "bands": ["B4", "B3", "B2"],
            "min": 0,
            "max": 3000,
            "region": aoi,
            "dimensions": 700,
            "format": "png",
        })
        out_path = OUT_DIR / f"composite_{period}.png"
        urllib.request.urlretrieve(thumb_url, out_path)
        print(f"  thumbnail: {out_path}")


if __name__ == "__main__":
    main()
