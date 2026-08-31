## Why

`phase1-dataset-build` produces the Sentinel-2/MapBiomas dataset (patches, per-pixel features,
splits) but trains nothing. Nothing downstream (temporal comparison, Grad-CAM, carbon estimation
tied to observed change) can proceed without a trained classifier producing per-date land cover
predictions. This is the next unblocked piece of Fase 1.

## What Changes

- Train a Random Forest baseline on per-pixel spectral features (12 Sentinel-2 bands + NDVI) for
  the 3 target classes (bosque/pasto/cultivo), using the dataset's train split.
- Train a CNN candidate on the 33x33x13 patches from the same dataset, same 3 classes, small
  custom architecture (not a large pretrained backbone).
- Evaluate both on the held-out test split: accuracy, IoU/Dice per class, confusion matrix, and
  a direct CNN-vs-RF comparison — report the result whichever way it goes, a tie or an RF win is a
  valid finding, not a failure.
- Run the cross-region generalization check (designed but not executed in `phase1-dataset-build`):
  evaluate the winning classifier on the Filadelfia held-out sub-region, and cross-check its
  cultivo/bosque predictions there against ESA WorldCover.
- Does not include Grad-CAM (depends on a trained CNN, separate change) or producing the final
  change-detection map as a shippable artifact (depends on running the classifier over both 2019
  and 2023 and diffing, which this change enables but doesn't itself package as a deliverable).

## Capabilities

### New Capabilities
- `land-cover-classifier`: trains and evaluates a Random Forest baseline and a CNN candidate for
  per-date land cover classification (bosque/pasto/cultivo), including the cross-region
  generalization and WorldCover cross-checks.

### Modified Capabilities
(none)

## Impact

- New model training code (not yet written, this change is planning only).
- Consumes `phase1-dataset-build`'s dataset output (`data/study_area/dataset/`). Depends on that
  dataset being at real training volume, not the original 90-patch proof-of-mechanism sample —
  the scale-up (200 patches/class/period, 1,200 total) is running in parallel to this proposal and
  is not itself part of this change's scope.
- Produces the trained classifier that Grad-CAM, the temporal-comparison change, and the
  carbon-estimation change will all depend on.
