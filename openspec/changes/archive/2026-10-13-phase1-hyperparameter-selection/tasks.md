## 1. Pre-registration

- [x] 1.1 Write `data/study_area/hyperparameter_selection/README.md` with the grids (design D1), the selection rule (D2) and the truncation rule (D3) above a `## Results` heading, and log its SHA-256 to an MLflow `preregistration` run before any configuration is scored, verified by the hash in `preregistration.json` and in MLflow
- [x] 1.2 Rename `hyperparameter_sweep_results.json` to `hyperparameter_sweep_test_split.json` (design D6), verified by no remaining reference to the old name outside archived changes

## 2. Code

- [x] 2.1 `09_train_random_forest.py` and `10_train_cnn.py` take their hyperparameters (and `max_epochs` for the CNN) as arguments with the current values as defaults, verified by a default seed-42 run giving the same validation macro-F1 as before the change
- [x] 2.2 Replace `24_hyperparameter_sweep.py` with `24_hyperparameter_selection.py` (`preregister` and `score` steps): grids from D1, 5 seeds, validation split only, `ddof=1`, best and stop epoch per CNN run, truncation re-run (D3), selection rule (D2), results JSON and MLflow runs, verified by a reduced dry run (one configuration per model, one seed) that writes a well-formed results file
- [x] 2.3 Switch `11_compare_classifiers.py`, `12_plot_comparison.py` and `holdout_eval.py` to `ddof=1`, verified by recomputing the stored comparison from its per-seed scores (pooled std 0.010, CNN wins)

## 3. Selection and test

- [x] 3.1 Run `24_hyperparameter_selection.py score`, verified by 18 RF and 36 CNN configurations scored with 5 seeds each, no truncated configuration left un-rerun, and one selected configuration per model
- [x] 3.2 Set the selected configurations as the defaults in `09_train_random_forest.py` and `10_train_cnn.py`
- [x] 3.3 Run `11_compare_classifiers.py` once with the selected configurations and `12_plot_comparison.py`, verified by `comparison_results.json` with `ddof=1` spreads and the criterion outcome
- [x] 3.4 Update the held-out comparisons (design D4): recompute from stored per-seed scores if neither configuration changed, otherwise re-run `14`, `16` and `17`, verified by `winner` fields computed with `ddof=1`

## 4. Cascade (only if the CNN configuration changed, design D5)

- [x] 4.1 Retrain and save the seed-42 checkpoint, re-run `18_classify_aoi_temporal.py`, `26_score_change_configs.py score`, `19_temporal_change_map.py`, `21_grad_cam.py`, `22_explain_transition.py` and `27_draw_reference_sample.py`, verified by updated change statistics and a new sample with the same strata sizes

## 5. Documentation

- [x] 5.1 Unify the description of the CNN input to "12 Sentinel-2 L2A bands + NDVI" in `docs/FOUNDATION.md`, `docs/FOUNDATION.es.md`, `docs/PHASE1_SUMMARY.md`, `docs/METODOLOGIA_PIPELINE.md`, thesis chapter 2 and the `land-cover-classifier` and `training-dataset` specs (the `33x33x13` tensor shape stays, with its channels spelled out), verified by grep
- [x] 5.2 Rewrite the sweep paragraphs in `docs/PHASE1_SUMMARY.md`, `docs/METODOLOGIA_PIPELINE.md` and thesis chapters 2 and 3: the old sweep was scored on test and not used for decisions; the selection result on validation; the test result reported once. The "holds up in 4 of 5" claim is removed, not reworded, because the selection replaces it
- [x] 5.3 Run `openspec validate phase1-hyperparameter-selection --strict` and compile the thesis
