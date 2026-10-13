# Hyperparameter selection: pre-registration and results

Change: `openspec/changes/phase1-hyperparameter-selection/`. This file fixes the grids and the
selection rule **before** any configuration is scored. Its SHA-256 is logged to MLflow
(experiment `phase1-hyperparameter-selection`, run `preregistration`) before the first scoring
run, and `scripts/24_hyperparameter_selection.py` refuses to run if the pre-registered part
(everything above the "Results" heading) no longer matches that hash.

The earlier one-at-a-time sweep (`../hyperparameter_sweep_test_split.json`) was scored on the test
split. It is kept as a record and is not used for any decision here, including the choice of grid
values.

## Data

Fixed train/val/test split by ~2 km spatial blocks (`scripts/dataset_loader.py`). Every
configuration is trained on train and scored on **val only**. Test, the held-out regions and the
interpreted reference sample are not used.

## Grids

- **Random Forest** (18 configurations): `n_estimators` {300, 400, 500} × `max_depth` {None, 10,
  20} × `max_features` {"sqrt", 0.5}. Current: 400, None, "sqrt".
- **CNN** (36 configurations): `lr` {0.0001, 0.0003, 0.001, 0.01} × `dropout` {0.3, 0.4, 0.5} ×
  `batch_size` {16, 32, 64}. Current: 0.001, 0.4, 32. Everything else as in
  `scripts/10_train_cnn.py` (Adam, patience 10 on validation loss, best-loss weights restored).
- Seeds per configuration: 42, 1, 7, 123, 2026.

## Metric

Macro-F1 on val. Per configuration: the mean over the 5 seeds and the sample standard deviation
(`ddof=1`).

## Truncation

Every CNN run records the best epoch (lowest validation loss) and the stop epoch. If any run of a
configuration stops at `max_epochs` = 100, the whole configuration is re-run with `max_epochs` =
300, and only the re-run counts.

## Selection rule (each model separately)

1. Best = the configuration with the highest mean. Ties are broken by fewest parameters different
   from the current configuration, then by lower training cost (RF: fewer trees; CNN: lower mean
   stop epoch).
2. Pooled std = sqrt((s_best² + s_current²) / 2).
3. If mean_best − mean_current > pooled std, the best configuration is selected. Otherwise the
   current configuration is kept. This is the criterion the project already uses for RF vs. CNN.
4. The selected configurations are then evaluated on test exactly once
   (`scripts/11_compare_classifiers.py`, 5 seeds, `ddof=1`).

## Results

Run 2026-10-12 (`results.json`, MLflow experiment `phase1-hyperparameter-selection`). The
pre-registration hash was checked before scoring. No CNN run reached 100 epochs, so no
configuration was re-run.

| Model | Best configuration | Best (val) | Current (val) | Best − current | Pooled std | Selected |
|---|---|---|---|---|---|---|
| RF | 300 trees, depth 10, `max_features` 0.5 | 0.832 ± 0.007 | 0.827 ± 0.003 | +0.005 | 0.006 | current (400, none, "sqrt") |
| CNN | `lr` 0.0003, `dropout` 0.5, `batch_size` 16 | 0.844 ± 0.008 | 0.826 ± 0.016 | +0.018 | 0.013 | best |

Stop epochs of the selected CNN: 39, 24, 32, 27, 24 (best epochs 29, 14, 22, 17, 14).

Test, evaluated once with the selected configurations (`../comparison_results.json`, 5 seeds,
`ddof=1`): RF 0.811 ± 0.005, CNN 0.860 ± 0.008, difference +0.049 against a pooled std of 0.007.
CNN wins. Held-out regions re-run with the selected CNN: Filadelfia RF wins (0.831 vs. 0.706),
Bahía Negra CNN wins narrowly (0.619 vs. 0.611, pooled std 0.003), Pozo Colorado CNN wins (0.727
vs. 0.661).

The CNN changed, so the cascade in design D5 was run: new seed-42 checkpoint (test macro-F1
0.854), AOI and development area reclassified 2019-2023, change-map rule re-applied
(`../change_hardening/README.md`), Grad-CAM regenerated, AOI reference sample redrawn.
