# U-Net change map: pre-registration and results

Change: `openspec/changes/phase1-segmentation/` (design D6, amended 2026-11-10). This file fixes the
change-map rule for the U-Net maps **before** any configuration is scored. Its SHA-256 is logged to
MLflow (experiment `phase1-segmentation-change`, run `preregistration`) before the first scoring run,
and the scoring script refuses to run if the part above the "Results" heading no longer matches that
hash.

It carries over the rule of `data/study_area/change_hardening/README.md` (the CNN maps) with three
changes: the maps are the U-Net's 30 m rasters, the minimum mapping unit is expressed in 30 m cells,
and step 2 of the selection measures false loss on the development area's confirmed stable forest
instead of the AOI, so the AOI, where accuracy is assessed against the interpreted sample, plays no
part in choosing the filter.

## Change product

Each date's U-Net classification (`18_classify_aoi_temporal.py`, seed-42 checkpoint, 30 m cells) is
collapsed to forest (bosque) / non-forest (pasto, cultivo). Per cell: stable forest, stable
non-forest, loss (forest 2019 to non-forest 2023), gain (non-forest 2019 to forest 2023). Cells
unclassified in 2019 or 2023 stay unclassified.

## Candidate grid (12 configurations)

Applied in this order, each one only ever turning a change cell back into the stable class of its
2019 state (loss to stable forest, gain to stable non-forest):

1. **Confidence** `none | 0.7 | 0.9`: loss needs P(bosque) >= c in 2019 and P(pasto) + P(cultivo)
   >= c in 2023; gain the reverse. P is the U-Net's 30 m probability averaged over its windows.
2. **Persistence** `off | on`: loss needs non-forest in 2022 too, gain needs forest in 2022. A cell
   unclassified in 2022 cannot be confirmed and reverts to stable.
3. **Minimum mapping unit** `off | 0.5 ha`: connected loss (or gain) patches, 8-connectivity, of
   fewer than 6 cells revert to stable (0.5 ha / 0.09 ha per cell = 5.6, rounded up so a kept patch
   is never below 0.5 ha). Computed on what survives steps 1-2.

## Development references (not truth; the interpreted sample in `phase1-accuracy-assessment` is)

Both references are 30 m and are sampled by nearest neighbour on the map's own 30 m grid. A cell is
scored only if the map is classified in 2019 and 2023.

- Hansen loss: `UMD/hansen/global_forest_change_2025_v1_13`, `lossyear` 20-23 and
  `treecover2000` >= 25.
- MapBiomas loss: Chaco Collection 5, bosque codes (3, 4, 6, 45) in 2019 and any other valid code
  in 2023.
- **Confirmed loss** = Hansen loss AND MapBiomas loss.
- **Confirmed stable forest** = MapBiomas bosque in 2019 and 2023 AND no Hansen loss 2020-2023.

## Metrics per configuration

Both in the change-development area only.

- `dev_retention` = confirmed-loss cells mapped as loss / confirmed-loss cells.
- `dev_false_loss_ha` = confirmed-stable-forest cells mapped as loss (ha).
- Also reported, not used for selection: map loss vs. Hansen and vs. MapBiomas separately, in both
  directions, in the development area and in the AOI.

## Selection rule

1. Reject every configuration with `dev_retention` < 0.50.
2. Among the rest, let `m` be the minimum `dev_false_loss_ha`. Keep configurations with
   `dev_false_loss_ha` <= 1.10 x `m`.
3. Among those, pick the one with the fewest active steps (confidence != none, persistence on,
   minimum mapping unit on). If still tied, the lowest `dev_false_loss_ha`; if still tied, the
   lower confidence threshold.
4. If step 1 rejects all 12, no configuration is selected. That is reported as the result, and the
   rule is not loosened.

The selected configuration is then applied once to the AOI, which yields the change map the
reference sample is drawn on.

## Change-development area

The same box as the CNN maps (`data/study_area/change_hardening/dev_area.geojson`), selected there
before any scoring; since 2026-11-13 no training tile lies within the autocorrelation range of it
(design D2).

## Results

Run 2026-11-20 on the maps of `18` (seed-42 checkpoint, sha256 eec2fb79...), commit 104a1ed plus the
reporting fix of the next commit (reference totals restricted to the classified area; selection
unchanged). Pre-registration hash `36f7ab82...` logged before scoring and checked by `score`.

| Confidence | Persistence | MMU | Dev retention | Dev map loss (ha) | Dev false loss (ha) |
|---|---|---|---|---|---|
| none | off | off | 0.956 | 5,525.0 | 26.3 |
| none | off | on | 0.956 | 5,487.1 | 24.1 |
| none | on | off | 0.900 | 5,179.6 | 20.8 |
| none | on | on | 0.900 | 5,140.9 | 19.0 |
| 0.7 | off | off | 0.920 | 4,974.7 | 6.7 |
| 0.7 | off | on | 0.919 | 4,953.4 | 6.0 |
| 0.7 | on | off | 0.881 | 4,759.6 | 6.3 |
| 0.7 | on | on | 0.880 | 4,737.9 | 5.7 |
| 0.9 | off | off | 0.704 | 3,592.8 | 0.6 |
| 0.9 | off | on | 0.702 | 3,564.8 | 0.4 |
| 0.9 | on | off | 0.684 | 3,489.0 | 0.6 |
| 0.9 | on | on | 0.681 | 3,455.7 | 0.4 |

Development area: 4,848.9 ha confirmed loss, 9,519.1 ha confirmed stable forest. All 12 pass step 1;
`m` = 0.4 ha, so step 2 keeps the two configurations at 0.4 ha; step 3 picks the one with fewer
active steps: **confidence 0.9 + minimum mapping unit**. It keeps 70% of the confirmed loss: the
strict threshold buys almost no false loss at the cost of omission, which the `discarded_change`
stratum of the reference sample measures.

AOI with that configuration: 5.1 ha loss (57 cells), 61.6 ha gain, 20,063.6 ha stable forest,
452.0 ha stable non-forest; Hansen and MapBiomas confirm no loss in the AOI. Seg-Grad-CAM on two loss
patches (`22`): re-predicting every window over each explained cell gives back the stored
probabilities within 8.4e-5 in both dates. Reference sample redrawn on this map (`27`, seed 42), before
any interpretation: 340 points; stratum sizes loss 57, gain 684, discarded change 5,398, buffer 334
(0.15% of the AOI), stable forest 221,812, stable non-forest 399 cells.
