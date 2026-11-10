## 1. Pre-registration

- [x] 1.1 Write `data/study_area/patch_size_selection/README.md` with the 3x3 model (design D1), the grid and tie-breaks (D2) and the patch-size rule (D3) above a `## Results` heading, and log its SHA-256 to an MLflow `preregistration` run before any 3x3 configuration is scored, verified by the hash in `preregistration.json` and in MLflow: sha256 4ae99c43..., logged 2026-10-19

## 2. Code

- [x] 2.1 `10_train_cnn.py`: `patch_px` in `SmallCNN`, `train()`, `save_checkpoint()` and `load_checkpoint()` (D1), default 33, verified by a seed-42 33x33 run reproducing its stored validation macro-F1 and a 3x3 forward pass on a 33x33 batch: 0.8445 reproduced exactly; 3x3 and 33x33 have the same 96,963 parameters
- [x] 2.2 `31_patch_size_selection.py` (`preregister` and `score` steps), reusing the grid, scoring and truncation helpers of `24_hyperparameter_selection.py`, verified by a reduced dry run (one configuration, one seed) that writes a well-formed results file: dry run on a temporary MLflow store, 11 s per 3x3 run

## 3. Selection and test

- [x] 3.1 Run `31_patch_size_selection.py score`, verified by 36 3x3 configurations scored with 5 seeds each, no truncated configuration left un-rerun, and the D3 outcome recorded: 36 configurations, none truncated; 3x3 selected `lr` 0.0003, `dropout` 0.5, `batch_size` 32, val 0.837 ± 0.010 vs. 33x33 0.844 ± 0.008, difference 0.007 < pooled std 0.009, so 3x3 is operational under the rule. Patch files cached in memory after 3 configurations (`dataset_loader.load_patch`), seed-42 re-run identical
- [x] 3.2 Report both selected CNNs on test, 5 seeds each (D4), in the results file: 3x3 0.810 ± 0.011, 33x33 0.860 ± 0.008 (RF 0.811 ± 0.005)
- [ ] 3.3 (superseded by `phase1-dataset-v2`, which rebuilds the dataset and re-runs the input-size comparison on it) If 3x3 is operational, set `patch_px=3` and its configuration as the defaults in `10_train_cnn.py`, run `11_compare_classifiers.py` once and `12_plot_comparison.py`
- [ ] 3.4 (superseded by `phase1-dataset-v2`) If 3x3 is operational, copy the current held-out results into `patch_size_selection/` and re-run `14`, `16` and `17`, verified by `winner` fields with `ddof=1`

## 4. Cascade (only if 3x3 becomes operational, design D5)

- [x] 4.1 `21_grad_cam.py` draws a 3x3 CAM over the central block only, verified on one patch per class: verified on random patches, the 3x3 CAM and the guided saliency are non-zero only on pixels 15-17
- [ ] 4.2 (superseded by `phase1-dataset-v2`) Retrain and save the seed-42 checkpoint, re-run `18_classify_aoi_temporal.py` (AOI and development area, 2019-2023), `26_score_change_configs.py score`, `19_temporal_change_map.py`, `21_grad_cam.py`, `22_explain_transition.py` and `27_draw_reference_sample.py`, verified by updated change statistics and a new sample with the same strata design

## 5. Documentation

- [ ] 5.1 Update `docs/PHASE1_SUMMARY.md`, `docs/METODOLOGIA_PIPELINE.md` and thesis chapters 2 and 3 with the patch-size comparison, the rule and its outcome
- [ ] 5.2 Run `openspec validate phase1-patch-size --strict` and compile the thesis
