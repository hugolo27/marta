## Why

The tutor's review of PR #1 found that the hyperparameter sensitivity sweep (`scripts/24_hyperparameter_sweep.py`) scored every configuration on the test split: `evaluate()` defaults to `split="test"` and the sweep never overrides it. Nothing was selected with it, so the reported test results are not contaminated, but deciding `lr = 0.0001` from that sweep would be a choice made on test. The review also found:

- The sweep used 3 seeds while the main comparison uses 5, so its baseline (0.843 ± 0.016) and the main result (0.843 ± 0.012) are different runs. Standard deviations use `np.std` with `ddof=0`, which underestimates the spread with n = 3 (about 22%). The same `ddof=0` is used in the main comparison (`11_compare_classifiers.py`) and the held-out comparisons (`holdout_eval.py`).
- The epoch at which early stopping fires is not recorded, so a slow learning rate could be truncated by `MAX_EPOCHS = 100` without anyone noticing.
- The documentation says the CNN input has "13 bands". It has 13 channels: the 12 Sentinel-2 L2A bands (B10 is not in L2A) plus NDVI.
- "The literature-standard choice holds up empirically in 4 of 5 parameters" claims more than the data shows.

The tutor also asked why there is no hyperparameter selection. The values were fixed once from the literature to avoid tuning on a small dataset and to keep the RF vs. CNN comparison even-handed. Selecting on the validation split, with the same budget for both models and the test split reported once, keeps both goals and removes the open question.

## What Changes

- **Selection on the validation split.** A grid for each model (RF and CNN), 5 seeds per configuration, scored by mean validation macro-F1 with `ddof=1` standard deviations. Selection rule pre-registered before the first scoring run (design D2).
- **Early stopping recorded.** Best epoch and stop epoch logged for every CNN run; truncated configurations re-run with a higher epoch cap (design D3).
- **Test reported once.** The RF vs. CNN comparison (`11_compare_classifiers.py`) re-run with the selected configurations and `ddof=1`, same pre-registered criterion. Held-out comparisons recomputed with `ddof=1`.
- **Previous sweep kept and labeled.** Its JSON is renamed to say it was scored on test, and every document that cites it says so. It is not used for any decision.
- **Downstream cascade only if the CNN configuration changes** (design D5): retrain the operational checkpoint, re-run the AOI classification, the change map with its pre-registered post-processing rule, Grad-CAM, and redraw the AOI reference sample. No reference point has been interpreted yet, so nothing interpreted is lost.
- **Documentation fixes**: "12 bands + NDVI" everywhere the CNN input is described; "no evidence that the tested alternatives are better" instead of "holds up in 4 of 5".

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `land-cover-classifier`: adds hyperparameter selection on the validation split, sample standard deviations across seeds, and recorded early-stopping epochs to the baseline vs. candidate evaluation.

## Non-goals

- Changing the model families, the architecture, the input features or the train/val/test split.
- Semantic segmentation. The tutor's segmentation suggestion is a separate change.
- Any use of the test split, the held-out regions or the interpreted reference sample to choose a configuration.

## Impact

- **Scripts:** `24_hyperparameter_sweep.py` replaced by `24_hyperparameter_selection.py`; `09_train_random_forest.py` and `10_train_cnn.py` take the hyperparameters as arguments and read the selected values; `10_train_cnn.py` takes `max_epochs`; `11_compare_classifiers.py`, `12_plot_comparison.py` and `holdout_eval.py` use `ddof=1`.
- **Data:** `data/study_area/hyperparameter_selection/` (pre-registered README, preregistration hash, results). `hyperparameter_sweep_results.json` renamed to `hyperparameter_sweep_test_split.json`.
- **MLflow:** experiment `phase1-hyperparameter-selection` (preregistration run, one run per configuration and seed).
- **Compute:** about 180 CNN trainings at ~25-60 s each, plus RF, roughly 2 hours on the local machine.
- **Docs:** `docs/PHASE1_SUMMARY.md`, `docs/METODOLOGIA_PIPELINE.md`, `docs/FOUNDATION.md`, `docs/FOUNDATION.es.md` (band count only), thesis chapters 2 and 3, and the `land-cover-classifier` and `training-dataset` specs where they say "13 bands".
- **Blocks** the interpretation of the AOI reference sample (`phase1-accuracy-assessment` 4.x) until this change says whether the operational CNN changes.
