## 1. Pre-registration and prerequisites

- [ ] 1.1 Confirm with the tutor that this change belongs in the thesis scope (complementary to `phase1-accuracy-assessment`, no change to the operational CNN), and record it in `research_docs/BITACORA.md`
- [ ] 1.2 Write in `data/study_area/reliability/README.md`, before any scoring or sampling: the forest/non-forest crosswalk for each independent map (design D1), the ensemble comparison criterion and weight grid (D3), the consensus trigger and criterion (D2b), the AOA threshold rule (D4) and the landscape bins (D5). Verified by its SHA-256 logged to an MLflow `preregistration` run that precedes the first scoring run, as in `phase1-change-detection-hardening`

## 2. Independent disagreement zone and hard-case sample

- [ ] 2.1 Build the forest/non-forest disagreement zone from MapBiomas, WorldCover, Dynamic World and JRC GFC2020 over the AOI and the 3 held-out regions, verified by reporting the zone area and the share of each disagreement pattern per area
- [ ] 2.2 Draw ~50 random points per area inside the zone (fixed seed, ≥ 100 m from any `phase1-accuracy-assessment` point), writing a blind CSV/KML pair and a separate design file. Verified by counts per area, the minimum distance check, and no model labels in the blind files
- [ ] 2.3 Interpret the hard-case points (2023, forest/non-forest plus hard-case type) with a 10% blind repeat and adjudication, verified by the same completeness and adjudication checks as `phase1-accuracy-assessment` 4.1-4.3

## 3. Training-label audit

- [ ] 3.1 Build the agreement and disagreement strata over the training split and draw ~100 patches (~60 / ~40, stratified by class, fixed seed), verified by stratum sizes, per-class counts and inclusion probabilities
- [ ] 3.2 Interpret the central 30 m block of each drawn patch for its own period, blind to its MapBiomas label, typing each disagreement (label error, definition difference, mixed pixel), verified by completeness
- [ ] 3.3 Report the label-noise rate per class for the training split with intervals, and record whether the consensus trigger (design D2b) fires, verified by the numbers and the trigger outcome written to the README

## 4. CNN + RF combination and disagreement

- [ ] 4.1 Fit temperature scaling (CNN) and probability scaling (RF) on the validation split, verified by expected calibration error on the test split before and after
- [ ] 4.2 Choose the ensemble weight on the validation split and score ensemble vs. CNN over 5 seeds on the test split and the 3 held-out regions, applying the pre-registered criterion. Verified by a results JSON with per-seed F1 and the criterion outcome, logged to MLflow
- [ ] 4.3 Produce a dense RF forest/non-forest map over the AOI for 2019 and 2023 from the existing composites and the CNN/RF disagreement mask, verified by the flagged fraction per year
- [ ] 4.4 After `phase1-accuracy-assessment` interpretation, report accuracy for agreeing vs. disagreeing reference points in the AOI and each held-out region (Stehman estimates), verified by the results JSON

## 5. Area of applicability

- [ ] 5.1 Extract global-pooled CNN features for the training split and compute the DI threshold with spatial-block folds (design D4), verified by the threshold and the training DI distribution saved
- [ ] 5.2 Compute the AOA mask over the AOI (2019, 2023) and at the held-out reference points, verified by the inside fraction per area
- [ ] 5.3 After interpretation, report accuracy inside vs. outside the AOA per area (counts only below 20 points), verified by the results JSON

## 6. Accuracy by landscape type

- [ ] 6.1 Assign a fragmentation class (Hansen `treecover2000`, 1 km window) and an ecoregion (RESOLVE 2017) to every interpreted reference point, verified by every point having both
- [ ] 6.2 Report forest/non-forest accuracy per class and area with 95% CIs (counts only below 20 points), verified by the results JSON

## 7. Write-up

- [ ] 7.1 Update `docs/METODOLOGIA_PIPELINE.md` with a reliability subsection (hard cases, label noise, ensemble outcome, AOA, landscape breakdown) and add it to the thesis results chapter, stating explicitly that no result here changed the operational classifier
- [ ] 7.2 Run `openspec validate phase1-reliability --strict` and confirm it passes
