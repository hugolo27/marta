"""Cross-region generalization check #2, phase1-classifier task 5.4-5.6 (Bahia Negra, Alto
Paraguay). Mirrors 14_evaluate_filadelfia_holdout.py exactly, over a different held-out
sub-region: remote northern Chaco, forest-dominated, no significant agricultural-colony
influence — the contrast case for whether Filadelfia's CNN-on-bosque failure is landscape-
specific (fragmented/agricultural) or general (any region outside the training footprint).

Usage: .venv/bin/python scripts/16_evaluate_bahia_negra_holdout.py"""

import importlib
import json
from pathlib import Path

import ee
import mlflow
import numpy as np

import dataset_loader as dl
import gee_session
import holdout_eval
import mapbiomas_legend
import s2_utils

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "data" / "study_area" / "bahia_negra_holdout_results.json"
EXPERIMENT_NAME = "phase1-classifier"

PERIODS = {"2019": ("2019-06-01", "2019-09-30"), "2023": ("2023-06-01", "2023-09-30")}
PATCH_RADIUS_PX = 16  # -> 33x33, must match 08_assemble_dataset.py's training patches
N_PER_CLASS = 60  # per period; same order of magnitude as the AOI test split, mirrors 14_...
BATCH_SIZE = 25

HELDOUT_CENTER = (-58.18, -20.23)
HELDOUT_HALF_WIDTH_DEG = (0.20, 0.18)

COMPARISON_RESULTS_PATH = REPO_ROOT / "data" / "study_area" / "comparison_results.json"

# WorldCover legend remap: imported from 07_extract_worldcover.py rather than retyped, same
# reasoning as 14_evaluate_filadelfia_holdout.py.
extract_worldcover = importlib.import_module("07_extract_worldcover")
WC_FROM_CODES = extract_worldcover.FROM_CODES
WC_TO_CODES = extract_worldcover.TO_CODES
WC_CLASS_NAMES = extract_worldcover.CLASS_NAMES
PRED_TO_WC_CODE = {0: 1, 1: 2, 2: 3}  # dl.CLASS_TO_ID index -> WC code


def heldout_geometry():
    lon, lat = HELDOUT_CENTER
    dlon, dlat = HELDOUT_HALF_WIDTH_DEG
    return ee.Geometry.Rectangle([lon - dlon, lat - dlat, lon + dlon, lat + dlat])


def extract_points(heldout):
    """Stratified sample + batched patch extraction, one row per point: 33x33x13 S2 patch,
    MapBiomas class_id (ground truth), and the co-located WorldCover class (independent
    cross-check label). Same all-zero-pixel gap skip as 08_assemble_dataset.py."""
    rows = []
    skipped_gap = 0
    wc_remapped = (
        ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
        .remap(WC_FROM_CODES, WC_TO_CODES, defaultValue=0).rename("wc_class")
    )

    for period, (start, end) in PERIODS.items():
        # clip=True: keeps extraction inside this rectangle only. reproject=False: safe default
        # here too (Bahia Negra doesn't straddle a UTM boundary the way Filadelfia does, but
        # there's no correctness cost to leaving it off, and it keeps this script consistent
        # with 14_... rather than re-deriving per-region reasoning each time).
        s2 = s2_utils.build_s2_composite(heldout, start, end, add_ndvi=True, reproject=False, clip=True)
        channels = s2_utils.S2_BANDS + ["NDVI"]

        mapbiomas = ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET)
        from_codes, to_codes = mapbiomas_legend.remap_expression(f"classification_{period}")
        label = (
            mapbiomas.select(f"classification_{period}")
            .remap(from_codes, to_codes, defaultValue=0)
            .rename("label")
        )
        target_classes = label.eq(1).Or(label.eq(2)).Or(label.eq(3)).selfMask()
        points = label.updateMask(target_classes).stratifiedSample(
            numPoints=N_PER_CLASS, classBand="label", region=heldout, scale=30, seed=42, geometries=True,
        )

        light_info = points.getInfo()["features"]
        points_info = [
            {"lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
             "class_id": int(f["properties"]["label"])}
            for f in light_info
        ]
        points_fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]), {"class_id": p["class_id"]})
            for p in points_info
        ])

        patch_image = (
            s2.select(channels).neighborhoodToArray(ee.Kernel.square(PATCH_RADIUS_PX, "pixels"))
            .addBands(wc_remapped)
        )

        point_list = points_fc.toList(points_fc.size())
        n_points = len(points_info)
        print(f"{period}: {n_points} held-out sample points, extracting in batches of {BATCH_SIZE}")

        extracted = 0
        for start_idx in range(0, n_points, BATCH_SIZE):
            batch = ee.FeatureCollection(point_list.slice(start_idx, start_idx + BATCH_SIZE))
            sampled = patch_image.sampleRegions(collection=batch, scale=10, properties=["class_id"])
            features = sampled.getInfo()["features"]
            extracted += len(features)

            for feat in features:
                props = feat["properties"]
                arrays = [np.array(props[ch]) for ch in channels]
                patch = np.stack(arrays, axis=-1)  # (33, 33, 13)

                if np.any(np.all(patch == 0, axis=-1)):
                    skipped_gap += 1
                    continue

                class_name = mapbiomas_legend.CLASS_NAMES[props["class_id"]]
                rows.append({
                    "patch": patch, "period": period,
                    "label": dl.CLASS_TO_ID[class_name],
                    "wc_class": int(props["wc_class"]),
                })
            print(f"  batch {start_idx // BATCH_SIZE + 1}: {extracted}/{n_points} points extracted")

    print(f"\nTotal held-out points: {len(rows)} ({skipped_gap} skipped for masked/gap pixels)")
    return rows


def worldcover_agreement(pred, rows):
    """Per predicted class, agreement rate against the co-located WorldCover label. 'pasto' is
    a weaker proxy than 'bosque'/'cultivo' — WorldCover has no managed-pasture-vs-natural-
    grassland split, so it under-detects true pasture (see 07_extract_worldcover.py, same
    documented legend limitation)."""
    wc = np.array([r["wc_class"] for r in rows])
    agreement = {}
    confusion = {}
    for cls_idx, cls_name in enumerate(dl.CLASS_NAMES):
        mask = pred == cls_idx
        n = int(mask.sum())
        if n == 0:
            agreement[cls_name] = None
            continue
        matches = int((wc[mask] == PRED_TO_WC_CODE[cls_idx]).sum())
        agreement[cls_name] = matches / n
        confusion[cls_name] = {
            WC_CLASS_NAMES[code]: int((wc[mask] == code).sum()) for code in WC_CLASS_NAMES
        }
    return agreement, confusion


def main():
    gee_session.init()
    rows = extract_points(heldout_geometry())

    y_true = np.array([r["label"] for r in rows])

    print(f"\nRunning {len(holdout_eval.SEEDS)}-seed RF/CNN comparison over Bahia Negra "
          "(same protocol as 11_compare_classifiers.py's AOI comparison, code review 2026-09-12 — "
          "a single seed=42 run has no variance estimate)...")
    multiseed = holdout_eval.run_multiseed(rows, y_true, "Bahia Negra")

    rf_wc_agreement, rf_wc_confusion = worldcover_agreement(multiseed["rf_pred_seed42"], rows)
    cnn_wc_agreement, cnn_wc_confusion = worldcover_agreement(multiseed["cnn_pred_seed42"], rows)
    print("\nRF vs. ESA WorldCover agreement (independent cross-check, not used in training):")
    for cls_name, rate in rf_wc_agreement.items():
        note = " (weak proxy, see docstring)" if cls_name == "pasto" else ""
        print(f"  {cls_name}: {rate:.3f}{note}" if rate is not None else f"  {cls_name}: no predictions")
    print("\nCNN vs. ESA WorldCover agreement (independent cross-check, not used in training):")
    for cls_name, rate in cnn_wc_agreement.items():
        note = " (weak proxy, see docstring)" if cls_name == "pasto" else ""
        print(f"  {cls_name}: {rate:.3f}{note}" if rate is not None else f"  {cls_name}: no predictions")

    comparison = json.loads(COMPARISON_RESULTS_PATH.read_text())
    aoi_reference = {
        "rf_5seed_mean_macro_f1": comparison["rf_mean"],
        "cnn_5seed_mean_macro_f1": comparison["cnn_mean"],
        "note": "5-seed means from comparison_results.json (scripts/11_compare_classifiers.py), "
                "read live rather than hardcoded so this can't go stale when that file is regenerated.",
    }

    results = {
        "n_points": len(rows),
        "aoi_test_split_reference": aoi_reference,
        "bahia_negra_holdout": {
            "seeds": multiseed["seeds"],
            "rf": multiseed["rf"], "cnn": multiseed["cnn"],
            "pooled_std": multiseed["pooled_std"], "cnn_minus_rf": multiseed["cnn_minus_rf"],
            "winner": multiseed["winner"],
            "note": "5-seed mean/std (code review 2026-09-12), same protocol as "
                    "11_compare_classifiers.py's AOI comparison — replaces the earlier single "
                    "seed=42-only numbers, which had no variance estimate.",
        },
        "worldcover_cross_check": {
            "rf": {"agreement_rate": rf_wc_agreement, "confusion": rf_wc_confusion},
            "cnn": {"agreement_rate": cnn_wc_agreement, "confusion": cnn_wc_confusion},
            "note": "computed on seed=42's predictions only, not averaged across seeds — this "
                    "cross-check isn't the thing under variance investigation. pasto is a weaker "
                    "proxy than bosque/cultivo — WorldCover's Grassland class does not "
                    "distinguish managed pasture from natural grassland (see 07_extract_worldcover.py).",
        },
    }
    OUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nresults saved: {OUT_PATH}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="bahia_negra_holdout_5seed"):
        mlflow.log_param("n_points", len(rows))
        mlflow.log_params({"seeds": multiseed["seeds"], "winner": multiseed["winner"]})
        mlflow.log_metrics({
            "rf_macro_f1_mean": multiseed["rf"]["macro_f1_mean"],
            "rf_macro_f1_std": multiseed["rf"]["macro_f1_std"],
            "cnn_macro_f1_mean": multiseed["cnn"]["macro_f1_mean"],
            "cnn_macro_f1_std": multiseed["cnn"]["macro_f1_std"],
            "pooled_std": multiseed["pooled_std"], "cnn_minus_rf": multiseed["cnn_minus_rf"],
        })
        for cls_name, rate in rf_wc_agreement.items():
            if rate is not None:
                mlflow.log_metric(f"rf_wc_agreement_{cls_name}", rate)
        for cls_name, rate in cnn_wc_agreement.items():
            if rate is not None:
                mlflow.log_metric(f"cnn_wc_agreement_{cls_name}", rate)
        mlflow.log_artifact(str(OUT_PATH))


if __name__ == "__main__":
    main()
