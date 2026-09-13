"""Sampling footprint for phase1-dataset-build 2.1-2.2. Wider footprint: Chaco departments via
FAO GAUL (no new file needed). Held-out: Filadelfia box, distant from the AOI but same
vegetation, reserved for the generalization check (phase5-predictive-model).

Usage: .venv/bin/python scripts/03_define_sampling_footprint.py -> writes
data/study_area/sampling_footprint.png (not versioned)."""

import json
import urllib.request
from pathlib import Path

import ee

import gee_session

AOI_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "aoi.geojson"
OUT_PNG = Path(__file__).resolve().parents[1] / "data" / "study_area" / "sampling_footprint.png"

CHACO_DEPARTMENTS = ["Alto Paraguay", "Boqueron", "Presidente Hayes"]

# Filadelfia, Boqueron, approximate town-center coords, not a surveyed boundary.
HELDOUT_CENTER = (-60.03, -22.35)  # (lon, lat)
HELDOUT_HALF_WIDTH_DEG = (0.20, 0.18)  # ~40km x 40km box at this latitude


def load_aoi():
    geojson = json.loads(AOI_PATH.read_text())
    return ee.Geometry(geojson["features"][0]["geometry"])


def main():
    gee_session.init()

    gaul = ee.FeatureCollection("FAO/GAUL/2015/level1")
    chaco = gaul.filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Paraguay"),
            ee.Filter.inList("ADM1_NAME", CHACO_DEPARTMENTS),
        )
    )
    footprint = chaco.geometry().dissolve()
    footprint_area_ha = footprint.area().divide(10_000).getInfo()
    print(f"Wider Chaco footprint ({', '.join(CHACO_DEPARTMENTS)}): {footprint_area_ha:,.0f} ha")

    lon, lat = HELDOUT_CENTER
    dlon, dlat = HELDOUT_HALF_WIDTH_DEG
    heldout = ee.Geometry.Rectangle([lon - dlon, lat - dlat, lon + dlon, lat + dlat])
    heldout_in_footprint = heldout.intersection(footprint, ee.ErrorMargin(1))
    heldout_area_ha = heldout_in_footprint.area().divide(10_000).getInfo()
    print(f"Held-out sub-region (Filadelfia, Boqueron, approx.): {heldout_area_ha:,.0f} ha")

    aoi = load_aoi()
    overlap_ha = aoi.intersection(heldout, ee.ErrorMargin(1)).area().divide(10_000).getInfo()
    print(f"AOI/held-out overlap: {overlap_ha:.4f} ha (expect ~0)")
    if overlap_ha > 1:
        raise SystemExit("Held-out sub-region overlaps the AOI — pick a different location.")

    canvas = ee.Image(0).mask(0)
    footprint_img = canvas.paint(chaco, "0f766e", 2)  # teal outline
    aoi_img = canvas.paint(ee.FeatureCollection([ee.Feature(aoi)]), "c2410c", 3)  # rust outline
    heldout_img = canvas.paint(ee.FeatureCollection([ee.Feature(heldout_in_footprint)]), "1e3a8a", 3)  # blue outline
    combined = ee.ImageCollection([footprint_img, aoi_img, heldout_img]).mosaic()

    url = combined.getThumbUrl({
        "region": footprint.bounds(),
        "dimensions": 900,
        "format": "png",
    })
    urllib.request.urlretrieve(url, OUT_PNG)
    print(f"Map written to {OUT_PNG}")


if __name__ == "__main__":
    main()
