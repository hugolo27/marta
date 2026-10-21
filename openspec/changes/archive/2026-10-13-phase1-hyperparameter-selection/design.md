## Context

See proposal.md for motivation. Relevant current state:

- Split by ~2 km spatial blocks (`scripts/dataset_loader.py`): train 1,673 patches, val 361, test 359, balanced across bosque/pasto/cultivo.
- RF: `n_estimators=400`, `max_depth=None`, scikit-learn defaults otherwise, on the central pixel's 12 bands + NDVI.
- CNN (`SmallCNN`): `lr=0.001`, `dropout=0.4`, `batch_size=32`, Adam, `MAX_EPOCHS=100`, early stopping with patience 10 on validation loss, best-loss weights restored. One seed-42 run on val stops at epoch 15 (best at 5) and takes ~25 s.
- Main comparison: 5 seeds, CNN 0.843 ± 0.012 vs. RF 0.811 ± 0.004 test macro-F1 (`ddof=0`). Recomputed with `ddof=1` from the stored per-seed scores: pooled std 0.010 against a difference of 0.032, so the CNN still wins.
- Held-out regions with `ddof=1`, from the stored per-seed scores: Filadelfia RF wins (0.829 vs. 0.696), Bahía Negra tie (0.611 vs. 0.611), Pozo Colorado CNN wins (0.727 vs. 0.661). Same outcomes as with `ddof=0`.

## Goals / Non-Goals

**Goals:**
- Hyperparameters chosen on validation only, with a rule fixed before scoring.
- Test reported once, with the final configurations.
- Every standard deviation across seeds is the sample one (`ddof=1`).

**Non-Goals:** see proposal.md.

## Decisions

### D1. Grids
- **RF** (18 configurations): `n_estimators` {300, 400, 500} × `max_depth` {None, 10, 20} × `max_features` {"sqrt", 0.5}. `max_features` is added because it usually matters more for RF than the tree count, and RF is cheap.
- **CNN** (36 configurations): `lr` {0.0001, 0.0003, 0.001, 0.01} × `dropout` {0.3, 0.4, 0.5} × `batch_size` {16, 32, 64}. Full grid rather than one parameter at a time, so interactions (learning rate with batch size) are covered.
- 5 seeds per configuration, the same seeds as the main comparison: 42, 1, 7, 123, 2026.
- The grid values are the literature ranges already documented in `METODOLOGIA_PIPELINE.md`, plus `lr = 0.0003` to fill the gap between the two lowest values. They were fixed before this change and not narrowed using the old test-split sweep.

### D2. Selection rule (pre-registered)
- Score: mean validation macro-F1 over the 5 seeds; spread: standard deviation with `ddof=1`.
- Best configuration: highest mean.
- The current configuration is kept unless the best one beats it by more than the pooled standard deviation of the two, `sqrt((s_best² + s_current²) / 2)`. This is the same criterion the project already uses to decide RF vs. CNN: a change has to beat seed noise to count. Ties in the best mean are broken by the configuration closest to the current one, then by lower training cost.
- Applied separately to RF and CNN.
- The rule is written in `data/study_area/hyperparameter_selection/README.md` above a `## Results` heading. Its SHA-256 is logged to an MLflow `preregistration` run before any configuration is scored, and the scoring step refuses to run if that text changed, as in `26_score_change_configs.py`.

### D3. Early stopping
- Every CNN run logs `best_epoch` (lowest validation loss) and `stop_epoch`.
- A configuration counts as truncated if any of its runs reaches `max_epochs` without early stopping. Truncated configurations are re-run with `max_epochs = 300` before selection, and only the re-run counts.
- The selected configuration's epochs are reported in the results so the reader can see that it was not truncated.

### D4. Test once
- `11_compare_classifiers.py` re-runs RF and CNN with the selected configurations, 5 seeds, `ddof=1`, same "difference greater than the pooled standard deviation" criterion. This is the only time the new configurations touch the test split.
- `holdout_eval.py` switches to `ddof=1`. If neither configuration changes, the held-out summaries are recomputed from the stored per-seed scores (no retraining, no GEE extraction). If either changes, the three held-out evaluations are re-run.

### D5. Cascade if the CNN configuration changes
If D2 keeps the current CNN configuration, nothing downstream changes. If not, in this order:
1. Retrain and save the operational checkpoint (seed 42) with the selected configuration.
2. Re-run the AOI and development-area classification (`18_classify_aoi_temporal.py`).
3. Re-apply the pre-registered change-map selection (`26_score_change_configs.py score`) without changing its rule, and rebuild the change map (`19_temporal_change_map.py`).
4. Re-run Grad-CAM (`21_grad_cam.py`, `22_explain_transition.py`).
5. Redraw the AOI reference sample (`27_draw_reference_sample.py`). No point has been interpreted yet. The held-out samples (`29_draw_heldout_samples.py`) are stratified by WorldCover, not by the model, and are not redrawn.

An RF-only change updates the RF numbers and nothing downstream, because RF is not the operational classifier.

### D6. Previous sweep
`hyperparameter_sweep_results.json` is renamed `hyperparameter_sweep_test_split.json` and kept as a record. Every place that cites it says it was scored on the test split and was not used for any decision. `24_hyperparameter_sweep.py` is replaced, not kept beside the new script, so there is one way to run the selection.

## Risks / Trade-offs

- **Validation is small (361 patches).** Differences of a few thousandths of macro-F1 are within noise; the pooled-std rule in D2 is there for that reason.
- **Validation now steers both early stopping and the configuration.** Some optimism on validation is expected; test, reported once, is the unbiased figure.
- **The keep-current rule favours the status quo.** It is deliberate: a change of the operational CNN forces the D5 cascade, so it has to beat noise to justify it.
