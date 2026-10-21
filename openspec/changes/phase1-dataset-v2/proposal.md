## Why

Three findings from 2026-10-19 make the current dataset the weakest link in the Phase 1 evidence:

- **Validation blocks are smaller than the spatial autocorrelation.** Splits are assigned by ~2 km blocks, a value chosen as "more than 6 times the patch side". A semivariogram over 18,000 points in 60 windows of 20 km across the sampling footprint gives practical ranges of 3.9-4.8 km for NDVI and 4.4-5.2 km for the MapBiomas class (`data/study_area/spatial_autocorrelation/`). The literature asks for blocks at least as large as that range (Roberts et al., 2017; Valavi et al., 2019). With 2 km blocks, test points sit within the autocorrelation range of training points, so the test score (0.860) is likely optimistic.
- **The 3x3 vs. 33x33 comparison was run on a small dataset** (`phase1-patch-size`). The 3x3 crop of a 33x33 window holds the same 9 pixels as a directly extracted 3x3, so a "3x3 dataset" with the same points would give the same result. What can change it is the amount of data: with more examples both input sizes are compared on equal, larger footing. The small validation split (361 patches) was also too noisy to separate them (0.837 vs. 0.844, pooled std 0.009), while test separated them clearly (0.810 vs. 0.860).
- **Two selected hyperparameters sit on the edge of their grid** (`dropout` 0.5, `batch_size` 16), so the optimum may lie outside it.

On top of that, the composite uses only the dry season (June-September). For the reliability the downstream product needs, the wet season (January-April, leaf-on) adds phenology that may separate pasture from cropland. Whether it helps is tested, not assumed.

`phase1-patch-size` recorded that the 3x3 CNN is operational under its pre-registered rule; its downstream cascade is not run, because this change rebuilds the dataset both models are trained on.

## What Changes

- **Block size from the semivariogram.** A versioned analysis (`33_spatial_autocorrelation.py`, 20 km windows) sets the block side by the rule in design D1: 6 km. The 330 m minimum distance between splits stays: it is the physical overlap of 33x33 windows.
- **More examples.** 1,000 points per class and year instead of 400, same stratified sampling, same held-out exclusions, same quality checks.
- **Two seasonal composites per point.** Each example stores the dry (June-September) and wet (January-April) composites of the same year, 26 channels. A model uses either the 13 dry channels or all 26.
- **Wider grid.** CNN: `lr` {0.0001, 0.0003, 0.001} × `dropout` {0.3, 0.4, 0.5, 0.6} × `batch_size` {8, 16, 32, 64}. `lr` 0.01 is dropped because it was the worst value in both previous grids (best configuration and mean). An edge rule extends any axis whose winner lands on its edge.
- **Variant selection, pre-registered** (design D4): CNN variants (3x3 or 33x33, dry or dry+wet; the 33x33 ones were later dropped by design D4c) and two RF variants (dry or dry+wet), hyperparameters selected on validation, then one operational choice per model family by a rule fixed before scoring.
- **Test once, held-out and cascade** with the selected models.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `training-dataset`: block size justified by measured spatial autocorrelation; two seasonal composites per example.
- `land-cover-classifier`: variant selection (input size and season) on the validation split by a pre-registered rule.

## Non-goals

- Semantic segmentation. Still open with the tutor.
- New classes or a new label source.
- Changing the held-out regions, the AOI or the reference-sample design.

## Impact

- **Scripts:** new `33_spatial_autocorrelation.py`; `08_assemble_dataset.py` (block size, two composites, 26-channel patches, `N_PER_CLASS` 1,000); `dataset_loader.py` (channel selection by season); `09_train_random_forest.py` and `10_train_cnn.py` (`season`, `in_channels`); new `34_variant_selection.py`; `14`, `16`, `17`, `18` and `22` if dry+wet is selected (they must pull the wet composite too).
- **Data:** `data/study_area/dataset/` rebuilt (the current one moved to `dataset_v1_backup/`), `data/study_area/spatial_autocorrelation/`, `data/study_area/variant_selection/`.
- **MLflow:** experiments `phase1-spatial-autocorrelation`, `phase1-variant-selection`.
- **Compute:** GEE extraction of ~6,000 points × 2 composites (a few hours); about 1,000 CNN trainings on a ~2.5 times larger dataset, on the order of a day on the local CPU (the GPU is slower for this network: 5.5 s vs. 1.2 s per epoch).
- **Supersedes** the downstream cascade of `phase1-patch-size` and **blocks** the interpretation of the AOI reference sample until the cascade here redraws it.
