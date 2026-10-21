"""3x3 vs. 33x33 CNN input, phase1-patch-size (tasks 1.1, 2.2, 3.1, 3.2). Selects the 3x3 CNN's
hyperparameters on val with the grid and rules of 24_hyperparameter_selection.py, then applies the
pre-registered patch-size rule (design D3) against the 33x33 CNN's stored val scores.

Two steps, run in this order:
  preregister -- hashes the README's pre-registered part (everything above "## Results") and logs
                 it to MLflow before any 3x3 configuration has been scored
  score       -- refuses to run if that part changed since, scores the 3x3 grid on val, applies
                 the rule, then reports both selected CNNs on test once (nothing is chosen with it)

Progress is saved after every configuration, so an interrupted run resumes.
Usage: .venv/bin/python scripts/31_patch_size_selection.py preregister|score"""

import hashlib
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import numpy as np

train_cnn = importlib.import_module("10_train_cnn")
selection = importlib.import_module("24_hyperparameter_selection")

STUDY_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"
OUT_DIR = STUDY_DIR / "patch_size_selection"
README = OUT_DIR / "README.md"
PREREG_PATH = OUT_DIR / "preregistration.json"
RESULTS_PATH = OUT_DIR / "results.json"
HYPERPARAM_RESULTS = STUDY_DIR / "hyperparameter_selection" / "results.json"
EXPERIMENT_NAME = "phase1-patch-size-selection"

CNN_33 = {"lr": 0.0003, "dropout": 0.5, "batch_size": 16}  # selected in phase1-hyperparameter-selection


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


def score_cnn_3(cfg, seeds, max_epochs=train_cnn.MAX_EPOCHS):
    scores, best, stop = [], [], []
    for seed in seeds:
        model, device, history = train_cnn.train(seed=seed, verbose=False, max_epochs=max_epochs, patch_px=3, **cfg)
        scores.append(selection.macro_f1(train_cnn.evaluate(model, device, split="val")))
        best_epoch, stop_epoch = train_cnn.epochs(history)
        best.append(best_epoch)
        stop.append(stop_epoch)
        with mlflow.start_run(run_name=f"cnn3_{cfg}_seed{seed}", nested=True):
            mlflow.log_params({"model": "cnn", "patch_px": 3, "seed": seed, "max_epochs": max_epochs, **cfg})
            mlflow.log_metrics({"val_macro_f1": scores[-1], "best_epoch": best_epoch, "stop_epoch": stop_epoch})
    truncated = max(stop) >= max_epochs
    row = selection.summarize(cfg, scores, {"max_epochs": max_epochs, "best_epoch": best, "stop_epoch": stop, "truncated": truncated})
    if truncated and max_epochs < selection.RERUN_MAX_EPOCHS:
        print(f"  {cfg} truncated at {max_epochs} epochs, re-running with {selection.RERUN_MAX_EPOCHS}")
        return score_cnn_3(cfg, seeds, selection.RERUN_MAX_EPOCHS)
    return row


def stored_33():
    rows = json.loads(HYPERPARAM_RESULTS.read_text())["cnn"]
    return next(r for r in rows if r["config"] == CNN_33)


def run_grid(rows, done):
    finished = [r["config"] for r in rows]
    for cfg in selection.grid(selection.CNN_GRID):
        if cfg in finished:
            continue
        rows.append(score_cnn_3(cfg, selection.SEEDS))
        r = rows[-1]
        print(f"  cnn3 {cfg}: val macro_f1={r['mean']:.3f} +/- {r['std']:.3f}")
        RESULTS_PATH.write_text(json.dumps(done, indent=2))
    return rows


def decide(row_3, row_33):
    pooled = float(np.sqrt((row_3["std"] ** 2 + row_33["std"] ** 2) / 2))
    diff = row_33["mean"] - row_3["mean"]
    return {
        "cnn3": row_3["config"], "cnn33": row_33["config"],
        "cnn3_val": [row_3["mean"], row_3["std"]], "cnn33_val": [row_33["mean"], row_33["std"]],
        "cnn33_minus_cnn3": diff, "pooled_std": pooled,
        "operational_patch_px": 33 if diff > pooled else 3,
    }


def test_once(cfg, patch_px):
    scores = []
    for seed in selection.SEEDS:
        model, device, _ = train_cnn.train(seed=seed, verbose=False, patch_px=patch_px, **cfg)
        scores.append(selection.macro_f1(train_cnn.evaluate(model, device, split="test")))
    return selection.summarize(cfg, scores)


def score():
    prereg = json.loads(PREREG_PATH.read_text())
    digest = hashlib.sha256(preregistered_text().encode()).hexdigest()
    if digest != prereg["sha256"]:
        sys.exit("pre-registered part of README changed since preregistration -- refusing to score")

    done = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else {"preregistration": prereg}
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="patch_size_selection"):
        mlflow.log_param("readme_sha256", digest)
        print("3x3 CNN grid (val)")
        rows = run_grid(done.setdefault("cnn3", []), done)

        top = max(r["mean"] for r in rows)
        best = min([r for r in rows if r["mean"] == top],
                   key=lambda r: (selection.distance(r["config"], CNN_33), np.mean(r["stop_epoch"])))
        done["decision"] = decide(best, stored_33())
        RESULTS_PATH.write_text(json.dumps(done, indent=2))

        if "test" not in done:
            print("\nTest, once, both selected CNNs (reported, not used to choose)")
            done["test"] = {"cnn3": test_once(best["config"], 3), "cnn33": test_once(CNN_33, 33)}
            RESULTS_PATH.write_text(json.dumps(done, indent=2))

        mlflow.log_params({"cnn3_selected": json.dumps(best["config"]),
                           "operational_patch_px": done["decision"]["operational_patch_px"]})
        mlflow.log_metrics({"cnn3_test_macro_f1": done["test"]["cnn3"]["mean"],
                            "cnn33_test_macro_f1": done["test"]["cnn33"]["mean"]})
        mlflow.log_artifact(str(RESULTS_PATH))

    d = done["decision"]
    print(f"\n3x3 {d['cnn3']} val={d['cnn3_val'][0]:.4f}+/-{d['cnn3_val'][1]:.4f}  "
          f"33x33 {d['cnn33']} val={d['cnn33_val'][0]:.4f}+/-{d['cnn33_val'][1]:.4f}  "
          f"33-3={d['cnn33_minus_cnn3']:+.4f} pooled_std={d['pooled_std']:.4f} -> operational {d['operational_patch_px']}x{d['operational_patch_px']}")
    for name, r in done["test"].items():
        print(f"test {name}: {r['mean']:.4f} +/- {r['std']:.4f}")
    print(f"saved: {RESULTS_PATH}")


if __name__ == "__main__":
    {"preregister": preregister, "score": score}[sys.argv[1]]()
