## 1. Spatial autocorrelation and pre-registration

- [x] 1.1 `33_spatial_autocorrelation.py`: 20 km windows, both years, NDVI and class semivariograms, exponential fits, practical ranges, block side by design D1, results and plot in `data/study_area/spatial_autocorrelation/` and MLflow, verified by four fitted ranges and the derived block side: run 2026-10-19, 18,000 points; NDVI 3.9 km (2019) / 4.8 km (2023), class 5.2 / 4.4 km; block side 6 km. A first 10 km-window pass overestimated the class range (curves still rising at the window edge) and is not used
- [x] 1.2 Write `data/study_area/variant_selection/README.md` (design D2-D4) above `## Results` and log its hash to MLflow before any variant is scored: sha256 bff90e2f..., 2026-10-19 03:04 UTC, before the dataset was built

## 2. Dataset

- [x] 2.1 Check the wet composites' no-data fraction over the sampling area for 2019 and 2023 (D3), verified by both fractions recorded: 1,670 (2019) and 1,688 (2023) January-April scenes, no area without data at 500 m. Coarse; the per-example no-data check in 2.2 is the binding one
- [x] 2.2 `08_assemble_dataset.py`: block side in km from 1.1, 1,000 points per class and year, dry and wet composites, 33x33x26 float32, quality checks over both composites; current dataset moved to `dataset_v1_backup/`, verified by split counts per class, buffer and no-data drop counts, and no point inside a held-out region: 5,993 patches (train 4,157, val 921, test 915), 2 points dropped by the buffer, 5 by dry no-data, 0 by wet no-data (`wet_gap_share` 0.0), 289-325 points per class in val and test
- [x] 2.3 `dataset_loader.py`, `09_train_random_forest.py`, `10_train_cnn.py`: `season` ("dry" or "drywet") selecting 13 or 26 channels, verified by a forward pass and one RF fit per season: on the v1 dataset (13 channels) RF and 3x3 CNN seed-42 val scores reproduce the stored ones exactly

## 3. Selection and test

- [x] 3.1 `34_variant_selection.py` (`preregister`, `score`), reusing the helpers of `24_hyperparameter_selection.py`, verified by the full RF and 3x3 runs completing and resuming from `results.json`
- [x] 3.2 Run the selection: RF grid for both seasons, CNN grid for variants A and B (C and D dropped by Amendment 2, design D4c), edge rule, variant rule, verified by the results file recording every configuration, the edge extensions run and both decisions: operational CNN B (3x3 dry+wet, val 0.869 vs. A 0.843, pooled std 0.005) and RF dry+wet (0.845 vs. 0.827, pooled std 0.002)
- [x] 3.3 Report every variant on test once, set the selected configurations as defaults, run `11_compare_classifiers.py` and `12_plot_comparison.py`: test CNN A 0.835, B 0.865, RF dry 0.799, dry+wet 0.841; comparison RF 0.841 vs. CNN 0.865

## 4. Held-out and cascade

- [x] 4.1 If a selected model uses the wet season, add the wet composite to `14`, `16`, `17`, `18` and `22`: `s2_utils.build_season_composite`, also used by `30`; held-out scripts pull dry+wet and each model keeps its own channels; `18` classifies with windows of the model's input size and drops pixels with a gap in either composite, verified against per-window predictions on a synthetic tile
- [x] 4.2 Re-run the held-out regions, then the cascade of design D5, verified by updated held-out winners, change statistics and a redrawn AOI sample: held-out RF/CNN Filadelfia 0.839/0.824, Bahia Negra 0.621/0.627, Pozo Colorado 0.668/0.710; change rule now selects confidence 0.9 + persistence + MMU, loss 8.1 ha (was 7.6), gain 61.0 ha (was 0.5); new 340-point sample with the same allocation; held-out samples reclassified

## 5. Documentation

- [x] 5.1 Update `docs/PHASE1_SUMMARY.md`, `docs/METODOLOGIA_PIPELINE.md`, thesis chapters 2 and 3, the `training-dataset` and `land-cover-classifier` specs: spec deltas add input normalization and class-agnostic blocks; `20_mapbiomas_cross_check.py` re-run for the transition agreement quoted in the docs
- [x] 5.2 Run `openspec validate phase1-dataset-v2 --strict` and compile the thesis: valid, thesis compiles
