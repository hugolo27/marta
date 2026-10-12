"""Draws the held-out reference samples for phase1-accuracy-assessment (task 6.1): per region
(Filadelfia, Bahía Negra, Pozo Colorado), 50 points in ESA WorldCover 2021 tree cover and 50 in
everything else, fixed seed. WorldCover is independent of both MapBiomas (our training labels) and
our own map; the points are later classified by patch (30_assess_heldout_accuracy.py) and scored
with the Stehman (2014) estimator, since these strata aren't our map classes.

Same blind/design file split as 27_draw_reference_sample.py: heldout_<region>_sample.csv and .kml
carry no stratum, heldout_<region>_sample_design.csv does.
Usage: .venv/bin/python scripts/29_draw_heldout_samples.py"""

import csv
import importlib
from pathlib import Path

import ee
import mlflow
import numpy as np
import pyproj

import gee_session
import reference_labels

assemble = importlib.import_module("08_assemble_dataset")
draw_aoi = importlib.import_module("27_draw_reference_sample")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area" / "accuracy_assessment"
N_PER_STRATUM = 50
WC_TREE_COVER = 10
STRATA = {1: "wc_tree", 0: "wc_other"}
SEED = 42
EXPERIMENT_NAME = "phase1-accuracy-assessment"


def utm_for(lon):
    return f"EPSG:{32700 + int((lon + 180) // 6) + 1}"


def draw(name):
    region = assemble.heldout_rectangle(name)
    tree = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(WC_TREE_COVER).rename("stratum").clip(region)
    counts = tree.reduceRegion(ee.Reducer.frequencyHistogram(), region, scale=10, maxPixels=1e10).getInfo()["stratum"]
    n_h = {int(float(k)): int(v) for k, v in counts.items()}
    fc = tree.stratifiedSample(numPoints=N_PER_STRATUM, classBand="stratum", region=region, scale=10, seed=SEED, geometries=True)
    feats = fc.getInfo()["features"]

    rng = np.random.default_rng(SEED)
    points = []
    for f in feats:
        lon, lat = f["geometry"]["coordinates"]
        s = int(f["properties"]["stratum"])
        points.append({"lon": lon, "lat": lat, "stratum": STRATA[s], "n_h": N_PER_STRATUM, "N_h": n_h[s],
                       "inclusion_prob": N_PER_STRATUM / n_h[s]})
    prefix = name[:3].upper()
    for i, p in enumerate(rng.permutation(len(points))):
        points[p]["point_id"] = f"{prefix}{i + 1:03d}"
    points.sort(key=lambda p: p["point_id"])

    crs = utm_for(points[0]["lon"])
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    for p in points:
        p["x"], p["y"] = to_utm(p["lon"], p["lat"])

    with open(OUT_DIR / f"heldout_{name}_sample.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=reference_labels.blind_columns(("2023",)))
        w.writeheader()
        for p in points:
            w.writerow({"point_id": p["point_id"], "lon": f"{p['lon']:.7f}", "lat": f"{p['lat']:.7f}"})
    with open(OUT_DIR / f"heldout_{name}_sample_design.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["point_id", "lon", "lat", "stratum", "n_h", "N_h", "inclusion_prob"], extrasaction="ignore")
        w.writeheader()
        w.writerows(points)
    (OUT_DIR / f"heldout_{name}_sample.kml").write_text(draw_aoi.kml(points, {"utm_crs": crs}))

    (lon0, lat0), (dlon, dlat) = assemble.HELDOUT_REGIONS[name]["center"], assemble.HELDOUT_REGIONS[name]["half_width_deg"]
    inside = all(abs(p["lon"] - lon0) <= dlon and abs(p["lat"] - lat0) <= dlat for p in points)
    per_stratum = {s: sum(p["stratum"] == s for p in points) for s in STRATA.values()}
    print(f"{name}: {len(points)} points {per_stratum}, stratum sizes {n_h}, all inside region: {inside}")


def main():
    gee_session.init()
    OUT_DIR.mkdir(exist_ok=True)
    for name in assemble.HELDOUT_REGIONS:
        draw(name)
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="draw_reference_sample_heldout"):
        mlflow.log_params({"seed": SEED, "n_per_stratum": N_PER_STRATUM, "regions": ",".join(assemble.HELDOUT_REGIONS)})
        for name in assemble.HELDOUT_REGIONS:
            mlflow.log_artifact(str(OUT_DIR / f"heldout_{name}_sample.csv"))


if __name__ == "__main__":
    main()
