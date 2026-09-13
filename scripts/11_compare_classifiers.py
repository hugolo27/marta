"""Baseline vs. candidate comparison, phase1-classifier tasks 4.1-4.2. Runs both models across
5 seeds and applies the criterion fixed in design.md before training: the CNN only counts as a
genuine winner if its mean macro-F1 exceeds RF's by more than one pooled standard deviation.
Persists results to JSON so 12_plot_comparison.py always reflects the latest run, and logs every
run to MLflow (experiment "phase1-classifier") so runs stay comparable across code changes."""

import importlib
import json
from pathlib import Path

import mlflow
import numpy as np

import dataset_loader as dl

train_cnn = importlib.import_module("10_train_cnn")
train_rf = importlib.import_module("09_train_random_forest")

SEEDS = [42, 1, 7, 123, 2026]
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "comparison_results.json"
EXPERIMENT_NAME = "phase1-classifier"


def macro_f1(results):
    return results["report"]["macro avg"]["f1-score"]


def log_run(model_name, seed, params, results):
    with mlflow.start_run(run_name=f"{model_name}_seed{seed}", nested=True):
        mlflow.log_params({"model": model_name, "seed": seed, **params})
        mlflow.log_metric("macro_f1", macro_f1(results))
        mlflow.log_metric("accuracy", results["report"]["accuracy"])
        for cls, iou in zip(dl.CLASS_NAMES, results["iou_per_class"]):
            mlflow.log_metric(f"iou_{cls}", iou)


def main():
    mlflow.set_experiment(EXPERIMENT_NAME)
    rf_scores, cnn_scores = [], []

    with mlflow.start_run(run_name="rf_vs_cnn_comparison"):
        for seed in SEEDS:
            rf = train_rf.train(seed=seed, verbose=False)
            rf_results = train_rf.evaluate(rf)
            rf_scores.append(macro_f1(rf_results))
            log_run("rf", seed, {"n_estimators": train_rf.N_ESTIMATORS}, rf_results)

            model, device, _ = train_cnn.train(seed=seed, verbose=False)
            cnn_results = train_cnn.evaluate(model, device)
            cnn_scores.append(macro_f1(cnn_results))
            log_run("cnn", seed, {
                "batch_size": train_cnn.BATCH_SIZE, "lr": train_cnn.LEARNING_RATE,
                "max_epochs": train_cnn.MAX_EPOCHS, "dropout": train_cnn.DROPOUT,
            }, cnn_results)

            print(f"seed {seed}: RF macro-F1={rf_scores[-1]:.3f}  CNN macro-F1={cnn_scores[-1]:.3f}")

        rf_arr, cnn_arr = np.array(rf_scores), np.array(cnn_scores)
        rf_mean, rf_std = rf_arr.mean(), rf_arr.std()
        cnn_mean, cnn_std = cnn_arr.mean(), cnn_arr.std()
        pooled_std = np.sqrt((rf_std**2 + cnn_std**2) / 2)
        cnn_wins = bool(cnn_mean - rf_mean > pooled_std)

        print(f"\nRF:  mean={rf_mean:.3f} std={rf_std:.3f}  (runs: {rf_arr.round(3)})")
        print(f"CNN: mean={cnn_mean:.3f} std={cnn_std:.3f}  (runs: {cnn_arr.round(3)})")
        print(f"Pooled std: {pooled_std:.3f}, CNN - RF = {cnn_mean - rf_mean:.3f}")
        print("\nResult: CNN wins." if cnn_wins else
              "\nResult: CNN does NOT meaningfully outperform RF. Random Forest is selected "
              "as the classifier going forward (design.md criterion, fixed before this run).")

        mlflow.log_metrics({
            "rf_mean_f1": rf_mean, "rf_std_f1": rf_std,
            "cnn_mean_f1": cnn_mean, "cnn_std_f1": cnn_std,
            "pooled_std": pooled_std,
        })
        mlflow.log_param("cnn_wins", cnn_wins)

        OUT_PATH.write_text(json.dumps({
            "seeds": SEEDS, "rf_scores": rf_scores, "cnn_scores": cnn_scores,
            "rf_mean": rf_mean, "rf_std": rf_std, "cnn_mean": cnn_mean, "cnn_std": cnn_std,
            "cnn_wins": cnn_wins,
        }, indent=2))
        mlflow.log_artifact(str(OUT_PATH))
        print(f"\nresults saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
