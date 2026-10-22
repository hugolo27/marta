# Variant selection on the rebuilt dataset: pre-registration and results

Change: `openspec/changes/phase1-dataset-v2/`. This file fixes the dataset design, the grids and
the selection rules **before** the dataset is built and before any variant is scored. Its SHA-256
is logged to MLflow (experiment `phase1-variant-selection`, run `preregistration`), and
`scripts/34_variant_selection.py` refuses to score if the pre-registered part (everything above the
"Results" heading) no longer matches that hash.

## Dataset (built by `scripts/08_assemble_dataset.py`)

- 1,000 points per class (bosque, pasto, cultivo) and year (2019, 2023), stratified on MapBiomas
  Chaco Collection 5 at 30 m, seed 42, over the sampling area with the 3 held-out regions removed.
- Blocks of 6 km (the largest practical range of the semivariograms in
  `../spatial_autocorrelation/`, rounded up), built in kilometers. **All points in a block go to
  the same split, whatever their class**, so the block separates locations, not classes. Splits
  70 / 15 / 15 by block, one assignment for both years. The build stops if any class ends up with
  fewer than 10% of its points in validation or in test.
- Two quality checks: points of different splits closer than 330 m are dropped (the overlap of two
  33x33 windows), and examples with any no-data pixel in either composite are dropped.
- Each example: 33x33 window of Sentinel-2 L2A, dry composite (June 1 - September 30) then wet
  composite (January 1 - April 30 of the same year), 12 bands + NDVI each, 26 channels, float32.
- If more than 10% of the examples are dropped for no-data pixels of the wet composite alone, the
  dry+wet variants are not scored and that is reported.

## Variants

- CNN (`SmallCNN`, unchanged architecture): **A** 3x3 dry (default), **B** 3x3 dry+wet, **C**
  33x33 dry, **D** 33x33 dry+wet. A 3x3 variant crops the central 3x3 block of the window.
- Random Forest (central pixel): **dry** (default), **dry+wet**.

## Amendment 1 (2026-10-19, before the dataset was finished and before any variant was scored)

Every CNN variant normalizes its input per channel: subtract the mean and divide by the standard
deviation of that channel, both computed over every pixel of the **train** split only, and stored
with the model weights. Without it, the bands (values ~70-4,700) dwarf NDVI (-0.3 to 0.9) in the
first layer. Random Forest is unaffected (its splits don't depend on scale) and stays unnormalized.
The first registration of this file (hash `bff90e2f...`, without this section) is kept in
`preregistration_v1.json`.

## Amendment 2 (2026-10-19)

Following the tutor's guidance to work with 3x3 input, the variant rule compares **A** (default)
and **B** only. The 33x33 variants (C, D) had been started; the partial C results (23 of 48
configurations) stay in `results.json` as exploratory. The registration before this amendment is
kept in `preregistration_v2.json`.

## Hyperparameters, per variant, on validation only

- Seeds 42, 1, 7, 123, 2026. Score: mean macro-F1 on val; spread: sample standard deviation
  (`ddof=1`).
- CNN grid: `lr` {0.0001, 0.0003, 0.001} × `dropout` {0.3, 0.4, 0.5, 0.6} × `batch_size` {8, 16,
  32, 64} (48 configurations). `lr` 0.01 is left out because it was the worst value in both
  previous grids. Truncation: a configuration with any run stopping at 100 epochs is re-run at 300.
- Edge rule (once, not recursive): if the selected `dropout` is 0.6, or the selected `batch_size`
  is 8 or 64, that axis is extended by one step (0.7; 4 or 128) with the other two values fixed at
  the selection, and the selection is redone over all scored configurations.
- RF grid: `n_estimators` {300, 400, 500} × `max_depth` {None, 10, 20} × `max_features` {"sqrt",
  0.5}.
- Selected configuration per variant: the highest mean. Ties: CNN lower mean stop epoch, then
  larger batch; RF fewer trees.

## Variant rule

1. Candidate: the variant with the highest mean validation macro-F1 among the CNN variants (A-D),
   and separately among the RF variants.
2. Pooled std = sqrt((s_default² + s_candidate²) / 2).
3. The candidate replaces the default (A for the CNN, dry for RF) only if mean_candidate −
   mean_default > pooled std. Otherwise the default stays.
4. Every selected variant is then evaluated on test once (5 seeds). Those numbers are reported and
   not used for any choice. The operational CNN and RF go through `11_compare_classifiers.py`, the
   held-out regions and the downstream cascade (design D5).

## Results

Run 2026-10-19 (`results.json`, MLflow `phase1-variant-selection`). Validation macro-F1, 5 seeds,
selected configuration per variant:

| Variant | Configuration | Val | Test |
|---|---|---|---|
| RF dry | 300 trees, depth 10, `max_features` "sqrt" | 0.827 +/- 0.002 | 0.799 +/- 0.004 |
| RF dry+wet | 500 trees, no depth limit, `max_features` "sqrt" | 0.845 +/- 0.002 | 0.841 +/- 0.003 |
| CNN A, 3x3 dry | `lr` 0.0003, `dropout` 0.3, `batch_size` 8 | 0.843 +/- 0.003 | 0.835 +/- 0.007 |
| CNN B, 3x3 dry+wet | `lr` 0.0001, `dropout` 0.3, `batch_size` 32 | 0.869 +/- 0.007 | 0.865 +/- 0.003 |

- Edge rule: A's `batch_size` 8 sat on the grid edge; 4 scored 0.836, so 8 stays. B's selection
  is inside the grid on every extendable axis. No configuration was truncated at 100 epochs.
- Variant rule: B beats A by 0.027 (pooled std 0.005) and RF dry+wet beats RF dry by 0.018 (pooled
  std 0.002). **Operational: CNN B (3x3 dry+wet) and RF dry+wet.** Both are now the defaults of
  `10_train_cnn.py` and `09_train_random_forest.py`.
- Test was run once, after the decision, and used for nothing.
