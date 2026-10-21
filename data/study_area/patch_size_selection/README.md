# Patch size selection: pre-registration and results

Change: `openspec/changes/phase1-patch-size/`. This file fixes the 3x3 model, its grid and the
patch-size rule **before** any 3x3 configuration is scored. Its SHA-256 is logged to MLflow
(experiment `phase1-patch-size-selection`, run `preregistration`) before the first scoring run, and
`scripts/31_patch_size_selection.py` refuses to run if the pre-registered part (everything above
the "Results" heading) no longer matches that hash.

## Question

The tutor's design was a 3x3 matrix of Sentinel-2 pixels (10 m) per MapBiomas pixel (30 m). The
current CNN sees a 33x33 window (~330 m) centered on that block. Which input size goes forward?

## Models

- **33x33 CNN**: `SmallCNN` as selected in `phase1-hyperparameter-selection` (`lr` 0.0003,
  `dropout` 0.5, `batch_size` 16). Not re-scored: its 5 per-seed validation scores are taken from
  `../hyperparameter_selection/results.json`.
- **3x3 CNN**: the same `SmallCNN` with `patch_px=3`. It crops the central 3x3 block of each
  existing 33x33 patch and skips the two max-pooling layers. Same conv stack, same parameter count,
  same augmentation, same data and split.

## Grid for the 3x3 CNN

`lr` {0.0001, 0.0003, 0.001, 0.01} × `dropout` {0.3, 0.4, 0.5} × `batch_size` {16, 32, 64}
(36 configurations), seeds 42, 1, 7, 123, 2026, scored on **val only**: mean macro-F1 and sample
standard deviation (`ddof=1`). If any run of a configuration stops at `max_epochs` = 100, the whole
configuration is re-run with `max_epochs` = 300 and only the re-run counts.

Selected 3x3 configuration: the highest mean. Ties go to the configuration with fewest parameters
different from the 33x33 one, then to the lower mean stop epoch.

## Patch-size rule

1. 3x3 is the default, because it is the tutor's design.
2. Pooled std = sqrt((s_33² + s_3²) / 2), from the 5 val scores of each selected configuration.
3. If mean_33 − mean_3 > pooled std, the 33x33 CNN stays operational. Otherwise the 3x3 CNN
   becomes operational.
4. Both selected CNNs are then evaluated on test once (5 seeds each). Those numbers are reported
   and not used for any choice. The operational CNN goes through `scripts/11_compare_classifiers.py`
   against Random Forest and, if it changed, through the held-out regions and the downstream
   cascade (design D4 and D5).

## Results

Run 2026-10-19 (`results.json`, MLflow experiment `phase1-patch-size-selection`). The
pre-registration hash was checked before scoring. No 3x3 run reached 100 epochs. The run was
interrupted once after 3 configurations to cache the patch files in memory
(`dataset_loader.load_patch`); a seed-42 re-run reproduced the stored score exactly, and the
remaining configurations resumed from `results.json`.

| CNN | Selected configuration | Val macro-F1 (5 seeds) |
|---|---|---|
| 3x3 | `lr` 0.0003, `dropout` 0.5, `batch_size` 32 | 0.837 ± 0.010 |
| 33x33 | `lr` 0.0003, `dropout` 0.5, `batch_size` 16 | 0.844 ± 0.008 |

33x33 − 3x3 = +0.007 against a pooled std of 0.009. Under the rule, the 3x3 CNN becomes
operational.

Test, reported once and not used for the choice: 3x3 0.810 ± 0.011, 33x33 0.860 ± 0.008. For
reference, Random Forest on test is 0.811 ± 0.005 (`../comparison_results.json`).
