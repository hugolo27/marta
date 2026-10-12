## Context

See proposal.md for motivation. Relevant current state:

- Operational classifier: the reference CNN checkpoint (`data/study_area/cnn_checkpoint.pt`, seed 42). Random Forest baseline on the central pixel's 12 bands + NDVI (`scripts/09_train_random_forest.py`). Fixed train/val/test split by ~2 km spatial blocks (`scripts/dataset_loader.py`).
- Dense CNN probabilities exist for the AOI 2019-2023 (`aoi_proba_*.npy`). RF has no dense map yet.
- `phase1-accuracy-assessment` provides interpreted forest/non-forest reference points: ~275 in the AOI (2019 and 2023, stratified by change class) and 3 × 100 in the held-out regions (2023, stratified by WorldCover tree/other). Its labels are not yet interpreted.
- Known hygiene issue: the hyperparameter sweep scored on the test split (BITACORA 2026-09-19). Nothing here selects anything on the test split except the pre-registered ensemble comparison, which uses the same split and criterion style as the original CNN vs. RF decision.

## Goals / Non-Goals

**Goals:**
- Locate the classifier's weak spots with numbers and confidence intervals, not anecdotes.
- Keep the interpreted assessment sample as an untouched test: every use of it here is descriptive.
- Give the thesis an honest statement of where the accuracy figure applies and where it does not.

**Non-Goals:** see proposal.md.

## Decisions

### D1. Hard cases: probability sample over an independent disagreement zone
- **Zone.** Pixels where the four independent maps do not agree on forest vs. non-forest, each collapsed with a fixed crosswalk recorded before sampling: MapBiomas Chaco (forest codes per `mapbiomas_legend.py`), ESA WorldCover 2021 (tree cover), Dynamic World 2023 annual mode (trees), JRC GFC2020 (forest). Built over the three held-out regions and the AOI, which is where the classifier is evaluated. The model's predictions play no part in defining the zone.
- **Sample.** ~50 points per area (~200 total), simple random within each area's zone, fixed seed, excluding any point within 100 m of a `phase1-accuracy-assessment` point so the two samples stay disjoint.
- **Interpretation.** Same KML/CSV workflow and Paraguayan definition as the assessment, 2023 only, plus a hard-case type: windbreak, degraded forest, shrubland/other wooded land, pasture with scattered trees, other. Blind to model output.
- **Output.** CNN and RF forest/non-forest accuracy per hard-case type, with Wilson 95% intervals, and the share of each type within the zone. These describe the disagreement zone, not the landscape, and are labeled that way.
- **Why not stratify by type:** the type is only known after interpretation, so stratifying on it would need a map of hard cases that does not exist.

### D2. Training-label audit
- Two strata over the training split, at forest/non-forest level: patches whose MapBiomas label disagrees with at least two of the other three maps, and patches where all four agree. Sampling only the disagreement set would overstate noise and miss errors the maps share.
- Draw ~100 patches (fixed seed): ~60 from the disagreement stratum and ~40 from the agreement stratum, each stratified by MapBiomas class, with inclusion probabilities recorded.
- Interpret each patch's central 30 m block for its own period (2019 or 2023) with the same primary definition and attributes as `phase1-accuracy-assessment`, blind to its MapBiomas label.
- Each disagreement is typed as a real label error, a definition difference (e.g. crown 10-25%, which is forest under the FREL and MapBiomas but not under the CDM definition) or a mixed pixel.
- Report the noise rate per class for the whole training split (stratified estimator) and per stratum. Nothing is relabeled or retrained.

### D2b. Consensus labels: only on a pre-registered trigger
Training on consensus labels is not part of this change. It is run as a separate change only if D2 shows systematic noise in forest whose lower 95% bound exceeds 10%. If it is run:
- Variant: weight training examples by inter-map agreement plus a small hand-labeled set of hard cases, rather than discarding disagreeing examples, which would strip the boundary examples the classifier most needs. WorldCover stays out of the labels (it is the held-out verifier).
- Arbiter: a hand-labeled set outside the AOI and disjoint from the assessment sample (e.g. the D1 hard-case points), never MapBiomas or the consensus itself, since each model would win against its own labels.
- Replaces the current labels only if all three hold: macro-F1 on the hand-labeled set improves by more than one combined standard deviation over 5 seeds; forest recall on hard cases drops by no more than 2 points; false change in stable control areas does not increase. CNN and RF are both retrained under the same protocol.

### D3. CNN + RF combination
- **Calibration.** Temperature scaling for the CNN (one scalar on the logits) and Platt-style scaling of RF class probabilities, both fitted on the validation split only.
- **Ensemble.** `p = w * p_cnn + (1 - w) * p_rf`, with `w` chosen on the validation split from {0.25, 0.5, 0.75}.
- **Pre-registered comparison**, written into tasks.md before scoring and matching the Fase 1 posture: 5 seeds, macro-F1 on the test split and on each held-out region. The ensemble counts as better only if its mean F1 exceeds the CNN's by more than one combined standard deviation. Either outcome is reported. A better ensemble is **not** adopted here: adopting it changes the operational model and needs its own change and a fresh assessment sample.
- **Disagreement flag.** A pixel or point is flagged when the CNN and RF argmax differ at forest/non-forest level. Reported: the flagged fraction of the AOI (needs dense RF over the AOI) and of each held-out sample, and accuracy on the interpreted reference points split into agree vs. disagree, with Stehman (2014) estimates since the flag is not a sampling stratum. Calibration quality reported as expected calibration error before and after scaling, on the test split.

### D4. Area of applicability
- **Feature space.** The CNN's 128-d global-pooled features (the layer before the classifier head), standardized on the training split. The original AOA weights predictors by importance; for learned features no such weight exists, so all dimensions are weighted equally, which is stated as a departure from Meyer and Pebesma (2021).
- **Dissimilarity index (DI)** per Meyer and Pebesma: distance to the nearest training sample divided by the mean pairwise training distance. **Threshold:** computed on the training data with the spatial-block cross-validation folds (nearest training sample from a different fold), as the outlier-removed maximum (upper whisker of the DI distribution).
- **Outputs.** AOA mask over the AOI (2019, 2023) and at each held-out reference point, the fraction inside, and accuracy inside vs. outside from the interpreted points (Stehman estimates; if fewer than 20 points fall outside in an area, report counts only).
- **Alternative rejected:** AOA on the RF's 13 input features. It is cheaper but describes the baseline's feature space, not the operational model's.

### D5. Accuracy by landscape type
- **Fragmentation class** per reference point from Hansen `treecover2000` (independent of the model and of MapBiomas' 2019/2023 maps): forest fraction in a 1 km window around the point, binned into low (< 30%), mixed (30-70%) and high (> 70%). Bins fixed here, before looking at results.
- **Ecoregion** from RESOLVE Ecoregions 2017 (Dry Chaco vs. Humid Chaco), as available in Earth Engine.
- **Estimates.** Forest/non-forest accuracy per class with Stehman estimates and 95% CIs, pooling AOI and held-out points by area weight only within each area (areas are not pooled into one number). Cells with fewer than 20 points are reported as counts, not accuracies.

### D6. Where things live
- Scripts numbered after `30_assess_heldout_accuracy.py`; estimators reused from `scripts/accuracy_stats.py`.
- Data under `data/study_area/reliability/`, with the same blind/label-revealing file separation as `accuracy_assessment/`.
- MLflow experiment `phase1-reliability`.

## Risks / Trade-offs

- **[Risk] The disagreement zone is dominated by one hard-case type** → Reported as found; the per-type intervals show which types have too few points to say anything.
- **[Risk] Learned-feature AOA flags little or almost everything** → The threshold rule is fixed in advance; either result is reported, along with the DI distribution so a reader can judge it.
- **[Risk] The ensemble wins** → Recorded as a finding and as the motivation for a follow-up change; the CNN stays operational within the thesis to keep the assessed numbers valid.
- **[Trade-off] ~300 more interpreted points** → Accepted. The hard cases are where the classifier's limits are actually argued, and the label audit is the only direct evidence on MapBiomas label quality in this project. Neither blocks Fase 2.
- **[Risk] Small cells in the landscape breakdown** → Minimum cell size of 20 points; below it, counts only.

## Open Questions

- Whether the forestry-engineer contact can take part of the hard-case interpretation, which would also give an independent second opinion on windbreak and shrubland calls.
- Whether to add Paraguay's official forest cover map (INFONA) to the disagreement zone, if it is published as open data for 2023.
