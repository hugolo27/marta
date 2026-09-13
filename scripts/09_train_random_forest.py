"""Random Forest baseline, phase1-classifier tasks 2.1-2.2. Per-pixel spectral features
(12 Sentinel-2 bands + NDVI), not the 33x33 patches — RF doesn't benefit from the spatial
window the CNN uses, see design.md."""

from collections import Counter

from sklearn.ensemble import RandomForestClassifier

import classifier_report
import dataset_loader as dl

N_ESTIMATORS = 400


def train(seed=42, verbose=True):
    X_train, y_train = dl.load_pixel_features("train")
    if verbose:
        counts = Counter(y_train)
        print("Training class distribution:", {dl.CLASS_NAMES[k]: v for k, v in sorted(counts.items())})
    rf = RandomForestClassifier(n_estimators=N_ESTIMATORS, max_depth=None, random_state=seed, n_jobs=-1)
    rf.fit(X_train, y_train)
    return rf


def evaluate(rf, split="test"):
    X, y = dl.load_pixel_features(split)
    pred = rf.predict(X)
    return classifier_report.evaluate_predictions(y, pred)


def main():
    rf = train()
    print("Feature importances (bands B1..B12, NDVI):", rf.feature_importances_.round(3))
    results = evaluate(rf)
    classifier_report.print_evaluation(results, "Random Forest")


if __name__ == "__main__":
    main()
