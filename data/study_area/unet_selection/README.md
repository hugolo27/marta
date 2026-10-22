# U-Net selection (phase1-segmentation D5)

Pre-registered after the pilot and before any configuration is scored: everything above
"## Results" is hashed and logged to MLflow (`phase1-unet-selection`), and
`scripts/38_unet_selection.py` refuses to score if it changed.

## Inputs fixed by the pilot

From `data/study_area/unet_pilot/results.json` ("decisions"): the validation size in 6 km blocks,
the epoch cap, the early-stopping patience and the Random Forest's per-tree sample size. Nothing
else from the pilot is reused; its models were discarded.

## Split

`38_unet_selection.py split`, run before this README is hashed: test = every block of the reserve;
validation = the pilot's validation size in blocks of the pool; the rest is training. 100 random
draws of the validation blocks (seeds 42 to 141; 100 is blockCV's default number of allocations,
Valavi et al., 2019); the draw kept is the one whose share of each class's labeled cells (30 m) in
validation is closest to validation's share of all labeled cells, so validation is stratified by
class (Kohavi, 1995). Cells rather than the tile's center class, because Dice is scored on cells
and a tile centered on one class is often mostly another (center classes are a third each, cells
are 49% bosque, 39% pasto, 12% cultivo). The test reserve was fixed when the tiles were built, so its class shares
are reported, not chosen. This replaces the pilot's rule 5 floor ("at least 10% of each class"),
which had no source. Output: `final_split.json` and `split_stats.json` in this folder.

## U-Net

- Grid: tile {48, 96, 192} px × `lr` {0.0001, 0.0003, 0.001} × batch {8, 16, 32}, 5 seeds (42, 1,
  7, 123, 2026), `ddof=1`. Early stopping on validation macro Dice with the pilot's patience; best
  weights kept.
- Every configuration is scored on the whole 192 px validation tiles at 30 m, by windows of its own
  tile size with half-window overlap, so all configurations and the Random Forest are scored on
  the same cells.
- Selected configuration: the highest mean validation macro Dice. Ties go to the smaller tile, then
  the larger batch.
- Edge rule, once: if the selected `lr` is 0.0001 or 0.001, 0.00003 or 0.003 is added; if the
  selected batch is 8 or 32, 4 or 64 is added; each with the other two values fixed at the
  selection, and the selection is redone. Tile 48 cannot go lower (fewer than 4 px at the bottom
  level). If tile 192 is selected, tiles of 288 px are extracted and that value is added. Basis:
  a best value at the boundary of the search space suggests a better one beyond it (Godbole et
  al., 2023, Deep Learning Tuning Playbook, Google Research; a practitioner guide, not peer
  reviewed). The step size repeats the grid's own spacing (x3 for `lr`, x2 for batch) and is our
  convention.
- A configuration whose best epoch is within 10 epochs of the cap in any seed is re-run with three
  times the cap.

## Random Forest

- Grid as in `24_hyperparameter_selection.py`: `n_estimators` {300, 400, 500} × `max_depth` {None,
  10, 20} × `max_features` {"sqrt", 0.5}, with the pilot's per-tree sample size, 5 seeds. Ties go
  to fewer trees.

## Comparison

- The U-Net counts as better than the Random Forest only if its mean validation macro Dice exceeds
  the Random Forest's by more than their pooled sample standard deviation. Which one becomes
  operational follows the requirement "Operational classifier selection" of the
  `land-cover-classifier` spec.
- Test: both selected models are scored once on the test tiles, after the decision, and the result
  is used for nothing else.

## Results
