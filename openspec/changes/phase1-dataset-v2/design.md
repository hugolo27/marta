## Context

See proposal.md. Current state: 2,393 patches (400 per class and year, 7 dropped for no-data pixels, 0 by the 330 m buffer), 33x33x13, dry-season composites (June-September), splits by ~2 km blocks per class, held-out regions carved out of the sampling area and masked. Selected configurations: RF 400 trees, unlimited depth, `max_features` "sqrt"; CNN 33x33 `lr` 0.0003, `dropout` 0.5, `batch_size` 16; CNN 3x3 `lr` 0.0003, `dropout` 0.5, `batch_size` 32.

## Goals / Non-Goals

**Goals:**
- Every split-design value traceable to a measurement or to the patch geometry.
- Input size and season decided on a validation split large enough to separate them, by a rule fixed before scoring.

**Non-Goals:** see proposal.md.

## Decisions

### D1. Block size from the semivariogram (fixed before building the dataset)
- `33_spatial_autocorrelation.py` samples 30 windows of 20 km per year (2019, 2023) across the sampling area minus the held-out regions, 300 points per window at 30 m, with the MapBiomas class and the dry-season NDVI. For each distance bin it computes the semivariance (NDVI: half the mean squared difference; class: half the share of pairs with different classes), fits an exponential model and reports the practical range (distance at 95% of the sill).
- **Block side = the largest practical range across the 4 fits (NDVI and class, 2019 and 2023), rounded up to the next whole kilometer.** Blocks are built in kilometers (latitude and longitude converted at each block's latitude), not in a fixed number of degrees.
- If a fit does not converge or its range exceeds half the window (10 km), the window is the limit of what was measured; the block side is then set to 10 km and the limitation is reported.

### D2. Points and quality checks
- 1,000 points per class (bosque, pasto, cultivo) and year, `stratifiedSample` on MapBiomas at 30 m, seed 42, over the sampling area minus the held-out regions. Same 70/15/15 split ratios, blocks assigned once across both years, same 330 m buffer check, same no-data check (now over both composites).
- Blocks are assigned to splits **regardless of class**: every point in a block goes to the same split. The current code blocks per class (to guarantee every class in every split), which lets a forest block and a pasture block covering the same ground land in different splits; that defeats the purpose of spatial blocks. With 6 km blocks and 6,000 points the class balance per split is checked instead: the build stops if any class has fewer than 10% of its points in validation or in test.

### D3. Two composites per example
- Dry: June 1 to September 30. Wet: January 1 to April 30 of the same year (leaf-on, before the dry season of that year's label). Same cloud masking and median.
- Patch: 33x33x26, dry channels first (12 bands + NDVI), then wet. Stored as float32.
- A wet composite that leaves more than 5% of the sampling area without data (the threshold already used for the dry one) is reported, and the no-data check drops the affected examples. If more than 10% of the examples are dropped for wet-season gaps, the dry+wet variants are not run and the result is reported.

### D4. Variant selection (pre-registered)
- **Hyperparameters, per variant**, on validation, 5 seeds (42, 1, 7, 123, 2026), `ddof=1`, truncation rule as before. CNN grid: `lr` {0.0001, 0.0003, 0.001} × `dropout` {0.3, 0.4, 0.5, 0.6} × `batch_size` {8, 16, 32, 64}. RF grid: as in `phase1-hyperparameter-selection`. Selected configuration: the highest mean; ties go to the lower training cost.
- **Edge rule:** if the selected value of `dropout` or `batch_size` is on the edge of its axis (0.6, or 8 or 64), that axis is extended by one step (0.7; 4 or 128) for the selected values of the other two axes, and the selection is redone. Once, not recursively.
- **CNN variants:** A = 3x3 dry (default), B = 3x3 dry+wet, C = 33x33 dry, D = 33x33 dry+wet. The candidate is the variant with the highest mean validation macro-F1. It replaces A only if it beats A by more than their pooled std. A is the default because it follows the tutor's 3x3 design and is the simplest.
- **RF variants:** dry (default) and dry+wet. Dry+wet replaces dry only if it beats it by more than their pooled std.
- Written in `data/study_area/variant_selection/README.md` above `## Results`, hashed and logged to MLflow before the first scoring run, checked by the scoring step.

### D4b. Input normalization (amendment, before any scoring)
- Every CNN variant normalizes its input per channel with the train-split mean and standard deviation, inside the model (fixed buffers saved with the weights), so held-out evaluation, AOI classification and Grad-CAM apply the same scaling without changes. RF is not normalized: its splits are scale-invariant.
- Added to the pre-registration as an amendment on 2026-10-19, before the dataset was finished and before any variant was scored; the first registration is kept in `preregistration_v1.json`.

### D4c. 3x3 input (amendment)
- Following the tutor's guidance to work with 3x3 input, the variant rule compares A (default) and B. The 33x33 variants had been started; their partial results stay in `results.json` as exploratory. The registration before this amendment is kept in `preregistration_v2.json`.
- Grad-CAM on a 3x3 input gives a 3x3 heatmap (90 m): it shows which part of the block weighed, not spatial context.

### D5. Test once and cascade
- `11_compare_classifiers.py` once with the selected RF and CNN. Both CNN variants (A, B) and both RF variants are also reported on test once, for the record.
- Held-out regions (`14`, `16`, `17`) re-run with the selected models. If a selected model uses the wet season, these scripts and `18` pull the wet composite too.
- Then, as in `phase1-hyperparameter-selection` D5: seed-42 checkpoint, AOI and development area 2019-2023, change-map rule, Grad-CAM, and a redrawn AOI reference sample.

## Risks / Trade-offs

- **Bigger blocks leave fewer blocks per split.** Per-class blocking already guarantees at least one block per split; class balance per split is reported.
- **Wet season is cloudier.** D3 measures the gaps before any model is trained.
- **Compute.** About a day of CPU. 3x3 variants run first because they are cheaper.
- **The default favours the simplest variant.** Deliberate and stated before scoring; with a validation split about 2.5 times larger, real differences are more likely to clear the noise.
