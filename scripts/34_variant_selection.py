"""Variant selection on the rebuilt dataset, phase1-dataset-v2 (tasks 1.2, 3.1-3.3). Per variant,
hyperparameters on val (design D4: CNN grid with the edge rule, RF grid as in
24_hyperparameter_selection.py), then the pre-registered variant rule, then every selected variant
on test once, for the record.

CNN variants: A 3x3 dry (default), B 3x3 dry+wet. The 33x33 variants C and D were dropped by
Amendment 2 of the README; the partial C rows in results.json are kept as exploratory.
RF variants: dry (default), dry+wet.

Two steps, run in this order:
  preregister -- hashes the README's pre-registered part (everything above "## Results") and logs
                 it to MLflow before any variant is scored
  score       -- refuses to run if that part changed since; resumable from results.json

Usage: .venv/bin/python scripts/34_variant_selection.py preregister|score"""

import hashlib
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import numpy as np

train_cnn = importlib.import_module("10_train_cnn")
train_rf = importlib.import_module("09_train_random_forest")
selection = importlib.import_module("24_hyperparameter_selection")

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area" / "variant_selection"
README = OUT_DIR / "README.md"
PREREG_PATH = OUT_DIR / "preregistration.json"
RESULTS_PATH = OUT_DIR / "results.json"
EXPERIMENT_NAME = "phase1-variant-selection"

CNN_GRID = {"lr": [0.0001, 0.0003, 0.001], "dropout": [0.3, 0.4, 0.5, 0.6], "batch_size": [8, 16, 32, 64]}
EDGE_STEP = {"dropout": {0.6: 0.7}, "batch_size": {8: 4, 64: 128}}
CNN_VARIANTS = {"A": (3, "dry"), "B": (3, "drywet")}
RF_VARIANTS = ["dry", "drywet"]
BUILD_STATS = OUT_DIR.parent / "dataset" / "build_stats.json"
MAX_WET_GAP_SHARE = 0.10


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


def score_cnn(cfg, patch_px, season, max_epochs=train_cnn.MAX_EPOCHS):
    scores, best, stop = [], [], []
    for seed in selection.SEEDS:
        model, device, history = train_cnn.train(seed=seed, verbose=False, max_epochs=max_epochs,
                                                 patch_px=patch_px, season=season, **cfg)
        scores.append(selection.macro_f1(train_cnn.evaluate(model, device, split="val")))
        best_epoch, stop_epoch = train_cnn.epochs(history)
        best.append(best_epoch)
        stop.append(stop_epoch)
        with mlflow.start_run(run_name=f"cnn{patch_px}_{season}_{cfg}_seed{seed}", nested=True):
            mlflow.log_params({"model": "cnn", "patch_px": patch_px, "season": season, "seed": seed,
                               "max_epochs": max_epochs, **cfg})
            mlflow.log_metrics({"val_macro_f1": scores[-1], "best_epoch": best_epoch, "stop_epoch": stop_epoch})
    truncated = max(stop) >= max_epochs
    row = selection.summarize(cfg, scores, {"max_epochs": max_epochs, "best_epoch": best, "stop_epoch": stop,
                                            "truncated": truncated})
    if truncated and max_epochs < selection.RERUN_MAX_EPOCHS:
        print(f"  {cfg} truncated at {max_epochs} epochs, re-running with {selection.RERUN_MAX_EPOCHS}")
        return score_cnn(cfg, patch_px, season, selection.RERUN_MAX_EPOCHS)
    return row


def score_rf(cfg, season):
    scores = []
    for seed in selection.SEEDS:
        rf = train_rf.train(seed=seed, verbose=False, season=season, **cfg)
        scores.append(selection.macro_f1(train_rf.evaluate(rf, split="val")))
        with mlflow.start_run(run_name=f"rf_{season}_{cfg}_seed{seed}", nested=True):
            mlflow.log_params({"model": "rf", "season": season, "seed": seed, **{k: str(v) for k, v in cfg.items()}})
            mlflow.log_metric("val_macro_f1", scores[-1])
    return selection.summarize(cfg, scores)


def run_configs(rows, configs, scorer, done, label):
    finished = [r["config"] for r in rows]
    for cfg in configs:
        if cfg in finished:
            continue
        rows.append(scorer(cfg))
        print(f"  {label} {cfg}: val macro_f1={rows[-1]['mean']:.3f} +/- {rows[-1]['std']:.3f}", flush=True)
        RESULTS_PATH.write_text(json.dumps(done, indent=2))


def best_row(rows, cost):
    top = max(r["mean"] for r in rows)
    return min([r for r in rows if r["mean"] == top], key=cost)


def cnn_cost(row):
    return (np.mean(row["stop_epoch"]), -row["config"]["batch_size"])


def edge_extensions(cfg):
    """One extra step on any axis whose selected value sits on the grid edge (design D4)."""
    out = []
    for axis, steps in EDGE_STEP.items():
        if cfg[axis] in steps:
            out.append({**cfg, axis: steps[cfg[axis]]})
    return out


def pooled(a, b):
    return float(np.sqrt((a["std"] ** 2 + b["std"] ** 2) / 2))


def decide(selected, default_key):
    default = selected[default_key]
    candidate_key = max(selected, key=lambda k: selected[k]["mean"])
    candidate = selected[candidate_key]
    margin = pooled(default, candidate)
    replaced = candidate_key != default_key and candidate["mean"] - default["mean"] > margin
    return {"default": default_key, "candidate": candidate_key,
            "candidate_minus_default": candidate["mean"] - default["mean"], "pooled_std": margin,
            "operational": candidate_key if replaced else default_key}


def test_cnn(cfg, patch_px, season):
    scores = []
    for seed in selection.SEEDS:
        model, device, _ = train_cnn.train(seed=seed, verbose=False, patch_px=patch_px, season=season, **cfg)
        scores.append(selection.macro_f1(train_cnn.evaluate(model, device, split="test")))
    return selection.summarize(cfg, scores)


def test_rf(cfg, season):
    scores = [selection.macro_f1(train_rf.evaluate(train_rf.train(seed=s, verbose=False, season=season, **cfg)))
              for s in selection.SEEDS]
    return selection.summarize(cfg, scores)


def score():
    prereg = json.loads(PREREG_PATH.read_text())
    digest = hashlib.sha256(preregistered_text().encode()).hexdigest()
    if digest != prereg["sha256"]:
        sys.exit("pre-registered part of README changed since preregistration -- refusing to score")

    done = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else {"preregistration": prereg}
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="variant_selection"):
        mlflow.log_param("readme_sha256", digest)

        wet_gap = json.loads(BUILD_STATS.read_text())["wet_gap_share"]
        seasons = RF_VARIANTS if wet_gap <= MAX_WET_GAP_SHARE else ["dry"]
        variants = {k: v for k, v in CNN_VARIANTS.items() if v[1] in seasons}
        done["wet_gap_share"] = wet_gap
        if len(seasons) == 1:
            print(f"wet-season gaps dropped {wet_gap:.1%} of the examples (> {MAX_WET_GAP_SHARE:.0%}): dry+wet variants not scored")

        rf_selected = {}
        for season in seasons:
            rows = done.setdefault(f"rf_{season}", [])
            run_configs(rows, selection.grid(selection.RF_GRID), lambda cfg: score_rf(cfg, season), done, f"rf {season}")
            rf_selected[season] = best_row(rows, lambda r: r["config"]["n_estimators"])

        cnn_selected = {}
        for key in variants:
            patch_px, season = variants[key]
            rows = done.setdefault(f"cnn_{key}", [])
            scorer = lambda cfg: score_cnn(cfg, patch_px, season)
            run_configs(rows, selection.grid(CNN_GRID), scorer, done, f"cnn {key}")
            best = best_row([r for r in rows if not r.get("edge")], cnn_cost)
            extra = edge_extensions(best["config"])
            if extra:
                print(f"  cnn {key}: selected {best['config']} on the grid edge, extending {extra}")
                run_configs(rows, extra, lambda cfg: {**scorer(cfg), "edge": True}, done, f"cnn {key} edge")
            cnn_selected[key] = best_row(rows, cnn_cost)

        done["decision"] = {"rf": decide(rf_selected, "dry"), "cnn": decide(cnn_selected, "A"),
                            "rf_selected": {k: v["config"] for k, v in rf_selected.items()},
                            "cnn_selected": {k: v["config"] for k, v in cnn_selected.items()}}
        RESULTS_PATH.write_text(json.dumps(done, indent=2))

        test = done.setdefault("test", {})
        for season, row in rf_selected.items():
            if f"rf_{season}" not in test:
                test[f"rf_{season}"] = test_rf(row["config"], season)
                RESULTS_PATH.write_text(json.dumps(done, indent=2))
        for key, row in cnn_selected.items():
            if f"cnn_{key}" not in test:
                test[f"cnn_{key}"] = test_cnn(row["config"], *CNN_VARIANTS[key])
                RESULTS_PATH.write_text(json.dumps(done, indent=2))

        mlflow.log_params({"cnn_operational": done["decision"]["cnn"]["operational"],
                           "rf_operational": done["decision"]["rf"]["operational"]})
        mlflow.log_metrics({f"test_{k}": v["mean"] for k, v in test.items()})
        mlflow.log_artifact(str(RESULTS_PATH))

    print(json.dumps(done["decision"], indent=2))
    for k, v in done["test"].items():
        print(f"test {k}: {v['mean']:.4f} +/- {v['std']:.4f}")


if __name__ == "__main__":
    {"preregister": preregister, "score": score}[sys.argv[1]]()
