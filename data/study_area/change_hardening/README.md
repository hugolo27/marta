# Change-detection hardening — pre-registration and results

Change: `openspec/changes/phase1-change-detection-hardening/`. This file fixes the candidate grid
and the selection rule **before** any candidate is scored. Its SHA-256 is logged to MLflow
(experiment `phase1-change-detection-hardening`, run `preregistration`) before the first scoring
run, and `scripts/26_score_change_configs.py` refuses to run if the file's pre-registered part
(everything above the "Results" heading) no longer matches that hash.

## Change product

Each date's CNN classification is collapsed to forest (bosque) / non-forest (pasto, cultivo).
Per pixel: stable forest, stable non-forest, loss (forest 2019 → non-forest 2023), gain
(non-forest 2019 → forest 2023). Pixels unclassified in 2019 or 2023 stay unclassified.

## Candidate grid (12 configurations)

Applied in this order, each one only ever turning a change pixel back into the stable class of its
2019 state (loss → stable forest, gain → stable non-forest):

1. **Confidence** `none | 0.7 | 0.9`: loss needs P(bosque) ≥ c in 2019 and P(pasto) + P(cultivo)
   ≥ c in 2023; gain the reverse.
2. **Persistence** `off | on`: loss needs non-forest in 2022 too, gain needs forest in 2022. A
   pixel unclassified in 2022 cannot be confirmed and reverts to stable.
3. **Minimum mapping unit** `off | 0.5 ha`: connected loss (or gain) patches, 8-connectivity, of
   fewer than 50 pixels (10 m) revert to stable. Computed on what survives steps 1-2.

## Development references (not truth; the interpreted sample in `phase1-accuracy-assessment` is)

Compared at 30 m: every layer is sampled on the map's 10 m UTM grid and aggregated to 3×3 blocks
by majority, and a block is scored only if the map is classified in both dates for the majority
of its pixels.

- Hansen loss: `UMD/hansen/global_forest_change_2025_v1_13`, `lossyear` 20-23 and
  `treecover2000` ≥ 25.
- MapBiomas loss: Chaco Collection 5, bosque codes (3, 4, 6, 45) in 2019 and any other valid code
  in 2023.
- **Confirmed loss** = Hansen loss AND MapBiomas loss.
- **Confirmed stable forest** = MapBiomas bosque in 2019 and 2023 AND no Hansen loss 2020-2023.

## Metrics per configuration

- `dev_retention` = confirmed-loss blocks mapped as loss / confirmed-loss blocks, in the
  change-development area.
- `aoi_false_loss_ha` = blocks mapped as loss that are not confirmed loss, in the AOI (ha).
- Also reported, not used for selection: map loss vs. Hansen and vs. MapBiomas separately, in both
  directions, in both areas.

## Selection rule

1. Reject every configuration with `dev_retention` < 0.50.
2. Among the rest, let `m` be the minimum `aoi_false_loss_ha`. Keep configurations with
   `aoi_false_loss_ha` ≤ 1.10 × `m`.
3. Among those, pick the one with the fewest active steps (confidence ≠ none, persistence on,
   minimum mapping unit on). If still tied, the lowest `aoi_false_loss_ha`; if still tied, the
   lower confidence threshold.
4. If step 1 rejects all 12, no configuration is selected. That is reported as the result, and the
   rule is not loosened (design.md, Risks).

## Change-development area

Selection criterion, fixed before scoring: among candidate boxes of 0.13° × 0.13° (~13.4 × 14.4 km,
~19,000 ha, close to the AOI's 20,641 ha) on a regular grid inside the 3-department footprint,
restricted to longitudes east of -60° (UTM zone 21S, the AOI's own zone, so the existing tiling
applies unchanged), excluding any box that intersects the AOI or a held-out region (Filadelfia,
Bahía Negra, Pozo Colorado), pick the one with the largest Hansen loss area for 2020-2023
(`treecover2000` ≥ 25).

Selected box: see "Results" below (filled by task 1.2, before scoring).

## Results

### Change-development area (task 1.2, selected 2026-09-24, before scoring)

`scripts/25_select_change_dev_area.py` scored 610 candidate boxes. Selected: lon -58.960 to
-58.830, lat -20.085 to -19.955 (Alto Paraguay), 19,633 ha, **5,498.2 ha of Hansen loss
2020-2023** (next best: 4,765 ha). Overlap with the AOI and with each held-out region: 0 ha
(checked with `ee.Geometry.intersection().area()`). Geometry: `dev_area.geojson`.

### Scores and selection with the initial CNN (tasks 4.1-4.3, 2026-09-24, superseded)

Superseded by the re-scoring below, after `phase1-hyperparameter-selection` changed the CNN. Kept
as a record.

Pre-registration hash checked by `26_score_change_configs.py score` before scoring (unchanged).
Full table: `scores.json`. Confirmed loss (Hansen AND MapBiomas, 30 m blocks): **AOI 0.0 ha**,
**development area 4,855.9 ha**.

| Confidence | Persistence | MMU 0.5 ha | Dev retention | Dev map loss (ha) | AOI false loss (ha) |
|---|---|---|---|---|---|
| none | off | off | 0.960 | 6,194.4 | 999.6 |
| none | off | on | 0.960 | 6,191.7 | 997.1 |
| none | on | off | 0.927 | 5,859.8 | 581.6 |
| none | on | on | 0.927 | 5,855.9 | 579.1 |
| 0.7 | off | off | 0.931 | 5,635.6 | 118.1 |
| 0.7 | off | on | 0.931 | 5,633.6 | 115.8 |
| **0.7** | **on** | **off** | **0.907** | **5,427.0** | **80.8** |
| 0.7 | on | on | 0.907 | 5,424.8 | 79.6 |
| 0.9 | off | off | 0.446 | 2,292.3 | 0.0 |
| 0.9 | off | on | 0.445 | 2,286.0 | 0.0 |
| 0.9 | on | off | 0.445 | 2,281.0 | 0.0 |
| 0.9 | on | on | 0.444 | 2,275.0 | 0.0 |

Rule applied: step 1 rejects all four confidence-0.9 configurations (retention < 0.50). They
remove every false-loss pixel in the AOI, but miss more than half of the real clearing in the
development area; this is the "suppress everything" case the rule exists for. Step 2: minimum AOI
false loss among the rest is 79.6 ha, so the 10% band is ≤ 87.6 ha: {0.7 + persistence: 80.8,
0.7 + persistence + MMU: 79.6}. Step 3: fewest active steps. **Selected: confidence 0.7 +
persistence, no MMU.**

Selected vs. unfiltered:

- AOI: false loss 999.6 → 80.8 ha (−92%); confirmed stable forest kept 95.1% → 99.6%.
- Development area: 89.3% of map loss confirmed by Hansen (was 84.3%) and 82.2% by MapBiomas (was
  77.8%); captures 87.9% of Hansen loss (was 94.6%) and 80.3% of MapBiomas loss (was 86.7%).

The MMU step changes almost nothing here, because at 30 m blocks isolated 10 m pixels already
drop out; it was not needed to meet the rule. The 80.8 ha left in the AOI are still not confirmed
by either reference. Whether they are errors or real change missed by both is what the interpreted
sample in `phase1-accuracy-assessment` decides.

### Re-scored after `phase1-hyperparameter-selection` (2026-10-13)

The CNN configuration selected on the validation split replaced the operational checkpoint
(`openspec/changes/archive/2026-10-13-phase1-hyperparameter-selection/`, design D5). The AOI and the development area
were reclassified for 2019-2023 with the new checkpoint and the same rule was applied again,
unchanged (pre-registration hash checked by `26_score_change_configs.py score`). Confirmed loss is
the same as before: AOI 0.0 ha, development area 4,855.9 ha.

| Confidence | Persistence | MMU 0.5 ha | Dev retention | Dev map loss (ha) | AOI false loss (ha) |
|---|---|---|---|---|---|
| none | off | off | 0.985 | 6,597.4 | 899.4 |
| none | off | on | 0.985 | 6,591.1 | 893.5 |
| none | on | off | 0.935 | 5,845.9 | 429.1 |
| none | on | on | 0.935 | 5,835.5 | 424.5 |
| 0.7 | off | off | 0.975 | 6,145.0 | 301.7 |
| 0.7 | off | on | 0.975 | 6,143.5 | 300.0 |
| 0.7 | on | off | 0.931 | 5,604.6 | 145.1 |
| 0.7 | on | on | 0.931 | 5,601.1 | 144.4 |
| 0.9 | off | off | 0.911 | 5,274.1 | 18.8 |
| 0.9 | off | on | 0.911 | 5,270.8 | 18.3 |
| **0.9** | **on** | **off** | **0.882** | **4,969.9** | **7.1** |
| 0.9 | on | on | 0.882 | 4,962.9 | 6.7 |

Rule applied: step 1 rejects nothing (every retention ≥ 0.50; the new CNN is more confident on real
clearing, so the confidence-0.9 configurations no longer lose half of it). Step 2: minimum AOI
false loss is 6.7 ha, band ≤ 7.4 ha: {0.9 + persistence: 7.1, 0.9 + persistence + MMU: 6.7}.
Step 3: fewest active steps. **Selected: confidence 0.9 + persistence, no MMU.**

Selected vs. unfiltered:

- AOI: false loss 899.4 → 7.1 ha (−99%); confirmed stable forest kept 95.6% → 99.96%.
- Development area: 92.8% of map loss confirmed by Hansen (was 81.6%) and 87.1% by MapBiomas (was
  76.2%); captures 83.6% of Hansen loss (was 97.6%) and 77.9% of MapBiomas loss (was 90.6%).

Final AOI map (`change_stats_2019_2023_fnf.json`): 7.6 ha loss, 0.5 ha gain, mapped, not assessed.
The AOI reference sample was redrawn on this map (`../accuracy_assessment/`); no point of the
previous draw had been interpreted.
