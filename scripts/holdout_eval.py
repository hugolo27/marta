"""Shared multi-seed train+eval helper for cross-region held-out checks (phase1-classifier
group 5/5b: scripts 14/16/17). Point/patch extraction stays in each region's own script since
it's GEE-specific per region and deterministic regardless of model seed; this module factors out
the training+scoring loop, which was identical across all three scripts and, until now, only ever
ran once per seed=42 with no variance estimate — unlike scripts/11_compare_classifiers.py's own
5-seed AOI protocol. Mirrors that protocol so a held-out region's "RF beats CNN" (or the reverse)
can be told apart from single-run noise (code review 2026-09-12, prompted by Hugo noticing the
single-run held-out numbers were being read as decisive without ever checking their variance)."""

import importlib
import json

import numpy as np

import classifier_report
import dataset_loader as dl

train_cnn = importlib.import_module("10_train_cnn")
train_rf = importlib.import_module("09_train_random_forest")

SEEDS = [42, 1, 7, 123, 2026]


def macro_f1(results):
    return results["report"]["macro avg"]["f1-score"]


def has_gap(patch):
    """A pixel all-zero in either composite is a gap: a dry+wet patch with only the wet one missing
    would otherwise be scored on fake zero reflectance (same per-composite check as 08)."""
    composites = patch.reshape(*patch.shape[:-1], -1, dl.SEASON_CHANNELS["dry"].stop)
    return bool(np.any(np.all(composites == 0, axis=-1)))


def predict_rf(rows, model):
    center = rows[0]["patch"].shape[0] // 2  # derived from the array, not a hardcoded radius
    X = np.stack([r["patch"][center, center, dl.SEASON_CHANNELS[model.season]] for r in rows])
    return model.predict(X)


def predict_cnn(rows, model, device):
    import torch

    model.eval()
    preds = []
    with torch.no_grad():
        for i in range(0, len(rows), train_cnn.BATCH_SIZE):
            chunk = rows[i:i + train_cnn.BATCH_SIZE]
            batch = np.stack([r["patch"].transpose(2, 0, 1) for r in chunk]).astype(np.float32)
            logits = model(torch.from_numpy(batch).to(device))
            preds.append(logits.argmax(1).cpu().numpy())
    return np.concatenate(preds)


def _summarize(runs):
    f1s = np.array([macro_f1(r) for r in runs])
    accs = np.array([r["report"]["accuracy"] for r in runs])
    ious = np.stack([r["iou_per_class"] for r in runs])
    return {
        "macro_f1_mean": float(f1s.mean()), "macro_f1_std": float(f1s.std(ddof=1)),
        "macro_f1_runs": f1s.round(4).tolist(),
        "accuracy_mean": float(accs.mean()), "accuracy_std": float(accs.std(ddof=1)),
        "iou_per_class_mean": dict(zip(dl.CLASS_NAMES, ious.mean(axis=0).round(4).tolist())),
        "iou_per_class_std": dict(zip(dl.CLASS_NAMES, ious.std(axis=0, ddof=1).round(4).tolist())),
    }


def run_multiseed(rows, y_true, region_name, seeds=SEEDS):
    """Trains RF and CNN once per seed on the fixed AOI training split, evaluates every time
    against the same fixed held-out points (only model-internal randomness varies, matching
    11_compare_classifiers.py's own protocol), and returns per-seed + aggregate metrics for both
    models. Also keeps seed=42's raw predictions for callers that need a representative single
    prediction set (e.g. the WorldCover cross-check, which isn't the thing under variance
    investigation here and doesn't need averaging)."""
    rf_runs, cnn_runs, rf_preds, cnn_preds = [], [], [], []
    for seed in seeds:
        rf = train_rf.train(seed=seed, verbose=False)
        rf_pred = predict_rf(rows, rf)
        rf_results = classifier_report.evaluate_predictions(y_true, rf_pred)
        rf_runs.append(rf_results)
        rf_preds.append(rf_pred)

        model, device, _ = train_cnn.train(seed=seed, verbose=False)
        cnn_pred = predict_cnn(rows, model, device)
        cnn_results = classifier_report.evaluate_predictions(y_true, cnn_pred)
        cnn_runs.append(cnn_results)
        cnn_preds.append(cnn_pred)

        print(f"  [{region_name}] seed {seed}: RF macro-F1={macro_f1(rf_results):.3f}  "
              f"CNN macro-F1={macro_f1(cnn_results):.3f}")

    rf_summary, cnn_summary = _summarize(rf_runs), _summarize(cnn_runs)
    pooled_std = float(np.sqrt((rf_summary["macro_f1_std"] ** 2 + cnn_summary["macro_f1_std"] ** 2) / 2))
    diff = cnn_summary["macro_f1_mean"] - rf_summary["macro_f1_mean"]
    if diff > pooled_std:
        winner = "cnn"
    elif -diff > pooled_std:
        winner = "rf"
    else:
        winner = "inconclusive"

    print(f"  [{region_name}] RF mean={rf_summary['macro_f1_mean']:.3f} "
          f"std={rf_summary['macro_f1_std']:.3f}  CNN mean={cnn_summary['macro_f1_mean']:.3f} "
          f"std={cnn_summary['macro_f1_std']:.3f}  pooled_std={pooled_std:.3f}  winner={winner}")

    return {
        "rf": rf_summary, "cnn": cnn_summary,
        "pooled_std": pooled_std, "cnn_minus_rf": diff, "winner": winner,
        "seeds": seeds,
        "rf_pred_seed42": rf_preds[0], "cnn_pred_seed42": cnn_preds[0],
    }


# U-Net and Random Forest at 30 m (phase1-segmentation D6): each held-out region classified wall to
# wall by tile_inference and scored against MapBiomas on every labeled cell, instead of a point
# sample, with one U-Net checkpoint and one Random Forest per seed of the test.
UNET_CHECKPOINT_DIR = dl.REPO_ROOT / "data" / "study_area" / "unet_checkpoints"
SEGMENTATION_PERIODS = {"2019": ("2019-06-01", "2019-09-30"), "2023": ("2023-06-01", "2023-09-30")}
PRED_TO_WC_CODE = {0: 1, 1: 2, 2: 3}


def unet_checkpoint(seed):
    """Seed 42 is the operational checkpoint saved by the test; the others live next to it."""
    unet = importlib.import_module("36_train_unet")
    return unet.CHECKPOINT_PATH if seed == 42 else UNET_CHECKPOINT_DIR / f"seed_{seed}.pt"


def segmentation_models(seeds=SEEDS):
    """One U-Net checkpoint per seed, and the Random Forest of the selected configuration trained
    on the final training split with each seed, as in 38's test."""
    unet = importlib.import_module("36_train_unet")
    selection = importlib.import_module("38_unet_selection")
    missing = [str(unet_checkpoint(s)) for s in seeds if not unet_checkpoint(s).exists()]
    if missing:
        raise SystemExit(f"missing U-Net checkpoints: {', '.join(missing)}")
    unets = [unet.load_checkpoint(unet_checkpoint(s)) for s in seeds]
    sel = json.loads(selection.RESULTS_PATH.read_text())["selection"]
    data, decisions = selection.splits(), selection.pilot_decisions()
    rfs = [train_rf.train_tiles(data["train"], seed=s, max_samples=decisions["rf_max_samples"], **sel["rf"]) for s in seeds]
    dl._load_full_tile.cache_clear()
    return unets, rfs


def region_counts(name, unets, rfs):
    """dice_counts against MapBiomas per model, U-Nets first, summed over both dates and every
    UTM part of the region, plus the WorldCover agreement counts of each model's seed-42
    predictions: (predicted class, WorldCover class) -> cells."""
    import ee
    from shapely.geometry import box

    import mapbiomas_legend
    import s2_utils
    import tile_inference

    tiles = importlib.import_module("35_assemble_tiles")
    worldcover = importlib.import_module("07_extract_worldcover")
    regions = importlib.import_module("08_assemble_dataset").HELDOUT_REGIONS
    (lon, lat), (dlon, dlat) = regions[name]["center"], regions[name]["half_width_deg"]
    wc_image = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").remap(
        worldcover.FROM_CODES, worldcover.TO_CODES, defaultValue=0).rename("wc_class")
    n = len(unets) + len(rfs)
    counts = np.zeros((n, len(dl.CLASS_NAMES), 3), dtype=np.int64)
    wc_counts = {"unet": np.zeros((3, len(worldcover.CLASS_NAMES)), np.int64), "rf": np.zeros((3, len(worldcover.CLASS_NAMES)), np.int64)}
    for epsg, part in tile_inference.zone_parts(box(lon - dlon, lat - dlat, lon + dlon, lat + dlat)):
        grid = tile_inference.area_grid(epsg, part, unets[0][0].tile_px)
        inside = tile_inference.inside_mask(grid, part)
        wc = tile_inference.label_cells(grid, wc_image)
        for period, (start, end) in SEGMENTATION_PERIODS.items():
            composite, channels = s2_utils.build_season_composite(tile_inference.grid_region(grid), start, end, "drywet", reproject=False)
            probs, gap = tile_inference.classify(tile_inference.gee_fetcher(grid, composite, channels), grid,
                                                 unets=[tile_inference.unet_predictor(m, d) for m, d in unets],
                                                 rfs=[tile_inference.rf_predictor(rf) for rf in rfs])
            label = tile_inference.label_cells(grid, tiles.label_image(period)).astype(np.int64) - 1
            label[gap | ~inside] = dl.IGNORE
            classes = [p.argmax(axis=0) for p in probs]
            for i, pred in enumerate(classes):
                counts[i] += classifier_report.dice_counts(pred, label)
            scored = (label != dl.IGNORE)
            for key, pred in (("unet", classes[0]), ("rf", classes[len(unets)])):
                np.add.at(wc_counts[key], (pred[scored], wc[scored]), 1)
            print(f"  [{name}] EPSG:{epsg} {period}: {int(scored.sum())} labeled cells scored", flush=True)
    return counts, wc_counts


def _seed_summary(counts, seeds):
    runs = [classifier_report.dice_from_counts(c) for c in counts]
    macro = np.array([m for _, m in runs])
    dice = np.stack([d for d, _ in runs])
    return {
        "macro_dice_mean": float(macro.mean()), "macro_dice_std": float(macro.std(ddof=1)),
        "macro_dice_runs": dict(zip(map(str, seeds), macro.round(4).tolist())),
        "dice_mean": dict(zip(dl.CLASS_NAMES, dice.mean(axis=0).round(4).tolist())),
        "dice_std": dict(zip(dl.CLASS_NAMES, dice.std(axis=0, ddof=1).round(4).tolist())),
    }


def run_region(name, out_path, seeds=SEEDS):
    """Both models over one held-out region, 5 seeds each; the same better-than rule as the test
    (difference of means beyond the pooled sample standard deviation)."""
    import mlflow

    import gee_session

    worldcover = importlib.import_module("07_extract_worldcover")
    selection = importlib.import_module("38_unet_selection")
    gee_session.init()
    unets, rfs = segmentation_models(seeds)
    counts, wc_counts = region_counts(name, unets, rfs)
    out = {"unet": _seed_summary(counts[:len(seeds)], seeds), "rf": _seed_summary(counts[len(seeds):], seeds)}
    pooled = float(np.sqrt((out["unet"]["macro_dice_std"] ** 2 + out["rf"]["macro_dice_std"] ** 2) / 2))
    diff = out["unet"]["macro_dice_mean"] - out["rf"]["macro_dice_mean"]
    out.update({"pooled_std": pooled, "unet_minus_rf": diff, "seeds": seeds,
                "winner": "unet" if diff > pooled else "rf" if -diff > pooled else "inconclusive"})
    out["worldcover_cross_check"] = {
        key: {"agreement_rate": {cls: (float(c[i, PRED_TO_WC_CODE[i]] / c[i].sum()) if c[i].sum() else None)
                                 for i, cls in enumerate(dl.CLASS_NAMES)},
              "confusion": {cls: {worldcover.CLASS_NAMES[k]: int(c[i, k]) for k in worldcover.CLASS_NAMES}
                            for i, cls in enumerate(dl.CLASS_NAMES)}}
        for key, c in wc_counts.items()}
    out["worldcover_cross_check"]["note"] = ("seed 42's predictions on every scored cell, WorldCover 2021 by nearest neighbour on the "
                                             "30 m cells; pasto is a weak proxy, WorldCover's grassland does not separate managed pasture")
    test = json.loads(selection.RESULTS_PATH.read_text())["test"]
    out["test_reference"] = {k: float(np.mean([r["macro_dice"] for r in runs])) for k, runs in test.items()}
    out_path.write_text(json.dumps(out, indent=2))
    print(f"  [{name}] U-Net {out['unet']['macro_dice_mean']:.4f} +/- {out['unet']['macro_dice_std']:.4f}  "
          f"RF {out['rf']['macro_dice_mean']:.4f} +/- {out['rf']['macro_dice_std']:.4f}  winner={out['winner']}")
    print(f"saved: {out_path}")

    mlflow.set_experiment("phase1-segmentation-heldout")
    with mlflow.start_run(run_name=f"{name}_heldout"):
        mlflow.log_params({"region": name, "seeds": seeds, "winner": out["winner"]})
        mlflow.log_metrics({"unet_macro_dice_mean": out["unet"]["macro_dice_mean"], "unet_macro_dice_std": out["unet"]["macro_dice_std"],
                            "rf_macro_dice_mean": out["rf"]["macro_dice_mean"], "rf_macro_dice_std": out["rf"]["macro_dice_std"],
                            "pooled_std": pooled, "unet_minus_rf": diff})
        mlflow.log_artifact(str(out_path))
    return out
