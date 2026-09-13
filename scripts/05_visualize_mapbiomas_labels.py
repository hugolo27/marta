"""MapBiomas labels remapped to bosque/pasto/cultivo over the AOI, both periods
(phase1-dataset-build 4.1). Usage: .venv/bin/python scripts/05_visualize_mapbiomas_labels.py ->
writes data/study_area/labels_<period>.png (not versioned)."""

import json
import urllib.request
from pathlib import Path

import ee

import gee_session
import mapbiomas_legend

AOI_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "aoi.geojson"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"

PERIODS = ["2019", "2023"]

# 0=other (gray), 1=bosque (green), 2=pasto (tan), 3=cultivo (magenta)
PALETTE = ["9ca3af", "1f8d49", "edde8e", "e974ed"]


def load_aoi():
    geojson = json.loads(AOI_PATH.read_text())
    return ee.Geometry(geojson["features"][0]["geometry"])


def main():
    gee_session.init()
    aoi = load_aoi()
    mapbiomas = ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET)

    for period in PERIODS:
        band = f"classification_{period}"
        from_codes, to_codes = mapbiomas_legend.remap_expression(band)
        remapped = mapbiomas.select(band).remap(from_codes, to_codes, defaultValue=0).rename(band).clip(aoi)

        hist = remapped.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(), geometry=aoi, scale=30, bestEffort=True, maxPixels=1e9
        ).getInfo()
        counts = hist.get(band, {})
        print(f"\n{period} class counts (30m pixels): " + ", ".join(
            f"{mapbiomas_legend.CLASS_NAMES[int(k)]}={v:.0f}" for k, v in sorted(counts.items())
        ))

        thumb_url = remapped.getThumbUrl({
            "min": 0, "max": 3, "palette": PALETTE,
            "region": aoi, "dimensions": 700, "format": "png",
        })
        out_path = OUT_DIR / f"labels_{period}.png"
        urllib.request.urlretrieve(thumb_url, out_path)
        print(f"  thumbnail: {out_path}")


if __name__ == "__main__":
    main()
