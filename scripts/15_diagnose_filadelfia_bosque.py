"""Diagnostic investigation for phase1-classifier task 4.4: why does the CNN specifically fail
on bosque in Filadelfia (IoU 0.803 on the AOI test split -> 0.451 there) while Random Forest holds
up (0.823)? Re-extracts the same Filadelfia points as 14_evaluate_filadelfia_holdout.py but keeps
per-point diagnostic data (period, both models' predictions, raw patches) instead of only
aggregate metrics, to test concrete hypotheses instead of speculating.

Usage: .venv/bin/python scripts/15_diagnose_filadelfia_bosque.py"""

import importlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import dataset_loader as dl
import gee_session
import holdout_eval

filadelfia = importlib.import_module("14_evaluate_filadelfia_holdout")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area"
BAND_NAMES = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B9", "B11", "B12", "NDVI"]
CENTER = filadelfia.PATCH_RADIUS_PX


def center_pixels(rows, mask):
    return np.stack([rows[i]["patch"][CENTER, CENTER, :] for i in np.where(mask)[0]])


def main():
    gee_session.init()
    rows = filadelfia.extract_points(filadelfia.heldout_geometry())
    y_true = np.array([r["label"] for r in rows])
    periods = np.array([r["period"] for r in rows])

    print("\nTraining Random Forest and CNN (seed=42, same config as the operational comparison)...")
    rf = holdout_eval.train_rf.train(verbose=False)
    rf_pred = holdout_eval.predict_rf(rows, rf)

    model, device, _ = holdout_eval.train_cnn.train(verbose=False)
    cnn_pred = holdout_eval.predict_cnn(rows, model, device)

    bosque_id = dl.CLASS_TO_ID["bosque"]
    bosque_mask = y_true == bosque_id
    cnn_wrong = bosque_mask & (cnn_pred != bosque_id)
    cnn_right = bosque_mask & (cnn_pred == bosque_id)
    print(f"\nTrue bosque points: {int(bosque_mask.sum())}  "
          f"CNN correct: {int(cnn_right.sum())}  CNN wrong: {int(cnn_wrong.sum())}")

    print("\n--- 1. Period skew ---")
    for period in ["2019", "2023"]:
        pmask = periods == period
        n_bosque_p = int((bosque_mask & pmask).sum())
        n_wrong_p = int((cnn_wrong & pmask).sum())
        rate = n_wrong_p / n_bosque_p if n_bosque_p else float("nan")
        print(f"  {period}: {n_bosque_p} true bosque, {n_wrong_p} CNN-misclassified ({rate:.1%})")

    print("\n--- 2. What RF predicted on the exact points CNN got wrong ---")
    n_wrong = int(cnn_wrong.sum())
    if n_wrong:
        rf_right_where_cnn_wrong = int((rf_pred[cnn_wrong] == bosque_id).sum())
        print(f"  Of {n_wrong} points CNN misclassified, RF got {rf_right_where_cnn_wrong} right "
              f"({rf_right_where_cnn_wrong / n_wrong:.1%})")
        rf_pred_dist = {dl.CLASS_NAMES[c]: int((rf_pred[cnn_wrong] == c).sum()) for c in range(3)}
        print(f"  RF's predictions on those same points: {rf_pred_dist}")

    print("\n--- 3. Band stats: SWIR (B11, B12) and red-edge (B5), the top RF features ---")
    X_train, y_train = dl.load_pixel_features("train")
    train_bosque = X_train[y_train == bosque_id]
    fil_wrong_px = center_pixels(rows, cnn_wrong)
    fil_right_px = center_pixels(rows, cnn_right)
    for name, arr in [("AOI train bosque", train_bosque),
                       ("Filadelfia bosque, CNN correct", fil_right_px),
                       ("Filadelfia bosque, CNN wrong", fil_wrong_px)]:
        b11, b12, b5 = (arr[:, BAND_NAMES.index(b)] for b in ("B11", "B12", "B5"))
        print(f"  {name} (n={len(arr)}): "
              f"B11={b11.mean():.0f}+/-{b11.std():.0f}  "
              f"B12={b12.mean():.0f}+/-{b12.std():.0f}  "
              f"B5={b5.mean():.0f}+/-{b5.std():.0f}")

    print("\n--- 4. Visual comparison ---")
    RGB_IDX = [3, 2, 1]
    n_show = min(6, int(cnn_wrong.sum()), int(cnn_right.sum()))
    if n_show:
        wrong_idx = np.where(cnn_wrong)[0][:n_show]
        right_idx = np.where(cnn_right)[0][:n_show]
        fig, axes = plt.subplots(2, n_show, figsize=(2.2 * n_show, 4.8))
        for col, i in enumerate(wrong_idx):
            rgb = np.clip(rows[i]["patch"][:, :, RGB_IDX] / 3000, 0, 1)
            axes[0, col].imshow(rgb)
            axes[0, col].set_xticks([])
            axes[0, col].set_yticks([])
        axes[0, 0].set_ylabel("CNN dice pasto\n(bosque real)", fontsize=10)
        for col, i in enumerate(right_idx):
            rgb = np.clip(rows[i]["patch"][:, :, RGB_IDX] / 3000, 0, 1)
            axes[1, col].imshow(rgb)
            axes[1, col].set_xticks([])
            axes[1, col].set_yticks([])
        axes[1, 0].set_ylabel("CNN acierta\nbosque", fontsize=10)
        fig.suptitle("Filadelfia: bosque real, CNN incorrecto (arriba) vs correcto (abajo)")
        fig.tight_layout()
        out_path = OUT_DIR / "filadelfia_bosque_diagnosis.png"
        fig.savefig(out_path, dpi=130)
        print(f"  saved: {out_path}")
    else:
        print("  not enough examples in one of the two groups to build a comparison grid")


if __name__ == "__main__":
    main()
