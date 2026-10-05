"""Draws the AOI reference sample for phase1-accuracy-assessment (task 3.1), stratified random over
six strata built from the hardened forest/non-forest change map (19_temporal_change_map.py ->
change_map_2019_2023_fnf.npy), in this order of precedence:
  loss, gain             -- the map's change classes
  discarded_change       -- change in the unfiltered map that the confidence/persistence filter
                            removed: where the filter may have erased real clearing
  buffer                 -- 60 m around the final change, plus Hansen 2020-2023 or MapBiomas
                            2019->2023 loss dilated 30 m: omission at edges and where the
                            independent references see loss the map doesn't
  stable_forest, stable_nonforest -- the rest
Redrawn 2026-10-03, before any point was interpreted (the first draw only had the four map
classes, design.md). Strata are no longer the map's classes, so 28_assess_aoi_accuracy.py uses
the Stehman (2014) estimator throughout, with each point's map class stored in the design file.

Writes three files to data/study_area/accuracy_assessment/:
  aoi_sample.csv         -- the blind template the interpreter fills in: point id + coordinates,
                            no stratum, no map label (a stratum IS a map label here)
  aoi_sample.kml         -- same points plus a 0.5 ha square around each, for Google Earth Pro
  aoi_sample_design.csv  -- stratum, inclusion probability and map classes per point; the join
                            file 28_assess_aoi_accuracy.py needs, never opened while labeling
  aoi_sample_strata.json -- stratum and map-class pixel counts, buffer areas (also label-revealing)
Point ids are shuffled so their order doesn't give the strata away either.

`repeat` (after the first labeling pass) draws a random 20% of every *_sample.csv in the folder
into a *_repeat.csv with empty labels, for the blind consistency check.
Usage: .venv/bin/python scripts/27_draw_reference_sample.py [repeat]"""

import csv
import importlib
import json
import sys
from pathlib import Path

import mlflow
import numpy as np
import pyproj
import shapely
from scipy import ndimage
from shapely.geometry import LineString, Point, box

import gee_session
import reference_labels

change_map = importlib.import_module("19_temporal_change_map")
classify_aoi = importlib.import_module("18_classify_aoi_temporal")
score_configs = importlib.import_module("26_score_change_configs")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"
OUT_DIR = DATA_DIR / "accuracy_assessment"
EXPERIMENT_NAME = "phase1-accuracy-assessment"

SEED = 42
REPEAT_FRACTION = 0.20
ALLOCATION = {"loss": 50, "gain": 40, "discarded_change": 40, "buffer": 30, "stable_forest": 120, "stable_nonforest": 60}
BUFFER_PX = 6       # 60 m around the final change
REF_DILATE_PX = 3   # 30 m around Hansen/MapBiomas loss
BUFFER_MAX_SHARE = 0.10
HALF_SIDE_M = np.sqrt(5_000) / 2  # 0.5 ha square, ~70.7 m side
GRID_N = 5          # 5x5 crown-count crosses inside the square, 4% of the square each
CROSS_M = 2.5
DATES = ("2019", "2023")
BLIND_COLUMNS = reference_labels.blind_columns(DATES)


def within(mask, px):
    return ndimage.distance_transform_edt(~mask) <= px


def inside_aoi(shape, meta, aoi):
    """Pixels whose centre falls inside the polygon. A few classified edge pixels have their centre
    just outside it; they are left out of the sampling frame rather than drawn and then dropped."""
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", meta["utm_crs"], always_xy=True).transform
    rows, cols = np.indices(shape)
    xs = meta["aoi_utm_bounds"][0] + (cols + 0.5) * meta["pixel_m"]
    ys = meta["aoi_utm_bounds"][3] - (rows + 0.5) * meta["pixel_m"]
    return shapely.contains_xy(shapely.ops.transform(to_utm, aoi), xs, ys)


def build_strata(final, raw, ref_loss, frame):
    valid = (final != change_map.UNCLASSIFIED) & frame
    changed = np.isin(final, (change_map.LOSS, change_map.GAIN))
    strata = np.full(final.shape, "", dtype=object)
    order = [
        ("loss", final == change_map.LOSS),
        ("gain", final == change_map.GAIN),
        ("discarded_change", np.isin(raw, (change_map.LOSS, change_map.GAIN))),
        ("buffer", within(changed, BUFFER_PX) | within(ref_loss, REF_DILATE_PX)),
        ("stable_forest", final == change_map.STABLE_FOREST),
        ("stable_nonforest", final == change_map.STABLE_NONFOREST),
    ]
    for name, mask in order:
        strata[valid & mask & (strata == "")] = name
    return strata


def allocate(strata):
    counts = {name: int((strata == name).sum()) for name in ALLOCATION}
    alloc = dict(ALLOCATION)
    for name in ("loss", "gain", "discarded_change", "buffer"):
        if counts[name] == 0:
            # empty stratum: nothing to sample there, its points go to stable forest, where
            # omission dominates the loss-area interval (design.md)
            alloc["stable_forest"] += alloc.pop(name)
    return {name: min(n, counts[name]) for name, n in alloc.items()}, counts


def kml(points, meta):
    to_wgs84 = pyproj.Transformer.from_crs(meta["utm_crs"], "EPSG:4326", always_xy=True).transform
    coords = lambda geom: " ".join(f"{lon:.7f},{lat:.7f},0" for lon, lat in (to_wgs84(x, y) for x, y in geom.coords))
    cell = 2 * HALF_SIDE_M / GRID_N
    placemarks = []
    for p in points:
        square = box(p["x"] - HALF_SIDE_M, p["y"] - HALF_SIDE_M, p["x"] + HALF_SIDE_M, p["y"] + HALF_SIDE_M)
        crosses = []
        for i in range(GRID_N):
            for j in range(GRID_N):
                cx, cy = p["x"] - HALF_SIDE_M + (i + 0.5) * cell, p["y"] - HALF_SIDE_M + (j + 0.5) * cell
                for line in (LineString([(cx - CROSS_M, cy), (cx + CROSS_M, cy)]), LineString([(cx, cy - CROSS_M), (cx, cy + CROSS_M)])):
                    crosses.append(f"<LineString><coordinates>{coords(line)}</coordinates></LineString>")
        placemarks.append(
            f"<Placemark><name>{p['point_id']}</name><MultiGeometry>"
            f"<Point><coordinates>{p['lon']:.7f},{p['lat']:.7f},0</coordinates></Point>"
            f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coords(square.exterior)}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
            + "".join(crosses) + "</MultiGeometry></Placemark>"
        )
    style = "<Style id='s'><LineStyle><color>ff00ffff</color><width>2</width></LineStyle><PolyStyle><fill>0</fill></PolyStyle></Style>"
    return ("<?xml version='1.0' encoding='UTF-8'?><kml xmlns='http://www.opengis.net/kml/2.2'><Document>"
            f"<name>AOI reference sample</name>{style}" + "".join(placemarks).replace("<Placemark>", "<Placemark><styleUrl>#s</styleUrl>")
            + "</Document></kml>")


def main():
    meta = json.loads((DATA_DIR / "aoi_classified_grid_meta.json").read_text())
    change = np.load(DATA_DIR / "change_map_2019_2023_fnf.npy")
    rasters = {y: np.load(DATA_DIR / f"aoi_classified_{y}.npy") for y in DATES}
    raw = change_map.build_fnf_change(rasters["2019"], rasters["2023"])
    fnf = {y: change_map.to_forest(r) for y, r in rasters.items()}
    aoi = classify_aoi.load_aoi_geom_wgs84()
    to_wgs84 = pyproj.Transformer.from_crs(meta["utm_crs"], "EPSG:4326", always_xy=True).transform

    gee_session.init()
    refs = score_configs.pull_references(classify_aoi.AOI_PATH, meta)
    assert refs["hansen_loss"].shape == change.shape, "reference grid differs from the change map"
    ref_loss = (refs["hansen_loss"] == 1) | ((refs["mb_forest_2019"] == 1) & (refs["mb_forest_2023"] == 0))

    frame = inside_aoi(change.shape, meta, aoi)
    strata = build_strata(change, raw, ref_loss, frame)
    valid_px = int(((change != change_map.UNCLASSIFIED) & frame).sum())
    changed = np.isin(change, (change_map.LOSS, change_map.GAIN))
    buffer_90m_px = int(((within(changed, 9) | within(ref_loss, REF_DILATE_PX)) & (strata != "loss") & (strata != "gain")
                         & (strata != "discarded_change") & (strata != "")).sum())
    alloc, counts = allocate(strata)
    assert counts["buffer"] <= BUFFER_MAX_SHARE * valid_px, f"60 m buffer covers {counts['buffer'] / valid_px:.1%} of the AOI"

    rng = np.random.default_rng(SEED)
    points = []
    for name, n in alloc.items():
        rows, cols = np.where(strata == name)
        for idx in rng.choice(len(rows), size=n, replace=False):
            r, c = int(rows[idx]), int(cols[idx])
            x = meta["aoi_utm_bounds"][0] + (c + 0.5) * meta["pixel_m"]
            y = meta["aoi_utm_bounds"][3] - (r + 0.5) * meta["pixel_m"]
            lon, lat = to_wgs84(x, y)
            assert aoi.contains(Point(lon, lat)), f"sample point outside AOI polygon: {lon}, {lat}"
            points.append({
                "row": r, "col": c, "x": x, "y": y, "lon": lon, "lat": lat,
                "stratum": name, "n_h": n, "N_h": counts[name], "inclusion_prob": n / counts[name],
                "map_2019": "forest" if fnf["2019"][r, c] == 1 else "nonforest",
                "map_2023": "forest" if fnf["2023"][r, c] == 1 else "nonforest",
                "map_change": change_map.FNF_NAMES[int(change[r, c])],
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
    design_cols = ["point_id", "row", "col", "stratum", "n_h", "N_h", "inclusion_prob", "map_2019", "map_2023", "map_change"]
    with open(OUT_DIR / "aoi_sample_design.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=design_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(points)
    (OUT_DIR / "aoi_sample.kml").write_text(kml(points, meta))
    (OUT_DIR / "aoi_sample_strata.json").write_text(json.dumps({
        "seed": SEED, "allocation": alloc, "stratum_px": counts, "valid_px": valid_px,
        "map_change_px": {n: int(((change == code) & frame).sum()) for code, n in change_map.FNF_NAMES.items()},
        "excluded_edge_px": int(((change != change_map.UNCLASSIFIED) & ~frame).sum()),
        "buffer_60m_share": counts["buffer"] / valid_px, "buffer_90m_share_for_reference": buffer_90m_px / valid_px,
        "reference_loss_px": int(ref_loss.sum()),
    }, indent=2))

    print(f"stratum pixel counts: {counts}")
    print(f"buffer share of AOI: 60 m {counts['buffer'] / valid_px:.2%} (90 m would be {buffer_90m_px / valid_px:.2%}); "
          f"reference loss px: {int(ref_loss.sum())}")
    print(f"allocation: {alloc} -> {len(points)} points")
    print(f"saved: {OUT_DIR / 'aoi_sample.csv'}, aoi_sample.kml, aoi_sample_design.csv, aoi_sample_strata.json")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="draw_reference_sample_aoi"):
        mlflow.log_params({"seed": SEED, "n_points": len(points), "buffer_px": BUFFER_PX, "ref_dilate_px": REF_DILATE_PX,
                           **{f"n_{k}": v for k, v in alloc.items()}})
        mlflow.log_metric("buffer_60m_share", counts["buffer"] / valid_px)
        # blind template + strata only; the design file (map labels) stays out of the run
        mlflow.log_artifact(str(OUT_DIR / "aoi_sample.csv"))
        mlflow.log_artifact(str(OUT_DIR / "aoi_sample_strata.json"))


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
