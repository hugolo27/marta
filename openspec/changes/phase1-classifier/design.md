## Context

See `proposal.md` - Why. This design covers how the Random Forest baseline and CNN candidate get trained and compared, and how the two evaluation passes (test split, held-out generalization) fit together. It assumes `phase1-dataset-build`'s dataset exists at real training volume under `data/study_area/dataset/<split>/<class>/`, with a manifest recording path/period/class/split/coordinates per example.

## Goals / Non-Goals

**Goals:**
- Produce a working Random Forest baseline and CNN candidate, evaluated on the same test split with the same metrics, so the comparison is fair.
- Keep the evaluation honest: report whichever model wins, and treat a Random Forest win as informative, not as a signal to keep tuning the CNN until it wins.
- Execute the generalization and WorldCover cross-checks designed in `phase1-dataset-build`, which were deferred because they need a trained classifier to run against.

**Non-Goals:**
- No Grad-CAM in this change. It needs a trained CNN to attach to, and is its own change with its own evaluation criteria (heatmap coherence), not a metric this change reports.
- No production-grade hyperparameter search. A reasonable, documented configuration for each model is enough to make the comparison meaningful; exhaustive tuning is not required to answer "does the added complexity help."
- No packaging of the final bosque-to-non-bosque change map as a deliverable. This change classifies each date; diffing two classified dates into a change map is downstream work.

## Decisions

**Random Forest trains on per-pixel features, not on flattened patches.** RF doesn't benefit from the 33x33 spatial window the CNN uses; feeding it flattened patches would just be a slower, higher-dimensional version of the same per-pixel decision, not a fairer comparison. RF gets each pixel's own 13 channel values (12 Sentinel-2 bands + NDVI), extracted from the dataset's patch centers, keeping training on the same underlying example set as the CNN without needing a separate data pull.

**CNN architecture stays small and custom, not a pretrained backbone.** Consistent with the decision already recorded in `docs/PIPELINE.md`: a large pretrained backbone would make Grad-CAM's heatmaps harder to interpret and would make the "does the CNN's complexity earn its keep" question less honest, since most of that complexity wouldn't have been learned from this project's own data.

**"Meaningful" outperformance is defined before training, not after seeing results.** To avoid post-hoc rationalizing a small CNN edge as a win, the design fixes the evaluation criterion in advance: run both models across 5 random seeds, score macro-averaged F1 on the test split for each run, and call the CNN a genuine winner only if its mean macro-F1 exceeds Random Forest's mean by more than one pooled standard deviation across those 5 runs. Full hyperparameter values (batch size 32, Adam at lr=0.001, up to 100 epochs with early stopping at 10 epochs without validation improvement, dropout 0.3-0.5, rotation/flip augmentation only, RF at 300-500 trees with unbounded depth) are documented in `docs/PIPELINE.md`, "Training hyperparameters" — not repeated here, this section is the decision rule, that doc is the reference values.

## Risks / Trade-offs

- **[Risk] The dataset's real training volume (200/class/period, 1,200 total) is still small for a CNN, especially split three ways (train/val/test) across 3 classes.** → Mitigation: this is exactly why the evaluation criterion above requires a margin beyond single-run noise, and why the Random Forest baseline matters: if the CNN can't beat RF at this volume, that's itself a valid, reportable data point about how much volume this task needs.
- **[Risk] The Filadelfia generalization check could show the classifier performs meaningfully worse there than on the case-study AOI's own test split.** → Mitigation: this is the outcome the check exists to catch. Report it as-is; it would motivate widening the training sample geographically in a future change, not something to hide or explain away here.
- **[Trade-off] Fixing the CNN architecture as "small and custom" trades away some ceiling on CNN performance for interpretability and honesty of the comparison.** Accepted deliberately, same rationale as `docs/PIPELINE.md`'s existing note on this.
