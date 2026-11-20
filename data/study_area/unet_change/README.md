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
