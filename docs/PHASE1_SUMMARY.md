# Phase 1 summary — for tutor review

This is an entry point, not a new source of truth — it summarizes what's already versioned
in this repo and links directly to it. Full framing and scope: [`FOUNDATION.md`](FOUNDATION.md).
Full methodology and results, section by section: [`METODOLOGIA_PIPELINE.md`](METODOLOGIA_PIPELINE.md).
Formal requirements and acceptance criteria per capability, tracked via OpenSpec:
[`openspec/specs/`](../openspec/specs/).

## Why this project exists

REDD+ projects need to demonstrate how much forest they hold and how much carbon it
stores. The gap isn't automation — monitoring tools already run at scale (Global Forest
Watch, MapBiomas itself) — it's that none of them give auditable evidence *per individual
prediction*: no way to check why a specific area was classified as deforestation, or how
a claimed CO2 figure was reached. A 2026 synthesis in *Nature Communications* (Swinfield et al.)
of independent evaluations of 44 first-generation REDD+ projects found they claimed 10.7 times
more avoided deforestation than those evaluations justify (95% CI: 5.4-26.5).

**Research question**: can a system be built, on free satellite imagery, that classifies
land cover with interpretable per-prediction evidence, and translates detected change
into CO2 tons — in a way that's auditable end to end?

## Study areas

- **Case-study AOI**: Corazón Verde del Chaco (VCS 2611), ~20,589 ha — the real project
  that Phase 4's audit demo will run against. See [`data/study_area/aoi.geojson`](../data/study_area/aoi.geojson)
  (renders as a map directly on GitHub) and [`data/study_area/README.md`](../data/study_area/README.md).
- **Sampling footprint**: 3 departments of the Paraguayan Chaco, ~24 million ha — needed
  because the AOI alone doesn't contain a single "cropland" pixel. Built in
  [`scripts/03_define_sampling_footprint.py`](../scripts/03_define_sampling_footprint.py).
- **3 held-out sub-regions** (Filadelfia, Bahía Negra, Pozo Colorado) — excluded from all
  training, reserved for testing real generalization, not just AOI-internal accuracy.

## Capabilities covered

| Capability | Spec (requirements) | Archived change | Key scripts |
|---|---|---|---|
| Study area | [`study-area`](../openspec/specs/study-area/spec.md) | [`2026-09-13-phase1-define-study-area`](../openspec/changes/archive/2026-09-13-phase1-define-study-area/) | `03_define_sampling_footprint.py`, `02_gedi_feasibility_check.py` |
| Training dataset | [`training-dataset`](../openspec/specs/training-dataset/spec.md) | [`2026-09-13-phase1-dataset-build`](../openspec/changes/archive/2026-09-13-phase1-dataset-build/) | `06_align_3x3_patches.py`, `08_assemble_dataset.py` |
| Land cover classifier | [`land-cover-classifier`](../openspec/specs/land-cover-classifier/spec.md) | [`2026-09-13-phase1-classifier`](../openspec/changes/archive/2026-09-13-phase1-classifier/) | `09_train_random_forest.py`, `10_train_cnn.py`, `11_compare_classifiers.py` |
| Temporal change detection | [`temporal-change-detection`](../openspec/specs/temporal-change-detection/spec.md) | [`2026-09-13-phase1-temporal-comparison`](../openspec/changes/archive/2026-09-13-phase1-temporal-comparison/) | `18_classify_aoi_temporal.py`, `19_temporal_change_map.py`, `20_mapbiomas_cross_check.py` |
| Dataset v2 and variant selection | `training-dataset`, `land-cover-classifier` (deltas) | [`phase1-dataset-v2`](../openspec/changes/phase1-dataset-v2/) (in progress), [`phase1-patch-size`](../openspec/changes/phase1-patch-size/) | `33_spatial_autocorrelation.py`, `08_assemble_dataset.py`, `31_patch_size_selection.py`, `34_variant_selection.py` |
| Grad-CAM interpretability | [`grad-cam-interpretability`](../openspec/specs/grad-cam-interpretability/spec.md) | [`2026-09-13-phase1-grad-cam`](../openspec/changes/archive/2026-09-13-phase1-grad-cam/) | `21_grad_cam.py`, `22_explain_transition.py` |

## How a training example is built

Sentinel-2 L2A (10m, 12 bands + NDVI; B10 is not in L2A) paired with MapBiomas labels (30m), an exact 3:1 pixel ratio,
so one MapBiomas pixel matches a 3×3 block of Sentinel-2 pixels. Each year has two cloud-free
median composites: dry season (June-September) and wet season (January-April of the same
year). Each example stores a 33×33 window (~330m per side) with 26 channels (13 dry, 13 wet);
the operational CNN reads its central 3×3 block. 1,000 points per class and year, 5,993
examples after quality checks (dataset v2, October 2026; the earlier dataset had 400 per class
and year, dry season only, and a 33×33 CNN input). Three classes per
date: forest / pasture / cropland (MapBiomas code 15 specifically = actual pasture, not
to be confused with natural grassland, which is a different code). "Deforestation" isn't
a class the model predicts directly — it's derived by comparing the same location's
classification across two dates (forest → non-forest).

## The spatial leakage finding — the project's most important methodological result

Each patch covers 330m on the ground. Two patches whose centers are closer than that can
physically overlap on the actual terrain — if one lands in `train` and the other in
`test`, the model is partly evaluated on data it already saw. This leakage showed up
**twice, through two different routes**, and fixing it changed the headline conclusion
every time:

1. **Within a single time period** — found by insisting on re-validating an already
   "passing" result, not by any automated check.
2. **Between 2019 and 2023** — found while building an unrelated demo: a live check meant
   to *confirm* "no leakage" instead surfaced 187 cross-period pairs under 330m apart.

The check itself: real-world distance between patch centers across different splits: if
it's under one patch width, there's physical overlap, not an approximation. Enforced by
`enforce_spatial_buffer()`, inside
[`scripts/08_assemble_dataset.py`](../scripts/08_assemble_dataset.py) — a mandatory,
automatic step that runs every time the dataset is built, rather than a one-off manual
verification that could be skipped on a future rebuild. Correcting each
occurrence flipped the RF-vs-CNN conclusion: "RF wins clearly" → "technical tie" →
"CNN wins" (full trajectory below).

## The two models and comparison criteria

- **Random Forest** (baseline): looks only at the center pixel's spectral values, no
  notion of spatial neighborhood. [`scripts/09_train_random_forest.py`](../scripts/09_train_random_forest.py).
- **CNN** (candidate, `SmallCNN`): 3 small convolutional blocks, a custom architecture
  rather than a pretrained backbone — deliberately kept small so it has to justify its
  added complexity with its own data, and so Grad-CAM stays legible later.
  [`scripts/10_train_cnn.py`](../scripts/10_train_cnn.py).
- **Comparison criterion, fixed *before* training**: 5 random seeds per model, F1 macro
  as the metric, and the CNN only counts as the winner if its mean F1 exceeds Random
  Forest's by more than one combined standard deviation across the 5 runs each.
  [`scripts/11_compare_classifiers.py`](../scripts/11_compare_classifiers.py).

### Current configuration (dataset v2)

| Model | Parameter | Value | Why |
|---|---|---|---|
| Random Forest | Input | center pixel, dry + wet (26 values) | Selected on val over dry only |
| Random Forest | `n_estimators` | 500 | Selected on val from 300, 400, 500 |
| Random Forest | `max_depth` | unlimited | Selected on val; averaging many distinct trees, not pruning, is what limits overfitting |
| CNN | Input | 3×3 block, dry + wet, standardized per channel with train-split statistics | 3×3 from the patch-size experiment; season selected on val |
| CNN | Architecture | 3 conv blocks (32→64→128 filters), 100,707 weights | Small and custom, not a pretrained backbone |
| CNN | Batch size | 32 | Selected on val from 8, 16, 32, 64 |
| CNN | Learning rate | 0.0001 | Selected on val from 0.0001, 0.0003, 0.001, around the Adam default (Kingma & Ba, 2014) |
| CNN | Dropout | 0.3 | Selected on val from 0.3 to 0.6 |
| CNN | Max epochs / patience | 100 / 10 | Training stops if validation loss doesn't improve for 10 epochs; no run hit the cap |

How these were chosen is in "Dataset v2 and variant selection" below. The next paragraphs
describe the first selection, on the earlier dataset.

### Hyperparameters: first selection on the validation split (earlier dataset)

The initial values were set once to standard literature values. What moved the result across
the review rounds was fixing pipeline bugs and dataset-design decisions, not the
hyperparameters (see the trajectory table below).

**Selection on the validation split** ([`phase1-hyperparameter-selection`](../openspec/changes/archive/2026-10-13-phase1-hyperparameter-selection/),
[`scripts/24_hyperparameter_selection.py`](../scripts/24_hyperparameter_selection.py),
[`data/study_area/hyperparameter_selection/`](../data/study_area/hyperparameter_selection/)).
Full grids: RF 18 configurations (`n_estimators` × `max_depth` × `max_features`), CNN 36
(`lr` × `dropout` × `batch_size`), 5 seeds each, macro-F1 on val, sample standard deviation
(`ddof=1`). Rule fixed before scoring (hash logged to MLflow): keep the initial configuration
unless the best one beats it by more than their pooled standard deviation, the same criterion
used for RF vs. CNN. No run hit the 100-epoch cap.

- RF: best 0.832 ± 0.007 vs. initial 0.827 ± 0.003 (+0.005, pooled std 0.006). Initial kept.
- CNN: best (`lr` 0.0003, `dropout` 0.5, `batch_size` 16) 0.844 ± 0.008 vs. initial 0.826 ±
  0.016 (+0.018, pooled std 0.013). Adopted. Early stopping fires between epochs 24 and 39.

Test was then evaluated once, with these configurations. An earlier one-at-a-time sweep (3
seeds) had been scored on the test split
([`hyperparameter_sweep_test_split.json`](../data/study_area/hyperparameter_sweep_test_split.json)).
It was not used to choose anything, including the grid values, and is kept only as a record.

## Dataset v2 and variant selection (October 2026)

Prompted by the tutor's review: the CNN input size had never been tested against the original
3×3 design, and the ~2 km split blocks had been set by hand.

- **Input size** ([`phase1-patch-size`](../openspec/changes/phase1-patch-size/)): the same CNN
  reading only the central 3×3 block, with its own grid on val. Val: 3×3 0.837 ± 0.010, 33×33
  0.844 ± 0.008, a difference inside the pooled std (0.009), so by the pre-registered rule 3×3
  became operational. The work continues with 3×3 input.
- **Block size from data** ([`data/study_area/spatial_autocorrelation/`](../data/study_area/spatial_autocorrelation/)):
  semivariograms of NDVI and of the MapBiomas class over 18,000 points give practical ranges of
  3.9 to 5.2 km, above the ~2 km blocks. The block side is now 6 km (Roberts et al., 2017;
  Valavi et al., 2019), so earlier test scores were probably optimistic.
- **Blocks were assigned per class**: one square could send its forest points to train and its
  pasture points to test. Now every point in a block goes to the same split, and the build stops
  if a class ends up with under 10% of its points in val or test.
- **Input normalization**: bands range ~70-4,700 and NDVI -0.3 to 0.9, so unscaled, NDVI barely
  reached the CNN's first layer. Each channel is standardized with train-split statistics,
  stored with the weights.
- **Dry vs. dry + wet**, 1,000 points per class and year, a wider grid with an edge rule.

Variants and rules were pre-registered before scoring (hash in MLflow, two dated amendments:
normalization, and 3×3 only), see
[`data/study_area/variant_selection/README.md`](../data/study_area/variant_selection/README.md):

| Variant | Val | Test |
|---|---|---|
| RF, dry | 0.827 ± 0.002 | 0.799 ± 0.004 |
| RF, dry + wet | 0.845 ± 0.002 | 0.841 ± 0.003 |
| CNN 3×3, dry | 0.843 ± 0.003 | 0.835 ± 0.007 |
| CNN 3×3, dry + wet | 0.869 ± 0.007 | 0.865 ± 0.003 |

The wet season wins for both models, well beyond seed noise, so both operational models use
dry + wet. Val and test now nearly match.

## What changed along the way

- **Training volume**: 200 → 400 examples per class/period (final dataset: 2,393
  patches) — done specifically to rule out that the CNN's Filadelfia failure was a data
  volume problem. It wasn't: the AOI's own forest class improved with more data (IoU
  0.803 → 0.883), but Filadelfia stayed nearly flat (0.451 → 0.460).
- **Augmentation seed**: a real bug — the seed only controlled PyTorch's RNG, not
  numpy's, which drives the rotation/flip augmentation. Fixed; it changed one run's
  numbers but not the final conclusion.
- **Train/val/test split assignment**: evolved 3 times — random per individual point →
  spatial blocking by ~2km blocks → an explicit 330m buffer check enforced by
  construction (not dependent on one dataset getting lucky).
- **Unifying splits across 2019 and 2023**: the most expensive fix — splits were
  originally assigned separately per time period, allowing leakage between dates. Fixed
  by pooling both periods before assigning splits, once.

**Trajectory of the RF vs. CNN result** (F1 macro, 5-seed comparison on the AOI):

| Point in time | RF | CNN | Conclusion | What changed |
|---|---|---|---|---|
| First run | 0.826 | 0.770 | RF wins clearly | — |
| Review round 1 | 0.826 | 0.751 | RF wins clearly | bug: seed didn't fix numpy's augmentation RNG |
| Review round 2 | 0.775 | 0.783 | Technical tie | UTM zone bug (footprint spans zones 20S/21S; `.reproject()` was distorting points far from the forced zone) |
| Review round 4 | 0.773 | 0.778 | Technical tie (held) | spatial buffer check made mandatory and automatic on every dataset build, not a one-off manual verification |
| Review rounds 5-8 | 0.811 | 0.843 | **CNN wins** | second leakage found (between 2019/2023), dataset doubled to 400/class, all 3 held-out regions rerun with 5 seeds |
| Tutor review of this PR | 0.811 | 0.860 | **CNN wins** | hyperparameters selected on val, test evaluated once, sample standard deviations |
| Dataset v2 | 0.841 | 0.865 | **CNN wins** | 6 km blocks from the variogram, class-agnostic blocks, 3×3 input, dry + wet, normalization, 1,000 per class |

None of this was "tuning to improve the number" — each change came from asking "is this
actually valid?", and the result sometimes got worse or flipped direction instead of
improving.

## Results

### On the AOI test split

**Random Forest 0.841 F1 macro (±0.003), CNN 0.865 (±0.003)**, a +0.024 difference,
above the pre-registered threshold (pooled std 0.003). 915 test examples in 6 km blocks,
variants and configurations selected on val, test evaluated once. On the earlier dataset it
was 0.811 vs. 0.860, with blocks smaller than the autocorrelation range. Raw numbers: [`data/study_area/comparison_results.json`](../data/study_area/comparison_results.json).
This answers one question only — which model wins on the AOI's own test split — not
which classifier the system should actually use; that needs evidence from outside the
AOI.

### Generalization: 3 independent held-out regions

Each region evaluated with 5 seeds (not 1 — a single run on Bahía Negra had shown
"RF wins" when it was really the CNN's worst seed of the five, a mistake caught before
it became the reported result):

| Region | Landscape | RF | CNN | Result | Raw data |
|---|---|---|---|---|---|
| Filadelfia | Mennonite farming colony, fragmented forest | 0.839 ± 0.004 | 0.824 ± 0.010 | **RF wins** (earlier: 0.831 vs. 0.706) | [`filadelfia_holdout_results.json`](../data/study_area/filadelfia_holdout_results.json) |
| Bahía Negra | Continuous, remote forest | 0.621 ± 0.001 | 0.627 ± 0.005 | **CNN wins**, narrowly (+0.006 vs. pooled std 0.004) | [`bahia_negra_holdout_results.json`](../data/study_area/bahia_negra_holdout_results.json) |
| Pozo Colorado | Cattle ranching, Trans-Chaco highway | 0.668 ± 0.004 | 0.710 ± 0.027 | **CNN wins** | [`pozo_colorado_holdout_results.json`](../data/study_area/pozo_colorado_holdout_results.json) |

### Why the CNN specifically fails in Filadelfia

Investigated, not just reported as a number. Ruled out first: it isn't a time-period
effect (2019 and 2023 fail at nearly identical rates), and it isn't a data volume problem
(doubling the training set didn't move Filadelfia while it did improve the AOI's own
forest class). Confirmed with statistical and visual evidence
([`scripts/15_diagnose_filadelfia_bosque.py`](../scripts/15_diagnose_filadelfia_bosque.py)):
misclassified forest points sit systematically on **narrow forest strips** (Mennonite
windbreak hedgerows, a standard feature of that agriculture) that don't fill the model's
330m window. The CNN partly learned "forest" as large, contiguous canopy — a pattern
that doesn't transfer to forest fragmented into thin strips. Random Forest, looking only
at the center pixel, has no such failure mode. With the 3×3 input (90 m) the gap shrank
from 0.125 to 0.015, consistent with that diagnosis; the failure has not been re-analyzed
point by point with the new model.

### Decision: CNN as the operational classifier

Confirmed as the classifier that Grad-CAM, the temporal comparison, and carbon
estimation are built on. It wins in 3 of the 4 evaluated contexts (AOI, Bahía
Negra, Pozo Colorado) and loses only in Filadelfia, with a specific, understood cause —
not an unexplained generalization gap. Acceptable because the actual deployment target
(Corazón Verde del Chaco) isn't a fragmented-colony landscape like Filadelfia.

**Limitation documented, not hidden**: don't trust the CNN without cross-checking against
Random Forest for forest classification in landscapes structurally similar to
Filadelfia (narrow strips, windbreak-style fragmentation). This doesn't generalize to
the whole Chaco either — 3 boxes of ~40×40km cover under 2% of the 24-million-ha
sampling footprint. What is established with real evidence: there's no universal winner,
performance depends on landscape type, and that's backed by a diagnosed mechanism, not
just a correlation.

## Why this result can be trusted — 9 rounds of review

The conclusion changed direction multiple times: "RF wins clearly" (spatial leakage
within a period) → "technical tie" (that leakage fixed) → "CNN wins" (a second leakage
found, between periods) → the Filadelfia gap confirmed real (two image-generation bugs
fixed, the gap widened instead of shrinking) → training volume doubled to rule out scale
→ the Filadelfia mechanism diagnosed with visual evidence → an own over-generalization
caught and corrected once the 3 regions were recomputed with real variance. That the
conclusion changed this many times isn't a sign of a broken process — it's what happens
when every claim is put through "is this actually true?" instead of accepted on the
first reassuring answer.

| Round | Main finding |
|---|---|
| 1 | Reproducibility bug (seed didn't control numpy's RNG); demo map was silently zero-filling cloud gaps; duplicated code consolidated |
| 2 | The UTM zone bug — the deepest finding in the project up to that point |
| 3 | Empirically verified (not just assumed) that the cloud-mask check actually works; `gap_fraction()` could return `None` |
| 4 | Spatial blocking didn't guarantee separation *by construction* at block edges — added an explicit post-hoc check (`enforce_spatial_buffer`) |
| 5 | Spatial leakage between time periods (second occurrence) — found while building a demo, not by an automated check |
| 6 | Two more bugs: a composite missing a `.clip()` to the sampling area, and the UTM zone bug reappearing in a new script |
| 7 | Dataset scaled to 400/class to rule out training volume as the explanation for rounds 1-6's instability |
| 8 | 5-seed reruns across the 3 held-out regions; final decision closed |
| 9 | Requested before committing rounds 7-8's code: a diagnosis script broken by an earlier refactor (`AttributeError` on rerun), a split-assignment bug silently overwriting the block/split decision for 64 locations whose class changed between 2019 and 2023, and a fragile patch-center indexing pattern in `predict_rf` brought in line with an existing fix. None of these changed already-generated results or required a dataset rebuild. |

## Temporal comparison, 2019 → 2023

The same trained CNN checkpoint is applied to both dates — never retrained per date, to
avoid mixing training variance with real change.
[`scripts/18_classify_aoi_temporal.py`](../scripts/18_classify_aoi_temporal.py) →
[`scripts/19_temporal_change_map.py`](../scripts/19_temporal_change_map.py). Named
transitions detected with the current checkpoint: `pasture_to_forest` (1,228 ha), `forest_to_pasture`
(436 ha), `cropland_to_pasture` (113 ha), `cropland_to_forest` (104 ha). With the earlier 33×33
checkpoint, transitions involving cropland (absent from the AOI) totalled ~1,090 ha; now ~220 ha. Full numbers:
[`data/study_area/change_stats_2019_2023.json`](../data/study_area/change_stats_2019_2023.json).

**Honest finding**, from cross-checking against MapBiomas
([`scripts/20_mapbiomas_cross_check.py`](../scripts/20_mapbiomas_cross_check.py),
[`data/study_area/mapbiomas_agreement.json`](../data/study_area/mapbiomas_agreement.json)):
`no_change` agrees 99.5% of the time, but each specific transition type agrees very
little (0-11.4%; the highest is `pasture_to_forest`). Most detected transitions are probably classifier noise at the
forest/pasture boundary, not confirmed real change — flagged plainly rather than
presented as validated.

That finding led to `phase1-change-detection-hardening` (archived): the main product is now
forest/non-forest change, with post-processing chosen by a pre-registered rule against Hansen
and MapBiomas. With the current checkpoint the rule selects confidence ≥ 0.9 on both dates,
persistence into 2022 and a minimum mapping unit: 8.1 ha of mapped loss in the AOI (7.6 ha with
the earlier checkpoint) and 61.0 ha of gain (0.5 ha earlier), mapped, not yet assessed. The
jump in gain is checked by the reference sample, whose gain stratum now holds 6,034 pixels
instead of 45. Details: [`data/study_area/change_hardening/README.md`](../data/study_area/change_hardening/README.md).
The final test against interpreted reference points is `phase1-accuracy-assessment`, in progress.

## Grad-CAM — per-prediction interpretability

A heatmap per prediction showing which part of the input actually supported the
classification. With the 3×3 input the native map is 3×3 pixels: it shows which part of the
block weighed, not wider spatial context. The text below describes the earlier 33×33 version. Sharpened with Guided Grad-CAM (combines Grad-CAM with guided
backpropagation) — the native heatmap is 8×8, this adds real detail without fabricating
resolution. Also applied to transition pixels, explaining *both* halves (2019 and 2023)
of a detected change, not just that the diff changed. Applies only to the CNN — Random
Forest has no gradients or activation maps to visualize.
[`scripts/21_grad_cam.py`](../scripts/21_grad_cam.py),
[`scripts/22_explain_transition.py`](../scripts/22_explain_transition.py).

## A note on visualizations

The PNG figures referenced in the internal slide deck (classification maps, Grad-CAM
heatmaps, the RF-vs-CNN comparison chart) aren't tracked in git —
`data/study_area/*.png` is gitignored on purpose, to avoid churn from regenerated
binaries. They're not part of this PR as a result. Happy to attach a specific set
directly if visuals would help the review — flag which ones and we'll add them as an
explicit exception.

## Next capability, planned

`phase5-predictive-model` (a spatiotemporal forecasting extension) is planned but not
started. See
[`openspec/changes/phase5-predictive-model/proposal.md`](../openspec/changes/phase5-predictive-model/proposal.md).

## Current status and what's next

**Phase 1 is complete**: study area, dataset, CNN/RF classifier, temporal comparison,
Grad-CAM — all archived above. **Not started**: Phase 2 (carbon estimation — canopy
height inference, GEDI L4A calibration, IPCC conversion to CO2e), Phase 3 (validation),
Phase 4 (audit demo against Corazón Verde del Chaco).
