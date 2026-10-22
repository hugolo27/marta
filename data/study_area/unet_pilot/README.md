# U-Net pilot (phase1-segmentation D4)

Pre-registered before any pilot run: everything above "## Results" is hashed and logged to MLflow
(`phase1-unet-pilot`), and `scripts/37_unet_pilot.py` refuses to run if it changed. The pilot sets
the early-stopping patience, the validation and test sizes, whether 2,000 tiles are enough, and the
Random Forest's per-tree sample size. Its models are discarded.

## Data

- Tiles from `data/study_area/tiles/` (`35_assemble_tiles.py`). Only the `pool` group is read; the
  `reserve` group (20% of the 6 km blocks) is never read by the pilot.
- Provisional split of the pool by 6 km blocks, shuffled with seed 42: 80% of the blocks train,
  20% validation. This proportion is used only here; the final one comes out of this pilot.

## Runs

- U-Net (`36_train_unet.py`): tile 96 px, batch 16, `lr` 0.0001, 0.0003 and 0.001 (the center and
  both ends of the selection grid), seeds 42 and 1, 100 epochs without early stopping. Validation
  macro Dice at 30 m recorded every epoch. Best weights = best validation macro Dice.
- Seed noise `s`: the pooled sample standard deviation (`ddof=1`) of the best validation macro Dice
  across the two seeds of each `lr`, pooled over the three `lr` values (square root of the mean of
  the three variances).

## Rules

1. **Epoch cap.** If any run's best epoch is within the last 10 epochs, the cap is raised to 300
   for the selection (as in `24_hyperparameter_selection.py`).
2. **Patience.** For each patience `p` from 1 to 30: in each run, the epoch where training would
   stop with `p` epochs without improvement, and the best validation macro Dice up to that epoch.
   Patience = the smallest `p` with which every run keeps a best within `s` of its full-run best.
   If no `p` up to 30 does, the selection trains to the cap without early stopping.
3. **Test size.** Validation predictions of the six runs (best weights), summed per 6 km block.
   For `n` in 10, 20, ..., 400 blocks, 1,000 bootstrap draws of `n` blocks with replacement (seed
   42); the spread of macro Dice is the standard deviation across draws, averaged over the six
   runs. Test size = the smallest `n` whose spread is at most `s`.
4. **Validation size.** Same, but on the difference between the two `lr` values of each adjacent
   pair (0.0001 vs. 0.0003, 0.0003 vs. 0.001) with the same seed, scored on the same drawn blocks.
   Validation size = the smallest `n` whose spread of the difference is at most `s`.
5. **Final split.** Test = the test size in blocks drawn from the reserve (seed 42); the reserve
   blocks left over go to training. Validation = the validation size in blocks drawn from the pool
   (seed 42); the rest of the pool is training. If a size exceeds the blocks available, all of them
   are used and the precision reached is reported. If a class has less than 10% of its tiles (by
   center class) in validation or in test, the draw is repeated with seed 43, 44, ... and the
   number of draws is reported.
6. **Learning curve.** `lr` 0.0003, batch 16, tile 96, with the patience of rule 2, on 25%, 50%,
   75% and 100% of the provisional training blocks (nested, seed 42), seeds 42 and 1, scored on the
   provisional validation. If the mean at 100% beats the mean at 75% by more than `s`, more tiles
   are extracted before the selection.
7. **Random Forest sample size.** 500 trees, no depth limit, `max_features` "sqrt", per-tree
   bootstrap of 25,000, 50,000, 100,000, 200,000 and 400,000 cells, seeds 42 and 1, provisional
   split. Its seed noise `s_rf` is pooled the same way. Sample size = the smallest whose mean is
   within `s_rf` of the best mean.

## Results

Run 2026-10-20 on the M4 (MPS), `results.json` and MLflow `phase1-unet-pilot`. Provisional split:
1,251 train tiles, 326 validation tiles (164 blocks).

| Run | Best val macro Dice | Best epoch / 100 |
|---|---|---|
| lr 0.0001, seeds 42 / 1 | 0.8149 / 0.8066 | 70 / 100 |
| lr 0.0003, seeds 42 / 1 | 0.8267 / 0.8223 | 92 / 47 |
| lr 0.001, seeds 42 / 1 | 0.8256 / 0.8270 | 97 / 71 |

- Seed noise `s` = 0.0039.
- Rule 1: three runs peaked in the last 10 epochs, cap raised to 300.
- Rule 2: patience 20.
- Rule 3: no size up to 400 blocks reaches a spread of `s` (0.0068 at 400). The reserve has 196
  blocks, all used for test: spread 0.0099 at that size.
- Rule 4: validation needs 390 blocks (spread of the difference 0.0038).
- Rule 5: draw seed 42 met the 10% rule at once. Train 829, validation 748, test 363 tiles.
  Amendment (2026-10-20, after the run): the 10% floor has no source. The split used by the
  selection is drawn again by `38_unet_selection.py split` with a stratification rule that does
  (see `data/study_area/unet_selection/README.md`); this pilot's `final_split.json` stays as the
  record of what rule 5 produced.
- Rule 6: learning curve 0.7920 / 0.8026 / 0.8153 / 0.8245 at 25 / 50 / 75 / 100%; 100% beats
  75% by 0.0092 > `s`, so more tiles are needed. An inverse power law fit (Figueroa et al., 2012)
  degenerates to a straight line in log(n): about +0.016 per doubling, no plateau in sight.
- Rule 7: RF means 0.8211 / 0.8212 / 0.8207 / 0.8201 / 0.8189, `s_rf` = 0.0003, sample size
  25,000.
- Time: 18.3 min per 100-epoch run at 96 px with 1,251 train tiles (about 11 s per epoch,
  validation included).
