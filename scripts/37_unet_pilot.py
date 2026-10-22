"""U-Net pilot, phase1-segmentation D4 (tasks 3.1-3.2). The rules are in
data/study_area/unet_pilot/README.md, above "## Results"; this script follows them in order and
writes every number they produce to results.json.

Two steps, run in this order:
  preregister -- hashes the README's pre-registered part and logs it to MLflow before any run
  run         -- refuses to run if that part changed since; resumable from results.json

Pilot 2 (task 3.3) repeats it with another provisional validation share: --val-share 0.5, 0.1 or
0.05 reads the README in data/study_area/unet_pilot_sensitivity/ and writes to a subfolder per share.
Both pilots read only the first batch of tiles.

Usage: .venv/bin/python scripts/37_unet_pilot.py preregister|run [--val-share X]"""

import argparse
import hashlib
import importlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import numpy as np

import classifier_report
import dataset_loader as dl

unet = importlib.import_module("36_train_unet")
train_rf = importlib.import_module("09_train_random_forest")

STUDY_DIR = Path(__file__).resolve().parents[1] / "data" / "study_area"
PILOT_DIR = STUDY_DIR / "unet_pilot"
OUT_DIR = PILOT_DIR
README = PILOT_DIR / "README.md"
PREREG_PATH = PILOT_DIR / "preregistration.json"
RESULTS_PATH = OUT_DIR / "results.json"
EXPERIMENT_NAME = "phase1-unet-pilot"

TILE_PX = 96
BATCH_SIZE = 16
LRS = [0.0001, 0.0003, 0.001]
SEEDS = [42, 1]
MAX_EPOCHS = 100
RAISED_MAX_EPOCHS = 300
CAP_MARGIN = 10
MAX_PATIENCE = 30
SIZES = list(range(10, 401, 10))
N_BOOTSTRAP = 1000
VAL_SHARE_PILOT = 0.20
FRACTIONS = [0.25, 0.5, 0.75, 1.0]
RF_SAMPLES = [25000, 50000, 100000, 200000, 400000]
MIN_EVAL_SHARE = 0.10


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


def shuffled_blocks(rows, seed=42):
    blocks = sorted({dl.tile_block(r) for r in rows})
    random.Random(seed).shuffle(blocks)
    return blocks


def provisional_split(pool):
    blocks = shuffled_blocks(pool)
    val_blocks = set(blocks[:round(len(blocks) * VAL_SHARE_PILOT)])
    train = [r for r in pool if dl.tile_block(r) not in val_blocks]
    val = [r for r in pool if dl.tile_block(r) in val_blocks]
    return train, val


def save(results):
    RESULTS_PATH.write_text(json.dumps(results, indent=2))


def unet_run(key, results, train_rows, val_rows, lr, seed, max_epochs, patience=None):
    if key in results["runs"]:
        return
    start = time.time()
    model, device, history = unet.train(train_rows, val_rows, tile_px=TILE_PX, lr=lr, batch_size=BATCH_SIZE, seed=seed,
                                        max_epochs=max_epochs, patience=patience, verbose=False)
    counts = unet.predict_counts(model, val_rows, device)
    np.save(OUT_DIR / f"counts_{key}.npy", counts)
    best_epoch, stop_epoch = unet.epochs(history)
    row = {"lr": lr, "seed": seed, "n_train": len(train_rows), "history": history, "best_epoch": best_epoch,
           "stop_epoch": stop_epoch, "best": max(history["val_macro_dice"]), "minutes": round((time.time() - start) / 60, 1),
           "device": device}
    with mlflow.start_run(run_name=key, nested=True):
        mlflow.log_params({"model": "unet", "tile_px": TILE_PX, "batch_size": BATCH_SIZE, "lr": lr, "seed": seed,
                           "max_epochs": max_epochs, "patience": str(patience), "n_train": len(train_rows)})
        for epoch, value in enumerate(history["val_macro_dice"], 1):
            mlflow.log_metric("val_macro_dice", value, step=epoch)
        mlflow.log_metrics({"best_val_macro_dice": row["best"], "best_epoch": best_epoch, "stop_epoch": stop_epoch})
    results["runs"][key] = row
    save(results)
    print(f"  {key}: best {row['best']:.4f} at epoch {best_epoch}/{stop_epoch}, {row['minutes']} min", flush=True)


def pooled_seed_std(values_by_config):
    return float(np.sqrt(np.mean([np.var(v, ddof=1) for v in values_by_config])))


def patience_rule(histories, s):
    for p in range(1, MAX_PATIENCE + 1):
        ok = True
        for h in histories:
            best, since = -np.inf, 0
            for value in h:
                if value > best:
                    best, since = value, 0
                else:
                    since += 1
                    if since >= p:
                        break
            ok &= best >= max(h) - s
        if ok:
            return p
    return None


def block_counts(counts, rows):
    keys = [dl.tile_block(r) for r in rows]
    blocks = sorted(set(keys))
    index = {b: i for i, b in enumerate(blocks)}
    out = np.zeros((len(blocks),) + counts.shape[1:])
    for k, c in zip(keys, counts):
        out[index[k]] += c
    return out


def bootstrap_spread(per_block, n, rng, other=None):
    idx = rng.integers(0, len(per_block), size=(N_BOOTSTRAP, n))
    macro = classifier_report.dice_from_counts(per_block[idx].sum(axis=1))[1]
    if other is not None:
        macro = macro - classifier_report.dice_from_counts(other[idx].sum(axis=1))[1]
    return float(np.std(macro, ddof=1))


def smallest_size(spreads, s):
    return next((n for n, spread in spreads.items() if spread <= s), None)


def final_split(pool, reserve, n_val, n_test):
    for seed in range(42, 142):
        test_blocks = set(shuffled_blocks(reserve, seed)[:n_test])
        val_blocks = set(shuffled_blocks(pool, seed)[:n_val])
        split = {}
        for r in pool + reserve:
            b = dl.tile_block(r)
            split[r["path"]] = "test" if b in test_blocks else "val" if b in val_blocks else "train"
        shares = {}
        for c in dl.CLASS_NAMES:
            tiles = [split[r["path"]] for r in pool + reserve if r["center_class"] == c]
            shares[c] = {g: tiles.count(g) / len(tiles) for g in ("val", "test")}
        if all(min(v.values()) >= MIN_EVAL_SHARE for v in shares.values()):
            return split, seed, shares
    # The 10% floor was replaced by 38_unet_selection.py split (no source), so pilot 2 records a
    # miss instead of stopping; with a 5% validation share no draw meets it
    return split, None, shares


def run():
    if hashlib.sha256(preregistered_text().encode()).hexdigest() != json.loads(PREREG_PATH.read_text())["sha256"]:
        sys.exit("README changed since pre-registration")
    manifest = [r for r in dl.load_tile_manifest() if r["batch"] == "1"]
    pool = [r for r in manifest if r["group"] == "pool"]
    reserve = [r for r in manifest if r["group"] == "reserve"]
    train_rows, val_rows = provisional_split(pool)
    results = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else {"runs": {}}
    results["provisional"] = {"train_tiles": len(train_rows), "val_tiles": len(val_rows),
                              "val_blocks": len({dl.tile_block(r) for r in val_rows})}
    print(f"pool {len(pool)} tiles: provisional train {len(train_rows)}, val {len(val_rows)}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=f"pilot_val{round(VAL_SHARE_PILOT * 100)}"):
        for lr in LRS:
            for seed in SEEDS:
                unet_run(f"lr{lr}_seed{seed}", results, train_rows, val_rows, lr, seed, MAX_EPOCHS)
        keys = {lr: [f"lr{lr}_seed{seed}" for seed in SEEDS] for lr in LRS}
        runs = results["runs"]
        s = pooled_seed_std([[runs[k]["best"] for k in keys[lr]] for lr in LRS])
        histories = [runs[k]["history"]["val_macro_dice"] for k in sum(keys.values(), [])]
        cap = RAISED_MAX_EPOCHS if any(runs[k]["best_epoch"] > MAX_EPOCHS - CAP_MARGIN for k in sum(keys.values(), [])) else MAX_EPOCHS
        patience = patience_rule(histories, s)

        rng = np.random.default_rng(42)
        per_block = {k: block_counts(np.load(OUT_DIR / f"counts_{k}.npy"), val_rows) for k in sum(keys.values(), [])}
        test_spread = {n: float(np.mean([bootstrap_spread(b, n, rng) for b in per_block.values()])) for n in SIZES}
        pairs = [(f"lr{a}_seed{seed}", f"lr{b}_seed{seed}") for a, b in zip(LRS, LRS[1:]) for seed in SEEDS]
        val_spread = {n: float(np.mean([bootstrap_spread(per_block[a], n, rng, per_block[b]) for a, b in pairs])) for n in SIZES}
        n_test, n_val = smallest_size(test_spread, s), smallest_size(val_spread, s)
        avail_test, avail_val = len({dl.tile_block(r) for r in reserve}), len({dl.tile_block(r) for r in pool})
        n_test_used = min(n_test or avail_test, avail_test)
        n_val_used = min(n_val or avail_val, avail_val)
        split, split_seed, shares = final_split(pool, reserve, n_val_used, n_test_used)
        (OUT_DIR / "final_split.json").write_text(json.dumps(split, indent=1))
        results["decisions"] = {
            "seed_std": s, "max_epochs": cap, "patience": patience,
            "test_spread": test_spread, "val_spread": val_spread,
            "test_blocks_needed": n_test, "val_blocks_needed": n_val,
            "test_blocks_used": n_test_used, "val_blocks_used": n_val_used,
            "final_split_seed": split_seed, "final_eval_shares": shares,
            "final_counts": {g: list(split.values()).count(g) for g in ("train", "val", "test")},
        }
        save(results)
        print(json.dumps({k: v for k, v in results["decisions"].items() if "spread" not in k}, indent=1), flush=True)

        train_blocks = shuffled_blocks(train_rows)
        for frac in FRACTIONS:
            keep = set(train_blocks[:round(len(train_blocks) * frac)])
            subset = [r for r in train_rows if dl.tile_block(r) in keep]
            for seed in SEEDS:
                unet_run(f"curve{frac}_seed{seed}", results, subset, val_rows, 0.0003, seed, cap, patience or cap)
        curve = {frac: float(np.mean([runs[f"curve{frac}_seed{seed}"]["best"] for seed in SEEDS])) for frac in FRACTIONS}
        results["decisions"]["learning_curve"] = curve
        results["decisions"]["more_tiles_needed"] = curve[1.0] - curve[0.75] > s
        save(results)

        rf_scores = results.setdefault("rf", {})
        for n in RF_SAMPLES:
            for seed in SEEDS:
                key = f"rf{n}_seed{seed}"
                if key in rf_scores:
                    continue
                rf = train_rf.train_tiles(train_rows, seed=seed, max_samples=n, tile_px=TILE_PX)
                rf_scores[key] = float(classifier_report.dice_from_counts(
                    train_rf.predict_counts_tiles(rf, val_rows, TILE_PX).sum(axis=0))[1])
                with mlflow.start_run(run_name=key, nested=True):
                    mlflow.log_params({"model": "rf", "max_samples": n, "seed": seed})
                    mlflow.log_metric("val_macro_dice", rf_scores[key])
                save(results)
                print(f"  {key}: {rf_scores[key]:.4f}", flush=True)
        s_rf = pooled_seed_std([[rf_scores[f"rf{n}_seed{seed}"] for seed in SEEDS] for n in RF_SAMPLES])
        means = {n: float(np.mean([rf_scores[f"rf{n}_seed{seed}"] for seed in SEEDS])) for n in RF_SAMPLES}
        results["decisions"].update({"rf_seed_std": s_rf, "rf_means": means,
                                     "rf_max_samples": next(n for n in RF_SAMPLES if means[n] >= max(means.values()) - s_rf)})
        save(results)
        mlflow.log_dict(results["decisions"], "decisions.json")
        print(json.dumps({k: v for k, v in results["decisions"].items() if "spread" not in k}, indent=1))


def configure(val_share):
    global PILOT_DIR, OUT_DIR, README, PREREG_PATH, RESULTS_PATH, EXPERIMENT_NAME, VAL_SHARE_PILOT
    PILOT_DIR = STUDY_DIR / "unet_pilot_sensitivity"
    OUT_DIR = PILOT_DIR / f"val{round(val_share * 100)}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    README = PILOT_DIR / "README.md"
    PREREG_PATH = PILOT_DIR / "preregistration.json"
    RESULTS_PATH = OUT_DIR / "results.json"
    EXPERIMENT_NAME = "phase1-unet-pilot-sensitivity"
    VAL_SHARE_PILOT = val_share


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["preregister", "run"])
    parser.add_argument("--val-share", type=float)
    args = parser.parse_args()
    if args.val_share:
        configure(args.val_share)
    {"preregister": preregister, "run": run}[args.step]()
