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
a claimed CO2 figure was reached. A 2025 study in *Science* found REDD+ projects issue on
average 10.7x more credits than their own baselines justify.

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
| Grad-CAM interpretability | [`grad-cam-interpretability`](../openspec/specs/grad-cam-interpretability/spec.md) | [`2026-09-13-phase1-grad-cam`](../openspec/changes/archive/2026-09-13-phase1-grad-cam/) | `21_grad_cam.py`, `22_explain_transition.py` |

## How a training example is built

Sentinel-2 (10m, 13 bands) paired with MapBiomas labels (30m) — an exact 3:1 pixel ratio.
Each training example is a 33×33 pixel patch (~330m per side), not a single 3×3 pixel —
the CNN needs real spatial context to have anything to learn from. Three classes per
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

### Hyperparameters — fixed once, never tuned

| Model | Parameter | Value | Why |
|---|---|---|---|
| Random Forest | `n_estimators` | 400 | Standard range (300-500); variance reduction has diminishing returns past a few hundred trees |
| Random Forest | `max_depth` | unlimited | Not risky in a forest — overfitting reduction comes from averaging many distinct trees, not pruning each one |
| CNN | Architecture | 3 conv blocks (32→64→128 filters) | Small and custom, not a pretrained backbone — keeps Grad-CAM legible and the comparison against RF honest |
| CNN | Batch size | 32 | Standard for a training set of this size (1,673 training examples in the final dataset) |
| CNN | Learning rate | 0.001 | Default recommended in the original Adam paper (Kingma & Ba, 2014) |
| CNN | Dropout | 0.4 | Standard range (0.3-0.5) for a small training set, where overfitting risk is real |
| CNN | Max epochs / patience | 100 / 10 | Training stops if validation loss doesn't improve for 10 epochs, instead of an arbitrary fixed epoch count |

**None of these were tuned to reach the final result.** They were set once to standard
literature values and never swept during development. What actually moved the final
number across the project's timeline was fixing pipeline bugs and dataset-design
decisions, not adjusting the model — see the trajectory table below.

**Sensitivity sweep, run afterward** (one parameter at a time, `data/study_area/hyperparameter_sweep_results.json`):
the literature-standard choice holds up empirically for 4 of 5 parameters swept (RF
`n_estimators`/`max_depth`, CNN `dropout`/`batch_size` all matched or beat the
alternatives tested). The exception: CNN `learning_rate` — 0.0001 scored 0.850 ± 0.007
against 0.843 ± 0.016 for the 0.001 actually used. The gap is small and the ranges
overlap at only 3 seeds, so it isn't confirmed as a real effect rather than noise, and
the reference CNN checkpoint was not retrained on it without a formal 5-seed comparison
first — flagged here as a real, honest finding, not acted on yet.

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

None of this was "tuning to improve the number" — each change came from asking "is this
actually valid?", and the result sometimes got worse or flipped direction instead of
improving.

## Results

### On the AOI test split

**Random Forest 0.811 F1 macro (±0.004), CNN 0.843 (±0.012)** — a +0.032 difference,
above the pre-registered threshold. Raw numbers: [`data/study_area/comparison_results.json`](../data/study_area/comparison_results.json).
This answers one question only — which model wins on the AOI's own test split — not
which classifier the system should actually use; that needs evidence from outside the
AOI.

### Generalization: 3 independent held-out regions

Each region evaluated with 5 seeds (not 1 — a single run on Bahía Negra had shown
"RF wins" when it was really the CNN's worst seed of the five, a mistake caught before
it became the reported result):

| Region | Landscape | RF | CNN | Result | Raw data |
|---|---|---|---|---|---|
| Filadelfia | Mennonite farming colony, fragmented forest | 0.829 ± 0.001 | 0.696 ± 0.021 | **RF wins, decisively** | [`filadelfia_holdout_results.json`](../data/study_area/filadelfia_holdout_results.json) |
| Bahía Negra | Continuous, remote forest | 0.611 ± 0.002 | 0.611 ± 0.016 | **Real tie** | [`bahia_negra_holdout_results.json`](../data/study_area/bahia_negra_holdout_results.json) |
| Pozo Colorado | Cattle ranching, Trans-Chaco highway | 0.661 ± 0.006 | 0.727 ± 0.021 | **CNN wins** | [`pozo_colorado_holdout_results.json`](../data/study_area/pozo_colorado_holdout_results.json) |

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
at the center pixel, has no such failure mode.

### Decision: CNN as the operational classifier

Confirmed as the classifier that Grad-CAM, the temporal comparison, and carbon
estimation are built on. It wins or ties in 3 of the 4 evaluated contexts (AOI, Bahía
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
transitions detected: `forest_to_pasture` (1,007 ha), `pasture_to_forest` (1,181 ha),
`cropland_to_pasture` (242 ha), `cropland_to_forest` (50 ha). Full numbers:
[`data/study_area/change_stats_2019_2023.json`](../data/study_area/change_stats_2019_2023.json).

**Honest finding**, from cross-checking against MapBiomas
([`scripts/20_mapbiomas_cross_check.py`](../scripts/20_mapbiomas_cross_check.py),
[`data/study_area/mapbiomas_agreement.json`](../data/study_area/mapbiomas_agreement.json)):
`no_change` agrees 99.3% of the time, but each specific transition type agrees very
little (0-4.7%). Most detected transitions are probably classifier noise at the
forest/pasture boundary, not confirmed real change — flagged plainly rather than
presented as validated.

## Grad-CAM — per-prediction interpretability

A heatmap per prediction showing which part of the 33×33 patch actually supported the
classification. Sharpened with Guided Grad-CAM (combines Grad-CAM with guided
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

## Open item for the tutor

`phase5-predictive-model` (a spatiotemporal forecasting extension, proposed in
conversation) is planned but not started — still needs confirmation on whether it's
required core or an optional addition. See
[`openspec/changes/phase5-predictive-model/proposal.md`](../openspec/changes/phase5-predictive-model/proposal.md).

## Current status and what's next

**Phase 1 is complete**: study area, dataset, CNN/RF classifier, temporal comparison,
Grad-CAM — all archived above. **Not started**: Phase 2 (carbon estimation — canopy
height inference, GEDI L4A calibration, IPCC conversion to CO2e), Phase 3 (validation),
Phase 4 (audit demo against Corazón Verde del Chaco).
