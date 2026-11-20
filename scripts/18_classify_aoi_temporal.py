"""Wall-to-wall per-date classification of the case-study AOI or the change-development area with
the operational U-Net (phase1-segmentation D6). One persisted checkpoint (36_train_unet.load_checkpoint,
seed 42 of the test) for every year, so all dates share the same decision boundary: retraining per
date would mix training-run variance into what should be a land-cover signal.

The area is classified by overlapping windows on its own UTM 10 m grid and the result is a 30 m
raster, the resolution the U-Net is trained and scored at (tile_inference.py). Cells with a gap in
either composite or outside the area are UNCLASSIFIED. Saves the classes and the averaged softmax
probabilities per year, which the confidence and persistence filters of the change map read, and
the grid, with the checkpoint's sha256 so a map can be traced to the model that made it.

The dry composite is June-September and the wet one January-April of the same year, as in training.

Usage: .venv/bin/python scripts/18_classify_aoi_temporal.py [--area aoi|dev] [--years 2019 2023]"""

import argparse
import hashlib
import importlib
import json
from pathlib import Path

import mlflow
import numpy as np
from shapely.geometry import shape

import gee_session
import s2_utils
import tile_inference

unet = importlib.import_module("36_train_unet")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area"
AOI_PATH = REPO_ROOT / "data" / "study_area" / "aoi.geojson"
AREAS = {
    "aoi": {"path": AOI_PATH, "prefix": "aoi"},
    "dev": {"path": REPO_ROOT / "data" / "study_area" / "change_hardening" / "dev_area.geojson", "prefix": "dev"},
}

PERIODS = {str(y): (f"{y}-06-01", f"{y}-09-30") for y in range(2019, 2024)}
DEFAULT_YEARS = ["2019", "2023"]
PIXEL_M = 30
UNCLASSIFIED = tile_inference.UNCLASSIFIED
CLASS_NAMES = ["bosque", "pasto", "cultivo"]
EXPERIMENT_NAME = "phase1-temporal-comparison"


def load_aoi_geom_wgs84(path=AOI_PATH):
    gj = json.loads(path.read_text())
    return shape(gj["features"][0]["geometry"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", choices=list(AREAS), default="aoi")
    parser.add_argument("--years", nargs="+", choices=list(PERIODS), default=DEFAULT_YEARS)
    args = parser.parse_args()
    area = AREAS[args.area]

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=f"classify_{area['prefix']}_{'_'.join(args.years)}"):
        gee_session.init()
        geom = load_aoi_geom_wgs84(area["path"])
        (epsg, part), = tile_inference.zone_parts(geom)
        model, device = unet.load_checkpoint()
        checkpoint_sha256 = hashlib.sha256(unet.CHECKPOINT_PATH.read_bytes()).hexdigest()
        grid = tile_inference.area_grid(epsg, part, model.tile_px)
        inside = tile_inference.inside_mask(grid, part)
        print(f"{args.area}: {grid['height']}x{grid['width']} px in EPSG:{epsg}, {int(inside.sum())} cells of 30 m inside; "
              f"checkpoint {unet.CHECKPOINT_PATH.name} {checkpoint_sha256[:12]}")
        mlflow.log_params({"area": args.area, "years": ",".join(args.years), "epsg": epsg, "tile_px": model.tile_px,
                           "checkpoint_sha256": checkpoint_sha256})

        for period in args.years:
            start, end = PERIODS[period]
            composite, channels = s2_utils.build_season_composite(tile_inference.grid_region(grid), start, end, "drywet", reproject=False)
            (probs,), gap = tile_inference.classify(tile_inference.gee_fetcher(grid, composite, channels), grid,
                                                    unets=[tile_inference.unet_predictor(model, device)])
            classes = tile_inference.to_classes(probs, gap, inside)
            share = float((classes[inside] == UNCLASSIFIED).mean())
            print(f"{period}: {share:.1%} of the area unclassified (gaps)")
            mlflow.log_metric(f"unclassified_fraction_{period}", share)
            proba = probs.transpose(1, 2, 0).astype(np.float16)
            proba[classes == UNCLASSIFIED] = np.nan
            for name, arr in [(f"{area['prefix']}_classified_{period}.npy", classes), (f"{area['prefix']}_proba_{period}.npy", proba)]:
                np.save(OUT_DIR / name, arr)
                print(f"saved: {OUT_DIR / name}")

        n_rows, n_cols = grid["height"] // 3, grid["width"] // 3
        meta = {
            "n_rows": n_rows, "n_cols": n_cols, "pixel_m": PIXEL_M, "utm_crs": f"EPSG:{epsg}",
            "aoi_utm_bounds": [grid["x0"], grid["y0"] - n_rows * PIXEL_M, grid["x0"] + n_cols * PIXEL_M, grid["y0"]],
            "tile_px": model.tile_px, "checkpoint_sha256": checkpoint_sha256,
            "class_names": CLASS_NAMES, "unclassified_value": UNCLASSIFIED,
        }
        meta_path = OUT_DIR / f"{area['prefix']}_classified_grid_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"saved: {meta_path}")
        mlflow.log_artifact(str(meta_path))


if __name__ == "__main__":
    main()
