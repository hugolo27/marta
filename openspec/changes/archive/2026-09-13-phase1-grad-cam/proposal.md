## Why

`land-cover-classifier`'s operational-classifier decision picked the CNN specifically because it uniquely supports per-prediction interpretability (`Requirement: Operational classifier selection`) — but that interpretability doesn't exist yet. Right now every CNN prediction, and every transition in the `temporal-change-detection` change map, is a number an auditor has to trust with no visual evidence for *why* the model called it. This is also the last piece the tutor's methodology puts in Phase 1 (dataset, CNN, RF baseline, temporal comparison, Grad-CAM, study area) — everything else in that list is already archived.

## What Changes

- Produce a Grad-CAM activation heatmap for any single CNN prediction, given a 33x33x13 patch, showing which spatial regions of the patch drove the predicted class.
- Apply this to a same-date classification (any patch from the existing dataset, or an arbitrary pixel in the dense per-date AOI rasters from `temporal-change-detection`).
- Apply this to pixels flagged as a transition in the 2019/2023 change map: produce Grad-CAM for both dates' predictions at that pixel, so an auditor sees the evidence behind *both* halves of a claimed transition, not just that the diff changed.
- Render heatmaps overlaid on the true-color patch (not a bare heatmap), matching the project's existing true-color visualization convention (`scripts/13_visualize_classification_map.py`, `05_visualize_mapbiomas_labels.py`).
- Sharpen the raw Grad-CAM heatmap with Guided Grad-CAM (combining it with guided backpropagation's pixel-level detail) before rendering, rather than presenting the raw 8x8-native heatmap upsampled with no further refinement.
- Explicitly scoped to the CNN only — Random Forest has no gradients or spatial activation maps to hook Grad-CAM onto, structurally, not a missing feature (`land-cover-classifier`'s own operational-classifier rationale already states this).

## Capabilities

### New Capabilities
- `grad-cam-interpretability`: produces and renders a Grad-CAM activation heatmap for a given CNN prediction on a single patch, for both standalone same-date predictions and the two predictions behind a detected temporal transition.

### Modified Capabilities
(none — this consumes the CNN trained in `land-cover-classifier` and the change map produced by `temporal-change-detection` as-is, without changing either's requirements)

## Impact

- New script(s) under `scripts/` for Grad-CAM computation (hooking into `SmallCNN`'s last conv block) and for rendering heatmap-over-true-color visualizations.
- Consumes the persisted CNN checkpoint from `phase1-temporal-comparison` (`scripts/10_train_cnn.py`'s `save_checkpoint`/`load_checkpoint`) rather than retraining.
- Consumes `temporal-change-detection`'s per-date classification rasters and change map to select transition pixels worth explaining.
- Closes out Phase 1 per the tutor's 6-phase methodology — Fase 2 (carbon estimation) is the next phase after this.
