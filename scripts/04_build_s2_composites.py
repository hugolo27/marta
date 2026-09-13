"""Sentinel-2 cloud-free composites, phase1-dataset-build 3.1-3.4. Dry-season 2019+2023: 2018
dropped after a real scene-count check found only 14 L2A scenes that year vs. 73 in 2019 (usable
archive for this tile starts later than assumed). Cloud mask via SCL, per-pixel not per-scene.

Usage: .venv/bin/python scripts/04_build_s2_composites.py -> writes
data/study_area/composite_<period>.png (not versioned)."""

import urllib.request
from pathlib import Path

import ee

import gee_session
import s2_utils

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"

PERIODS = {
    "2019": ("2019-06-01", "2019-09-30"),  # dry season
    "2023": ("2023-06-01", "2023-09-30"),
}


def main():
    gee_session.init()
    aoi = s2_utils.load_aoi()

    for period, (start, end) in PERIODS.items():
        raw = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(start, end)
        )
        n_scenes = raw.size().getInfo()
        avg_cloud_pct = raw.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo()

        composite = s2_utils.build_s2_composite(aoi, start, end, add_ndvi=True, raise_on_gap=False).clip(aoi)
        gap = s2_utils.gap_fraction(composite, aoi)

        print(f"\n{period} ({start} to {end}):")
        print(f"  scenes considered: {n_scenes}")
        print(f"  avg scene-level cloud %: {avg_cloud_pct:.1f}" if avg_cloud_pct is not None else "  avg scene-level cloud %: n/a")
        print(f"  residual no-data gap over AOI after compositing: {gap:.2%}")

        if gap > s2_utils.MAX_GAP_FRACTION:
            print(f"  FLAG: gap exceeds {s2_utils.MAX_GAP_FRACTION:.0%} threshold — may need SAR or a wider date window")
        else:
            print(f"  OK: gap under {s2_utils.MAX_GAP_FRACTION:.0%} threshold")

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
