"""Shared evaluation/report formatting for phase1-classifier's baseline and candidate, so RF
and CNN produce directly comparable output in the same format (design.md: fair comparison)."""

from sklearn.metrics import classification_report, confusion_matrix, jaccard_score

from dataset_loader import CLASS_NAMES

LABELS = list(range(len(CLASS_NAMES)))


def evaluate_predictions(y_true, y_pred):
    # Explicit labels=, not inferred from unique(y_true, y_pred): a class entirely absent from a
    # given split (e.g. a small held-out sample) would otherwise shrink the report/matrix/IoU
    # instead of reporting 0 support for it, misaligning them against CLASS_NAMES's fixed order
    # and crashing classification_report's target_names length check (code review 2026-09-11).
    report = classification_report(y_true, y_pred, labels=LABELS, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=LABELS)
    iou = jaccard_score(y_true, y_pred, labels=LABELS, average=None, zero_division=0)
    return {"report": report, "confusion_matrix": cm, "iou_per_class": iou}


def print_evaluation(results, model_name):
    print(f"\n{model_name} confusion matrix (rows=true, cols=pred), order {CLASS_NAMES}:")
    print(results["confusion_matrix"])
    print(f"{model_name} per-class IoU:", dict(zip(CLASS_NAMES, results["iou_per_class"].round(3))))
    print(f"{model_name} macro F1: {results['report']['macro avg']['f1-score']:.3f}")
    print(f"{model_name} accuracy: {results['report']['accuracy']:.3f}")
