"""Random Forest baseline, phase1-classifier tasks 2.1-2.2. Per-pixel spectral features
(12 Sentinel-2 bands + NDVI), not the 33x33 patches — RF doesn't benefit from the spatial
window the CNN uses, see design.md."""

from collections import Counter

import numpy as np
from sklearn.ensemble import RandomForestClassifier

import classifier_report
import dataset_loader as dl

N_ESTIMATORS = 500
MAX_DEPTH = None
MAX_FEATURES = "sqrt"
SEASON = "drywet"


def train(seed=42, verbose=True, n_estimators=N_ESTIMATORS, max_depth=MAX_DEPTH, max_features=MAX_FEATURES,
          season=SEASON):
    X_train, y_train = dl.load_pixel_features("train", season)
    if verbose:
        counts = Counter(y_train)
        print("Training class distribution:", {dl.CLASS_NAMES[k]: v for k, v in sorted(counts.items())})
    rf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, max_features=max_features,
                                random_state=seed, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf.season = season
    return rf


def evaluate(rf, split="test"):
    X, y = dl.load_pixel_features(split, rf.season)
    pred = rf.predict(X)
    return classifier_report.evaluate_predictions(y, pred)


def main():
    rf = train()
    print("Feature importances (bands B1..B12, NDVI):", rf.feature_importances_.round(3))
    results = evaluate(rf)
    classifier_report.print_evaluation(results, "Random Forest")


if __name__ == "__main__":
    main()


def train_tiles(rows, seed=42, n_estimators=N_ESTIMATORS, max_depth=MAX_DEPTH, max_features=MAX_FEATURES,
                max_samples=None, tile_px=192):
    """Random Forest at 30 m for phase1-segmentation D3: one example per labeled 30 m cell, the mean
    of its 3x3 block. max_samples is the bootstrap size of each tree, set by the pilot's curve (D4)."""
    X, y = dl.block_features(rows, tile_px)
    rf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, max_features=max_features,
                                max_samples=max_samples, random_state=seed, n_jobs=-1)
    rf.fit(X, y)
    return rf


def predict_counts_tiles(rf, rows, tile_px=192):
    """classifier_report.dice_counts per tile, (N, 3, 3), scored on the same 30 m cells as the U-Net."""
    counts = []
    for row in rows:
        image, label = dl.load_tile(row["path"], tile_px)
        cells = dl.tile_to_float(image).reshape(tile_px // 3, 3, tile_px // 3, 3, 26).mean(axis=(1, 3))
        pred = rf.predict(cells.reshape(-1, 26)).reshape(label.shape)
        counts.append(classifier_report.dice_counts(pred, label))
    return np.stack(counts)
