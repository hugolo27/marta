"""Shared multi-seed train+eval helper for cross-region held-out checks (phase1-classifier
group 5/5b: scripts 14/16/17). Point/patch extraction stays in each region's own script since
it's GEE-specific per region and deterministic regardless of model seed; this module factors out
the training+scoring loop, which was identical across all three scripts and, until now, only ever
ran once per seed=42 with no variance estimate — unlike scripts/11_compare_classifiers.py's own
5-seed AOI protocol. Mirrors that protocol so a held-out region's "RF beats CNN" (or the reverse)
can be told apart from single-run noise (code review 2026-09-12, prompted by Hugo noticing the
single-run held-out numbers were being read as decisive without ever checking their variance)."""

import importlib

import numpy as np

import classifier_report
import dataset_loader as dl

train_cnn = importlib.import_module("10_train_cnn")
train_rf = importlib.import_module("09_train_random_forest")

SEEDS = [42, 1, 7, 123, 2026]


def macro_f1(results):
    return results["report"]["macro avg"]["f1-score"]


def predict_rf(rows, model):
    center = rows[0]["patch"].shape[0] // 2  # derived from the array, not a hardcoded radius
    X = np.stack([r["patch"][center, center, :] for r in rows])
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
        "macro_f1_mean": float(f1s.mean()), "macro_f1_std": float(f1s.std()),
        "macro_f1_runs": f1s.round(4).tolist(),
        "accuracy_mean": float(accs.mean()), "accuracy_std": float(accs.std()),
        "iou_per_class_mean": dict(zip(dl.CLASS_NAMES, ious.mean(axis=0).round(4).tolist())),
        "iou_per_class_std": dict(zip(dl.CLASS_NAMES, ious.std(axis=0).round(4).tolist())),
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
