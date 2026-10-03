"""Draws the AOI reference sample for phase1-accuracy-assessment (task 3.1): stratified random
over the hardened forest/non-forest change map (19_temporal_change_map.py ->
change_map_2019_2023_fnf.npy), 50 loss / 50 gain / 100 stable forest / 75 stable non-forest.

Writes three files to data/study_area/accuracy_assessment/:
  aoi_sample.csv         -- the blind template the interpreter fills in: point id + coordinates,
                            no stratum, no map label (a stratum IS a map label here)
  aoi_sample.kml         -- same points plus a 0.5 ha square around each, for Google Earth Pro
  aoi_sample_design.csv  -- stratum, inclusion probability and map classes per point; the join
                            file 28_assess_aoi_accuracy.py needs, never opened while labeling
Point ids are shuffled so their order doesn't give the strata away either.

`repeat` (after the first labeling pass) draws a random 10% of every *_sample.csv in the folder
into a *_repeat.csv with empty labels, for the blind consistency check.
Usage: .venv/bin/python scripts/27_draw_reference_sample.py [repeat]"""

import csv
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pyproj
from shapely.geometry import Point, box

change_map = importlib.import_module("19_temporal_change_map")
classify_aoi = importlib.import_module("18_classify_aoi_temporal")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"
OUT_DIR = DATA_DIR / "accuracy_assessment"

SEED = 42
REPEAT_FRACTION = 0.10
ALLOCATION = {change_map.LOSS: 50, change_map.GAIN: 50, change_map.STABLE_FOREST: 100, change_map.STABLE_NONFOREST: 75}
HALF_SIDE_M = np.sqrt(5_000) / 2  # 0.5 ha square, ~70.7 m side
BLIND_COLUMNS = [
    "point_id", "lon", "lat",
    "label_2019", "imagery_source_2019", "imagery_date_2019",
    "label_2023", "imagery_source_2023", "imagery_date_2023",
    "flag_sparse_woody", "uninterpretable_reason", "notes",
]


def allocate(change):
    counts = {code: int((change == code).sum()) for code in ALLOCATION}
    alloc = dict(ALLOCATION)
    for code in (change_map.LOSS, change_map.GAIN):
        if counts[code] == 0:
            # empty change stratum: nothing to sample there, its area comes from omissions found
            # in the stable strata, so its points go to stable forest (design.md)
            alloc[change_map.STABLE_FOREST] += alloc.pop(code)
    return {code: min(n, counts[code]) for code, n in alloc.items()}, counts


def kml(points, meta):
    to_wgs84 = pyproj.Transformer.from_crs(meta["utm_crs"], "EPSG:4326", always_xy=True).transform
    placemarks = []
    for p in points:
        square = box(p["x"] - HALF_SIDE_M, p["y"] - HALF_SIDE_M, p["x"] + HALF_SIDE_M, p["y"] + HALF_SIDE_M)
        ring = " ".join(f"{lon:.7f},{lat:.7f},0" for lon, lat in (to_wgs84(x, y) for x, y in square.exterior.coords))
        placemarks.append(
            f"<Placemark><name>{p['point_id']}</name><MultiGeometry>"
            f"<Point><coordinates>{p['lon']:.7f},{p['lat']:.7f},0</coordinates></Point>"
            f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{ring}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
            f"</MultiGeometry></Placemark>"
        )
    style = "<Style id='s'><LineStyle><color>ff00ffff</color><width>2</width></LineStyle><PolyStyle><fill>0</fill></PolyStyle></Style>"
    return ("<?xml version='1.0' encoding='UTF-8'?><kml xmlns='http://www.opengis.net/kml/2.2'><Document>"
            f"<name>AOI reference sample</name>{style}" + "".join(placemarks).replace("<Placemark>", "<Placemark><styleUrl>#s</styleUrl>")
            + "</Document></kml>")


def main():
    meta = json.loads((DATA_DIR / "aoi_classified_grid_meta.json").read_text())
    change = np.load(DATA_DIR / "change_map_2019_2023_fnf.npy")
    fnf = {y: change_map.to_forest(np.load(DATA_DIR / f"aoi_classified_{y}.npy")) for y in ("2019", "2023")}
    aoi = classify_aoi.load_aoi_geom_wgs84()
    to_wgs84 = pyproj.Transformer.from_crs(meta["utm_crs"], "EPSG:4326", always_xy=True).transform

    alloc, counts = allocate(change)
    rng = np.random.default_rng(SEED)
    points = []
    for code, n in alloc.items():
        rows, cols = np.where(change == code)
        for idx in rng.choice(len(rows), size=n, replace=False):
            r, c = int(rows[idx]), int(cols[idx])
            x = meta["aoi_utm_bounds"][0] + (c + 0.5) * meta["pixel_m"]
            y = meta["aoi_utm_bounds"][3] - (r + 0.5) * meta["pixel_m"]
            lon, lat = to_wgs84(x, y)
            assert aoi.contains(Point(lon, lat)), f"sample point outside AOI polygon: {lon}, {lat}"
            points.append({
                "row": r, "col": c, "x": x, "y": y, "lon": lon, "lat": lat,
                "stratum": change_map.FNF_NAMES[code], "n_h": n, "N_h": counts[code],
                "inclusion_prob": n / counts[code],
                "map_2019": "forest" if fnf["2019"][r, c] == 1 else "nonforest",
                "map_2023": "forest" if fnf["2023"][r, c] == 1 else "nonforest",
            })

    for i, p in enumerate(rng.permutation(len(points))):
        points[p]["point_id"] = f"P{i + 1:03d}"
    points.sort(key=lambda p: p["point_id"])

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "aoi_sample.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=BLIND_COLUMNS)
        w.writeheader()
        for p in points:
            w.writerow({"point_id": p["point_id"], "lon": f"{p['lon']:.7f}", "lat": f"{p['lat']:.7f}"})
    design_cols = ["point_id", "row", "col", "stratum", "n_h", "N_h", "inclusion_prob", "map_2019", "map_2023"]
    with open(OUT_DIR / "aoi_sample_design.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=design_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(points)
    (OUT_DIR / "aoi_sample.kml").write_text(kml(points, meta))

    print(f"stratum pixel counts: { {change_map.FNF_NAMES[k]: v for k, v in counts.items()} }")
    print(f"allocation: { {change_map.FNF_NAMES[k]: v for k, v in alloc.items()} } -> {len(points)} points")
    print(f"saved: {OUT_DIR / 'aoi_sample.csv'}, aoi_sample.kml, aoi_sample_design.csv")


def draw_repeat():
    rng = np.random.default_rng(SEED + 1)
    for path in sorted(OUT_DIR.glob("*_sample.csv")):
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            columns, rows = reader.fieldnames, list(reader)
        picked = rng.choice(len(rows), size=max(1, round(REPEAT_FRACTION * len(rows))), replace=False)
        out = path.with_name(path.name.replace("_sample.csv", "_repeat.csv"))
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            for i in picked:
                w.writerow({"point_id": rows[i]["point_id"], "lon": rows[i]["lon"], "lat": rows[i]["lat"]})
        print(f"saved: {out} ({len(picked)} of {len(rows)} points)")


if __name__ == "__main__":
    draw_repeat() if sys.argv[1:] == ["repeat"] else main()
