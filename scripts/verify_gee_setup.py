"""GEE auth + AOI area sanity check (phase1-dataset-build 1.1-1.2). Usage: .venv/bin/python
scripts/verify_gee_setup.py"""

import json
from pathlib import Path

import ee

import gee_session

AOI_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "aoi.geojson"
EXPECTED_AREA_HA = 20_589
AREA_TOLERANCE_FRACTION = 0.01  # GEE's geodesic area calc differs slightly from pyproj's Geod


def main():
    gee_session.init()
    info = ee.Number(1).add(1).getInfo()
    print(f"ee.Initialize() ok, server round-trip returned: {info}")

    geojson = json.loads(AOI_PATH.read_text())
    aoi = ee.Geometry(geojson["features"][0]["geometry"])
    area_ha = aoi.area().divide(10_000).getInfo()
    print(f"AOI area from GEE: {area_ha:.1f} ha (expected ~{EXPECTED_AREA_HA} ha)")

    relative_diff = abs(area_ha - EXPECTED_AREA_HA) / EXPECTED_AREA_HA
    if relative_diff > AREA_TOLERANCE_FRACTION:
        raise SystemExit(
            f"AOI area mismatch: got {area_ha:.1f} ha, expected ~{EXPECTED_AREA_HA} ha "
            f"({relative_diff:.2%} off, tolerance {AREA_TOLERANCE_FRACTION:.0%})"
        )
    print("OK: auth verified, AOI area matches expectation.")


if __name__ == "__main__":
    main()
