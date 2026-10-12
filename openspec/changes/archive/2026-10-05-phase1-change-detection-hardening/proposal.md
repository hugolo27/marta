## Why

The change map produced by `temporal-change-detection` reports 1,007 ha of `bosque_a_pasto` over the case-study AOI between 2019 and 2023. Two independent products contradict it. MapBiomas agrees with 0% of those pixels (`data/study_area/mapbiomas_agreement.json`). Hansen Global Forest Change (`UMD/hansen/global_forest_change_2025_v1_13`, tree cover ≥ 25%) records 0.1 ha of loss inside the AOI polygon for 2020-2023 (checked 2026-09-24). The map's forest loss is therefore almost entirely commission error, most likely per-date classifier noise at the forest/pasture boundary compounding when two dates are diffed.

`phase1-accuracy-assessment` measures the map against manually interpreted reference points, which is the expensive step. Running it on a map already known to fail would spend that effort twice: once to confirm the failure, and again on a fresh sample after fixing it. This change fixes change detection first, using only automatic, independent references for development. The interpreted sample then acts as a single, untouched final test.

## What Changes

- Derive change from a forest/non-forest collapse of each date's classification (bosque vs. pasto+cultivo). Changes between pasto and cultivo are not forest change, and account for the `cultivo_a_*` transitions MapBiomas does not support (0 cultivo pixels in the AOI in either year).
- Add candidate post-processing to the change map: a 0.5 ha minimum mapping unit (the Paraguayan forest definition's own minimum area), temporal persistence using additional annual classifications (2020, 2021, 2022), and a per-pixel confidence requirement on both dates' predictions.
- Select one configuration by a pre-registered rule, evaluated against development references only: Hansen loss and MapBiomas transitions over the AOI, and over a separate change-development area that has real, documented deforestation 2020-2023 (so a filter that suppresses all change cannot win by default).
- Keep the named-transition map as a secondary output; the forest-loss/forest-gain map becomes the primary change product consumed by `phase1-accuracy-assessment` and Fase 2.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `temporal-change-detection`: the change map is derived from forest/non-forest per date with selected post-processing, and the choice of post-processing is made on independent development references with a pre-registered rule. A new requirement covers the development evaluation.

## Impact

- `scripts/18_classify_aoi_temporal.py` gains per-pixel class probabilities and the extra years 2020-2022; `scripts/19_temporal_change_map.py` gains the forest/non-forest collapse and post-processing. The existing 2019/2023 class rasters are regenerated, but the trained checkpoint and the classifier are unchanged.
- New development-evaluation script(s) under `scripts/`, logged to MLflow under experiment `phase1-change-detection-hardening`.
- GEE usage: dense inference over the AOI for 3 more years plus a change-development area of similar size. Well inside the Community-tier quota, based on the cost of the existing 2-date run.
- `phase1-accuracy-assessment` now depends on this change: it samples the hardened change map, not the current one.
- Updates `docs/METODOLOGIA_PIPELINE.md` with the finding and the selected configuration.
