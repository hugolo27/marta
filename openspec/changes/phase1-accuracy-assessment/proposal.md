## Why

Every accuracy number produced so far measures agreement with another map (MapBiomas for training/test, ESA WorldCover for the held-out regions), not agreement with what is actually on the ground. The original change map illustrates the risk. It reported 1,007 ha of forest loss in the case-study AOI, while MapBiomas agrees with 0% of those pixels and Hansen Global Forest Change records 0.1 ha of loss there for 2020-2023. `phase1-change-detection-hardening` fixes the change map against those automatic references. This change is the final, independent test of the result, and Fase 2 multiplies its hectares by a carbon density.

The case-study project's own Project Description (VM0007, monitoring module VMD0015, `data/study_area/source_documents/Corazon_Verde_del_Chaco_PD_2023-02-28.pdf`, pp. 157-164) states the bar a remote-sensing classification must clear before it is used for change detection in that project:

- accuracy assessed against ground-truth points or samples of high-resolution imagery;
- at least 50 points each for forest and non-forest;
- overall accuracy ≥ 90%;
- forest defined per Paraguay's CDM definition (≥ 25% crown cover, ≥ 0.5 ha, ≥ 5 m potential height);
- assessment data archived.

Measuring the classifier against that same bar is what makes the Fase 4 audit comparison meaningful.

## What Changes

- Build an independent reference dataset for the case-study AOI: a stratified random sample over the hardened forest/non-forest change map (~275 points). Each point is visually interpreted as forest or non-forest on high-resolution imagery for 2019 and 2023, blind to the model's output, against Paraguay's forest definition.
- Assess per-date forest/non-forest accuracy (overall, user's and producer's, with confidence intervals) and report pass/fail against the VM0007 gate (≥ 50 points per class, overall accuracy ≥ 90%).
- Estimate error-adjusted forest-loss and forest-gain areas with 95% confidence intervals (Olofsson et al., 2014). These replace mapped pixel counts as the area figure handed to Fase 2.
- Assess 2023 forest/non-forest accuracy against interpreted reference samples in the three held-out regions (~100 points each), so generalization is measured against reference data, not only against WorldCover. This part does not block Fase 2.
- Measure interpreter consistency with a blind repeat of a 10% subset.
- Record the outcome as a decision gate.

## Capabilities

### New Capabilities
- `map-accuracy-assessment`: independent, reference-based accuracy assessment of the per-date land cover maps and the change map, following the VM0007 accuracy requirement and Olofsson et al. (2014) area estimation, producing the error-adjusted areas that downstream carbon estimation consumes.

### Modified Capabilities
(none — `land-cover-classifier` and `temporal-change-detection` keep their requirements; this change evaluates their outputs)

## Impact

- **Depends on `phase1-change-detection-hardening`:** the sample is stratified on the hardened change map. The independent Hansen cross-check lives in that change and is not repeated here.
- **New scripts** under `scripts/` for sampling, estimation and the held-out assessment, plus an unnumbered estimator module.
- **New versioned reference dataset** (points, labels, interpreter notes, KML for interpretation) and results under `data/study_area/accuracy_assessment/`, archived as VM0007 requires.
- **Reference imagery:** Google Earth Pro historical imagery, with Esri World Imagery Wayback as a secondary source. Planet NICFI is used only if access is granted; the program's contract with Planet ended in 2025 and the project's service account has no access.
- **Manual effort:** ~275 AOI points plus ~300 held-out points, plus ~60 repeats, each interpreted in one view. Estimated at ~6 hours, not yet measured. The AOI part (~3 hours) blocks Fase 2.
- **Updates** `docs/METODOLOGIA_PIPELINE.md` and `docs/FOUNDATION.md`/`FOUNDATION.es.md` (evaluation, point 7).
