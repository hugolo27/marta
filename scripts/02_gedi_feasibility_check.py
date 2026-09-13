"""GEDI L4A feasibility check over the study area AOI (one-off go/no-go for
phase1-define-study-area task 3). Counts footprints actually inside the AOI polygon, not just
granules touching its bounding box, and reports the quality-flag pass rate.

Usage: .venv/bin/python scripts/02_gedi_feasibility_check.py (needs EARTHDATA_USERNAME/PASSWORD
in .env)."""

import json
from pathlib import Path

import earthaccess
import h5py
import numpy as np
from dotenv import load_dotenv
from pyproj import Geod
from shapely.geometry import Point, shape

AOI_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "aoi.geojson"
SHORT_NAME = "GEDI_L4A_AGB_Density_V3_2508"
VERSION = "3"
TEMPORAL = ("2019-04-01", None)  # full GEDI L4A mission to date


def load_aoi():
    geojson = json.loads(AOI_PATH.read_text())
    return shape(geojson["features"][0]["geometry"])


def aoi_area_ha(aoi):
    geod = Geod(ellps="WGS84")
    area_m2, _ = geod.geometry_area_perimeter(aoi)
    return abs(area_m2) / 10_000


def count_footprints_in_granule(fp, aoi):
    minx, miny, maxx, maxy = aoi.bounds
    total, quality_ok = 0, 0
    with h5py.File(fp, "r") as f:
        for beam in [k for k in f if k.startswith("BEAM")]:
            grp = f[beam]
            if "lat_lowestmode" not in grp:
                continue
            lats = grp["lat_lowestmode"][:]
            lons = grp["lon_lowestmode"][:]
            quality = grp["l4a_quality_flag_rel3"][:]
            in_bbox = np.where((lons >= minx) & (lons <= maxx) & (lats >= miny) & (lats <= maxy))[0]
            for i in in_bbox:
                if aoi.contains(Point(lons[i], lats[i])):
                    total += 1
                    quality_ok += int(quality[i] == 1)
    return total, quality_ok


def main():
    load_dotenv()
    earthaccess.login(strategy="environment")

    aoi = load_aoi()
    area_ha = aoi_area_ha(aoi)
    minx, miny, maxx, maxy = aoi.bounds

    results = earthaccess.search_data(
        short_name=SHORT_NAME,
        version=VERSION,
        bounding_box=(minx, miny, maxx, maxy),
        temporal=TEMPORAL,
    )
    print(f"AOI area: {area_ha:.0f} ha")
    print(f"Granules with bbox intersecting AOI, {TEMPORAL[0]} to present: {len(results)}")

    if not results:
        print("\nGO/NO-GO: NO-GO — no granules found. Widen the AOI or fall back to Chaco Vivo (task 3.3).")
        return

    files = earthaccess.open(results)
    total_footprints, total_quality_ok = 0, 0
    for fp, granule in zip(files, results):
        try:
            footprints, quality_ok = count_footprints_in_granule(fp, aoi)
        except Exception as e:
            print(f"  skipped a granule, failed to read: {e}")
            continue
        total_footprints += footprints
        total_quality_ok += quality_ok
        if footprints:
            print(f"  {granule['meta']['native-id']}: {footprints} footprints in AOI, {quality_ok} pass l4a_quality_flag_rel3")

    density = total_footprints / area_ha * 100 if area_ha else 0
    print(f"\nTotal GEDI L4A footprints inside AOI polygon: {total_footprints}")
    print(f"Passing l4a_quality_flag_rel3 == 1: {total_quality_ok}")
    print(f"Density: {density:.2f} footprints per 100 ha")


if __name__ == "__main__":
    main()
