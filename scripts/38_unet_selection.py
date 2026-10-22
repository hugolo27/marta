"""U-Net selection, phase1-segmentation D5 (tasks 4.1-4.3). The rules are in
data/study_area/unet_selection/README.md, above "## Results"; the split, cap, patience and RF
sample size come from the pilot (37_unet_pilot.py).

Four steps, run in this order:
  split       -- final split: test = every reserve block, validation = the pilot's size, best of 100 draws
  preregister -- hashes the README's pre-registered part and logs it to MLflow before scoring
  score       -- U-Net and RF grids on validation, edge rule, comparison; resumable from results.json
  test        -- both selected models on the test tiles, once

Usage: .venv/bin/python scripts/38_unet_selection.py split|preregister|score|test"""

import hashlib
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import numpy as np

import classifier_report
import dataset_loader as dl

unet = importlib.import_module("36_train_unet")
train_rf = importlib.import_module("09_train_random_forest")
selection = importlib.import_module("24_hyperparameter_selection")
pilot = importlib.import_module("37_unet_pilot")

STUDY_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"
OUT_DIR = STUDY_DIR / "unet_selection"
PILOT_DIR = STUDY_DIR / "unet_pilot"
README = OUT_DIR / "README.md"
PREREG_PATH = OUT_DIR / "preregistration.json"
SPLIT_PATH = OUT_DIR / "final_split.json"
RESULTS_PATH = OUT_DIR / "results.json"
EXPERIMENT_NAME = "phase1-unet-selection"

UNET_GRID = {"tile_px": [48, 96, 192], "lr": [0.0001, 0.0003, 0.001], "batch_size": [8, 16, 32]}
EDGE_STEP = {"lr": {0.0001: 0.00003, 0.001: 0.003}, "batch_size": {8: 4, 32: 64}}
CAP_MARGIN = 10
SPLIT_DRAWS = 100  # blockCV's default number of random block allocations (Valavi et al., 2019)


def preregistered_text():
    text = README.read_text()
    return text[:text.index("## Results")]


def preregister():
    digest = hashlib.sha256(preregistered_text().encode()).hexdigest()
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="preregistration"):
        mlflow.log_param("readme_sha256", digest)
        mlflow.log_artifact(str(README))
    PREREG_PATH.write_text(json.dumps({"sha256": digest, "utc": datetime.now(timezone.utc).isoformat()}, indent=2))
    print(f"pre-registered {README} sha256={digest}")


def balanced_split():
    """Test = every reserve block; validation = the pilot's validation size in pool blocks. Of
    SPLIT_DRAWS draws, keeps the one whose share of each class's labeled cells in validation stays
    closest to validation's share of all labeled cells (stratified splits, Kohavi 1995; repeated block
    allocation, Valavi et al., 2019). Cells, not the tile's center class: Dice is scored on cells, and
    tiles centered on cultivo are often mostly another class. Replaces the pilot's 10% floor, which
    had no source."""
    rows = dl.load_tile_manifest()
    pool = [r for r in rows if r["group"] == "pool"]
    n_val = min(pilot_decisions()["val_blocks_needed"] or len(pool), len({dl.tile_block(r) for r in pool}))
    best = None
    for seed in range(42, 42 + SPLIT_DRAWS):
        val_blocks = set(pilot.shuffled_blocks(pool, seed)[:n_val])
        split = {r["path"]: "test" if r["group"] == "reserve" else "val" if dl.tile_block(r) in val_blocks else "train"
                 for r in rows}
        cells = {c: {g: sum(int(r[f"px_{c}"]) for r in rows if split[r["path"]] == g) for g in ("train", "val", "test")}
                 for c in dl.CLASS_NAMES}
        shares = {g: {c: cells[c][g] / sum(cells[c].values()) for c in dl.CLASS_NAMES} for g in ("val", "test")}
        overall = {g: sum(cells[c][g] for c in dl.CLASS_NAMES) / sum(sum(v.values()) for v in cells.values())
                   for g in ("val", "test")}
        gap = max(abs(s - overall["val"]) for s in shares["val"].values())
        if best is None or gap < best["val_gap"]:
            best = {"seed": seed, "val_gap": gap, "shares": shares, "overall": overall, "split": split,
                    "test_gap": max(abs(s - overall["test"]) for s in shares["test"].values())}
    split = best.pop("split")
    SPLIT_PATH.write_text(json.dumps(split, indent=1))
    best["counts"] = {g: list(split.values()).count(g) for g in ("train", "val", "test")}
    (OUT_DIR / "split_stats.json").write_text(json.dumps(best, indent=2))
    print(json.dumps(best, indent=1))


def splits():
    split = json.loads(SPLIT_PATH.read_text())
    rows = dl.load_tile_manifest()
    return {g: [r for r in rows if split[r["path"]] == g] for g in ("train", "val", "test")}


def pilot_decisions():
    return json.loads((PILOT_DIR / "results.json").read_text())["decisions"]


def save(results):
    RESULTS_PATH.write_text(json.dumps(results, indent=2))


def score_unet(cfg, data, max_epochs, patience):
    scores, best, stop = [], [], []
    for seed in selection.SEEDS:
        model, device, history = unet.train(data["train"], data["val"], seed=seed, max_epochs=max_epochs,
                                            patience=patience, verbose=False, **cfg)
        scores.append(float(classifier_report.dice_from_counts(
            unet.predict_counts_full(model, data["val"], device).sum(axis=0))[1]))
        best_epoch, stop_epoch = unet.epochs(history)
        best.append(best_epoch)
        stop.append(stop_epoch)
        with mlflow.start_run(run_name=f"unet_{cfg}_seed{seed}", nested=True):
            mlflow.log_params({"model": "unet", "seed": seed, "max_epochs": max_epochs, "patience": patience, **cfg})
            mlflow.log_metrics({"val_macro_dice": scores[-1], "best_epoch": best_epoch, "stop_epoch": stop_epoch})
    near_cap = max(best) > max_epochs - CAP_MARGIN
    if near_cap and max_epochs == pilot_decisions()["max_epochs"]:
        print(f"  {cfg} best epoch near the cap, re-running with {3 * max_epochs}")
        return score_unet(cfg, data, 3 * max_epochs, patience)
    return selection.summarize(cfg, scores, {"max_epochs": max_epochs, "best_epoch": best, "stop_epoch": stop})


def score_rf(cfg, data, max_samples):
    scores = []
    for seed in selection.SEEDS:
        rf = train_rf.train_tiles(data["train"], seed=seed, max_samples=max_samples, **cfg)
        scores.append(float(classifier_report.dice_from_counts(train_rf.predict_counts_tiles(rf, data["val"]).sum(axis=0))[1]))
        with mlflow.start_run(run_name=f"rf_{cfg}_seed{seed}", nested=True):
            mlflow.log_params({"model": "rf", "seed": seed, "max_samples": max_samples, **{k: str(v) for k, v in cfg.items()}})
            mlflow.log_metric("val_macro_dice", scores[-1])
    return selection.summarize(cfg, scores)


def run_grid(name, configs, scorer, results):
    rows = results.setdefault(name, [])
    for cfg in configs:
        if cfg in [r["config"] for r in rows]:
            continue
        rows.append(scorer(cfg))
        print(f"  {name} {cfg}: val macro Dice {rows[-1]['mean']:.4f} +/- {rows[-1]['std']:.4f}", flush=True)
        save(results)
    return rows


def best(rows, tie_key):
    top = max(r["mean"] for r in rows)
    return min([r for r in rows if r["mean"] == top], key=tie_key)


def score():
    if hashlib.sha256(preregistered_text().encode()).hexdigest() != json.loads(PREREG_PATH.read_text())["sha256"]:
        sys.exit("README changed since pre-registration -- refusing to score")
    data, pilot = splits(), pilot_decisions()
    patience = pilot["patience"] or pilot["max_epochs"]
    results = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else {}
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="selection"):
        print("Random Forest grid (val)")
        rf_rows = run_grid("rf", selection.grid(selection.RF_GRID),
                           lambda cfg: score_rf(cfg, data, pilot["rf_max_samples"]), results)
        print("U-Net grid (val)")
        unet_scorer = lambda cfg: score_unet(cfg, data, pilot["max_epochs"], patience)
        rows = run_grid("unet", selection.grid(UNET_GRID), unet_scorer, results)
        tie = lambda r: (r["config"]["tile_px"], -r["config"]["batch_size"])
        chosen = best(rows, tie)["config"]
        edges = [{**chosen, axis: EDGE_STEP[axis][chosen[axis]]} for axis in EDGE_STEP if chosen[axis] in EDGE_STEP[axis]]
        if chosen["tile_px"] == 192:
            print("tile 192 selected: extract 288 px tiles before going on (README edge rule)")
        rows = run_grid("unet", edges, unet_scorer, results)
        u, rf = best(rows, tie), best(rf_rows, lambda r: r["config"]["n_estimators"])
        pooled = float(np.sqrt((u["std"] ** 2 + rf["std"] ** 2) / 2))
        results["selection"] = {"unet": u["config"], "rf": rf["config"], "unet_mean": u["mean"], "rf_mean": rf["mean"],
                                "unet_max_epochs": u["max_epochs"], "unet_minus_rf": u["mean"] - rf["mean"], "pooled_std": pooled,
                                "unet_better": u["mean"] - rf["mean"] > pooled, "edges_run": edges}
        save(results)
        mlflow.log_dict(results["selection"], "selection.json")
    print(json.dumps(results["selection"], indent=1))


def test():
    results = json.loads(RESULTS_PATH.read_text())
    if "test" in results:
        sys.exit("test already run once")
    data, pilot = splits(), pilot_decisions()
    sel = results["selection"]
    out = {"unet": [], "rf": []}
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="test_once"):
        for seed in selection.SEEDS:
            model, device, _ = unet.train(data["train"], data["val"], seed=seed, max_epochs=sel["unet_max_epochs"],
                                          patience=pilot["patience"] or pilot["max_epochs"], verbose=False, **sel["unet"])
            dice, macro = classifier_report.dice_from_counts(unet.predict_counts_full(model, data["test"], device).sum(axis=0))
            out["unet"].append({"seed": seed, "macro_dice": float(macro), "dice": dict(zip(dl.CLASS_NAMES, dice.tolist()))})
            if seed == 42:
                unet.save_checkpoint(model, seed)
            rf = train_rf.train_tiles(data["train"], seed=seed, max_samples=pilot["rf_max_samples"], **sel["rf"])
            dice, macro = classifier_report.dice_from_counts(train_rf.predict_counts_tiles(rf, data["test"]).sum(axis=0))
            out["rf"].append({"seed": seed, "macro_dice": float(macro), "dice": dict(zip(dl.CLASS_NAMES, dice.tolist()))})
        results["test"] = out
        save(results)
        mlflow.log_dict(out, "test.json")
    for name, runs in out.items():
        macro = [r["macro_dice"] for r in runs]
        print(f"{name}: test macro Dice {np.mean(macro):.4f} +/- {np.std(macro, ddof=1):.4f}")


if __name__ == "__main__":
    {"split": balanced_split, "preregister": preregister, "score": score, "test": test}[sys.argv[1]]()
