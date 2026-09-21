"""One-parameter-at-a-time hyperparameter sensitivity sweep, designed in
GUIA_DE_ESTUDIO.md sec 7.4 but never run until now. Each parameter is varied alone,
holding the rest at their final trained values (09_train_random_forest.py /
10_train_cnn.py) -- not a full factorial grid, which would cost hours for no
proportional information gain. Logs every run to MLflow (experiment "phase1-classifier")
and persists a summary JSON so the result can be cited without re-running it."""

import importlib
import json
from pathlib import Path

import mlflow
import numpy as np

import dataset_loader as dl

train_cnn = importlib.import_module("10_train_cnn")
train_rf = importlib.import_module("09_train_random_forest")

RF_SEEDS = [42, 1, 7, 123, 2026]
CNN_SEEDS = [42, 1, 7]
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "study_area" / "hyperparameter_sweep_results.json"
EXPERIMENT_NAME = "phase1-classifier"

RF_SWEEP = {
    "n_estimators": [300, 400, 500],
    "max_depth": [None, 10, 20],
}
CNN_SWEEP = {
    "dropout": [0.3, 0.4, 0.5],
    "lr": [0.0001, 0.001, 0.01],
    "batch_size": [16, 32, 64],
}


def macro_f1(results):
    return results["report"]["macro avg"]["f1-score"]


def sweep_rf_param(param, values):
    rows = []
    for value in values:
        scores = []
        for seed in RF_SEEDS:
            rf = train_rf.train(seed=seed, verbose=False, **{param: value})
            results = train_rf.evaluate(rf)
            score = macro_f1(results)
            scores.append(score)
            with mlflow.start_run(run_name=f"sweep_rf_{param}_{value}_seed{seed}", nested=True):
                mlflow.log_params({"model": "rf", "sweep_param": param, param: str(value), "seed": seed})
                mlflow.log_metric("macro_f1", score)
        arr = np.array(scores)
        print(f"  RF {param}={value}: macro_f1={arr.mean():.3f} +/- {arr.std():.3f}")
        rows.append({"param": param, "value": value, "seeds": RF_SEEDS, "scores": scores,
                      "mean": arr.mean(), "std": arr.std()})
    return rows


def sweep_cnn_param(param, values):
    rows = []
    for value in values:
        scores = []
        for seed in CNN_SEEDS:
            model, device, _ = train_cnn.train(seed=seed, verbose=False, **{param: value})
            results = train_cnn.evaluate(model, device)
            score = macro_f1(results)
            scores.append(score)
            with mlflow.start_run(run_name=f"sweep_cnn_{param}_{value}_seed{seed}", nested=True):
                mlflow.log_params({"model": "cnn", "sweep_param": param, param: value, "seed": seed})
                mlflow.log_metric("macro_f1", score)
        arr = np.array(scores)
        print(f"  CNN {param}={value}: macro_f1={arr.mean():.3f} +/- {arr.std():.3f}")
        rows.append({"param": param, "value": value, "seeds": CNN_SEEDS, "scores": scores,
                      "mean": arr.mean(), "std": arr.std()})
    return rows


def main():
    mlflow.set_experiment(EXPERIMENT_NAME)
    summary = {"rf": {}, "cnn": {}}

    with mlflow.start_run(run_name="hyperparameter_sweep"):
        print("Random Forest sweep")
        for param, values in RF_SWEEP.items():
            summary["rf"][param] = sweep_rf_param(param, values)

        print("\nCNN sweep")
        for param, values in CNN_SWEEP.items():
            summary["cnn"][param] = sweep_cnn_param(param, values)

        OUT_PATH.write_text(json.dumps(summary, indent=2, default=str))
        mlflow.log_artifact(str(OUT_PATH))
        print(f"\nresults saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
