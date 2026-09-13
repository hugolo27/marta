"""ESA WorldCover extraction, phase1-dataset-build 5.1-5.2. Reuses the Filadelfia held-out
sub-region (never used for training) as the independent accuracy cross-check area. WorldCover
has no managed-pasture-vs-natural-grassland split like MapBiomas does, so its Grassland (30)
class is only a weak proxy for "pasto" here (bosque/cultivo cross-checks are solid).

Usage: .venv/bin/python scripts/07_extract_worldcover.py"""

import json
import urllib.request
from pathlib import Path

import ee

import gee_session

AOI_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "aoi.geojson"
OUT_PNG = Path(__file__).resolve().parents[1] / "data" / "study_area" / "worldcover_heldout.png"

HELDOUT_CENTER = (-60.03, -22.35)
HELDOUT_HALF_WIDTH_DEG = (0.20, 0.18)

# WorldCover code -> our class (0=other, 1=bosque, 2=pasto [weak proxy], 3=cultivo)
FROM_CODES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]
TO_CODES = [1, 0, 2, 3, 0, 0, 0, 0, 0, 0, 0]
CLASS_NAMES = {0: "other", 1: "bosque", 2: "pasto (proxy debil)", 3: "cultivo"}


def load_aoi():
    geojson = json.loads(AOI_PATH.read_text())
    return ee.Geometry(geojson["features"][0]["geometry"])


def main():
    gee_session.init()
    aoi = load_aoi()

    lon, lat = HELDOUT_CENTER
    dlon, dlat = HELDOUT_HALF_WIDTH_DEG
    heldout = ee.Geometry.Rectangle([lon - dlon, lat - dlat, lon + dlon, lat + dlat])

    overlap_ha = aoi.intersection(heldout, ee.ErrorMargin(1)).area().divide(10_000).getInfo()
    print(f"AOI/held-out overlap: {overlap_ha:.4f} ha (must be ~0)")
    if overlap_ha > 1:
        raise SystemExit("Held-out area overlaps AOI training footprint — cross-check would be circular.")

    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    remapped = wc.remap(FROM_CODES, TO_CODES, defaultValue=0).rename("wc_class").clip(heldout)

    hist = remapped.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(), geometry=heldout, scale=10, bestEffort=True, maxPixels=1e9
    ).getInfo()
    counts = hist.get("wc_class", {})
    print("Held-out WorldCover class counts (10m pixels): " + ", ".join(
        f"{CLASS_NAMES[int(k)]}={v:.0f}" for k, v in sorted(counts.items())
    ))

    thumb_url = remapped.getThumbUrl({
        "min": 0, "max": 3, "palette": ["9ca3af", "1f8d49", "edde8e", "e974ed"],
        "region": heldout, "dimensions": 700, "format": "png",
    })
    urllib.request.urlretrieve(thumb_url, OUT_PNG)
    print(f"thumbnail: {OUT_PNG}")


if __name__ == "__main__":
    main()
