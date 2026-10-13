"""Hyperparameter selection on the validation split, phase1-hyperparameter-selection (tasks 1.1,
2.2, 3.1). Replaces the earlier one-at-a-time sweep, which scored on the test split
(data/study_area/hyperparameter_sweep_test_split.json, kept as a record, not used for any decision).

Two steps, run in this order:
  preregister -- hashes the README's pre-registered part (everything above "## Results") and logs
                 it to MLflow before any configuration has been scored
  score       -- refuses to run if that part changed since, then scores both grids on val and
                 applies the selection rule (design D2)

The test split is never touched here; 11_compare_classifiers.py reports it once with the selected
configurations. Progress is saved after every configuration, so an interrupted run resumes.
Usage: .venv/bin/python scripts/24_hyperparameter_selection.py preregister|score"""

import hashlib
import importlib
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import numpy as np

train_cnn = importlib.import_module("10_train_cnn")
train_rf = importlib.import_module("09_train_random_forest")

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area" / "hyperparameter_selection"
README = OUT_DIR / "README.md"
PREREG_PATH = OUT_DIR / "preregistration.json"
RESULTS_PATH = OUT_DIR / "results.json"
EXPERIMENT_NAME = "phase1-hyperparameter-selection"

SEEDS = [42, 1, 7, 123, 2026]
RF_GRID = {"n_estimators": [300, 400, 500], "max_depth": [None, 10, 20], "max_features": ["sqrt", 0.5]}
CNN_GRID = {"lr": [0.0001, 0.0003, 0.001, 0.01], "dropout": [0.3, 0.4, 0.5], "batch_size": [16, 32, 64]}
RF_CURRENT = {"n_estimators": 400, "max_depth": None, "max_features": "sqrt"}
CNN_CURRENT = {"lr": 0.001, "dropout": 0.4, "batch_size": 32}  # before selection; 10_train_cnn.py now holds the selected values
RERUN_MAX_EPOCHS = 300


def preregistered_text():
    text = README.read_text()
    return text[:text.index("## Results")]


def preregister():
    digest = hashlib.sha256(preregistered_text().encode()).hexdigest()
    record = {"sha256": digest, "utc": datetime.now(timezone.utc).isoformat()}
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="preregistration"):
        mlflow.log_param("readme_sha256", digest)
        mlflow.log_artifact(str(README))
    PREREG_PATH.write_text(json.dumps(record, indent=2))
    print(f"pre-registered {README} sha256={digest}")


def grid(spec):
    return [dict(zip(spec, values)) for values in itertools.product(*spec.values())]


def macro_f1(results):
    return results["report"]["macro avg"]["f1-score"]


def summarize(cfg, scores, extra=None):
    arr = np.array(scores)
    return {"config": cfg, "scores": scores, "mean": float(arr.mean()), "std": float(arr.std(ddof=1)), **(extra or {})}


def score_rf(cfg, seeds):
    scores = []
    for seed in seeds:
        rf = train_rf.train(seed=seed, verbose=False, **cfg)
        scores.append(macro_f1(train_rf.evaluate(rf, split="val")))
        with mlflow.start_run(run_name=f"rf_{cfg}_seed{seed}", nested=True):
            mlflow.log_params({"model": "rf", "seed": seed, **{k: str(v) for k, v in cfg.items()}})
            mlflow.log_metric("val_macro_f1", scores[-1])
    return summarize(cfg, scores)


def score_cnn(cfg, seeds, max_epochs=train_cnn.MAX_EPOCHS):
    scores, best, stop = [], [], []
    for seed in seeds:
        model, device, history = train_cnn.train(seed=seed, verbose=False, max_epochs=max_epochs, **cfg)
        scores.append(macro_f1(train_cnn.evaluate(model, device, split="val")))
        best_epoch, stop_epoch = train_cnn.epochs(history)
        best.append(best_epoch)
        stop.append(stop_epoch)
        with mlflow.start_run(run_name=f"cnn_{cfg}_seed{seed}", nested=True):
            mlflow.log_params({"model": "cnn", "seed": seed, "max_epochs": max_epochs, **cfg})
            mlflow.log_metrics({"val_macro_f1": scores[-1], "best_epoch": best_epoch, "stop_epoch": stop_epoch})
    truncated = max(stop) >= max_epochs
    row = summarize(cfg, scores, {"max_epochs": max_epochs, "best_epoch": best, "stop_epoch": stop, "truncated": truncated})
    if truncated and max_epochs < RERUN_MAX_EPOCHS:
        print(f"  {cfg} truncated at {max_epochs} epochs, re-running with {RERUN_MAX_EPOCHS}")
        return score_cnn(cfg, seeds, RERUN_MAX_EPOCHS)
    return row


def distance(cfg, current):
    return sum(cfg[k] != current[k] for k in current)


def select(rows, current, cost_key):
    top = max(r["mean"] for r in rows)
    best = min([r for r in rows if r["mean"] == top], key=lambda r: (distance(r["config"], current), cost_key(r)))
    cur = next(r for r in rows if r["config"] == current)
    pooled = float(np.sqrt((best["std"] ** 2 + cur["std"] ** 2) / 2))
    changed = best["mean"] - cur["mean"] > pooled
    return {
        "best": best["config"], "current": current, "best_minus_current": best["mean"] - cur["mean"],
        "pooled_std": pooled, "changed": changed, "selected": best["config"] if changed else current,
    }


def run_grid(name, configs, scorer, done):
    rows = done.setdefault(name, [])
    finished = [r["config"] for r in rows]
    for cfg in configs:
        if cfg in finished:
            continue
        rows.append(scorer(cfg, SEEDS))
        r = rows[-1]
        print(f"  {name} {cfg}: val macro_f1={r['mean']:.3f} +/- {r['std']:.3f}")
        RESULTS_PATH.write_text(json.dumps(done, indent=2))
    return rows


def score():
    prereg = json.loads(PREREG_PATH.read_text())
    digest = hashlib.sha256(preregistered_text().encode()).hexdigest()
    if digest != prereg["sha256"]:
        sys.exit("pre-registered part of README changed since preregistration -- refusing to score")

    done = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else {"preregistration": prereg}
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="hyperparameter_selection"):
        mlflow.log_param("readme_sha256", digest)
        print("Random Forest grid (val)")
        rf_rows = run_grid("rf", grid(RF_GRID), score_rf, done)
        print("\nCNN grid (val)")
        cnn_rows = run_grid("cnn", grid(CNN_GRID), score_cnn, done)

        done["selection"] = {
            "rf": select(rf_rows, RF_CURRENT, lambda r: r["config"]["n_estimators"]),
            "cnn": select(cnn_rows, CNN_CURRENT, lambda r: np.mean(r["stop_epoch"])),
        }
        RESULTS_PATH.write_text(json.dumps(done, indent=2))
        mlflow.log_param("rf_selected", json.dumps(done["selection"]["rf"]["selected"]))
        mlflow.log_param("cnn_selected", json.dumps(done["selection"]["cnn"]["selected"]))
        mlflow.log_artifact(str(RESULTS_PATH))

    for name, sel in done["selection"].items():
        print(f"\n{name}: best={sel['best']} best-current={sel['best_minus_current']:+.4f} "
              f"pooled_std={sel['pooled_std']:.4f} -> selected={sel['selected']} (changed={sel['changed']})")
    print(f"saved: {RESULTS_PATH}")


if __name__ == "__main__":
    {"preregister": preregister, "score": score}[sys.argv[1]]()
