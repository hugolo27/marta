# U-Net pilot 3: all tiles, with a buffer (phase1-segmentation task 3.5)

Pre-registered before any run: everything above "## Results" is hashed and logged to MLflow
(`phase1-unet-pilot3`), and `scripts/37_unet_pilot.py --pilot3` refuses to run if it changed.
This README also fixes, now, every rule left for the final split, the selection and the test, so
that no later step is designed after seeing a result. A change after this hash is a dated
amendment under "## Results", with its reason.

## Why a third pilot

- The first pilot's learning curve was still climbing (`../unet_pilot/README.md`, rule 6), so a
  second batch of tiles was extracted (task 3.4): now 3,852 tiles, pool 3,165, reserve 687 (333
  blocks).
- Tiles of different 6 km blocks can sit closer than the autocorrelation range, and pool tiles
  were only kept off reserve tiles by the tile diagonal (2.7 km). In the first pilot 75 pairs of
  training and validation tiles had centers closer than that, so they could share ground, and its
  validation was mildly optimistic. Pilot 3 adds a buffer.
- Two code fixes since the first pilot (commit 4ed0ce0): a class absent from both labels and
  predictions is left out of macro Dice instead of scoring 1, and validation scores the whole
  192 px tile.

## Buffer

A tile is left out if any of its pixels lies within the autocorrelation range of a pixel of a
tile in a split it must be kept apart from (Roberts et al., 2017):

- Range: the largest practical range of the four semivariograms, 5,161 m
  (`../spatial_autocorrelation/results.json`; practical range = distance at 95% of the sill). The
  largest of the four, as for the block side. Read from that file by `dataset_loader`, not rounded.
- Distance: edge to edge between tile footprints, each drawn in its own UTM zone with its
  corners moved to UTM 21S (`dataset_loader.tiles_near`).
- Order: first pool tiles near any reserve tile are left out; then the validation blocks are
  drawn from what is left; then training tiles near any validation tile are left out.

Provisional split with this buffer (pool shuffled by 6 km blocks with seed 42, 20% of the blocks
to validation, as in the first pilot): 727 pool tiles left out near the reserve, 384 training
tiles left out near validation; 1,552 training tiles, 502 validation tiles in 229 blocks.

## Runs and rules

The first pilot's runs and rules 1, 2, 3, 4, 6 and 7, unchanged except for the following:

- Tiles: every batch (3,852), with the buffer above.
- Validation predictions saved for the bootstrap are whole 192 px tiles, the cells the selection
  scores.
- Rule 3 (test size): the test is the whole reserve (333 blocks), fixed when the tiles were built;
  the size needed and the spread at 333 blocks are reported, not used to choose anything.
- Rules 3 and 4, absent classes: the number of bootstrap draws with no labeled cell of some class
  (cultivo, in practice) is reported for each size, out of 6,000 draws for rule 3. In those draws
  macro Dice averages the classes present.
- Rule 4 (validation size), cap: if the measured size exceeds the provisional validation's 229
  blocks, 229 are used and the spread reached is reported. Reason: with the buffer, a larger
  validation takes tiles away from training (390 blocks would leave about 1,050), and the
  patience, epoch cap and Random Forest sample size are measured here with 1,552 training tiles;
  the selection should not train on fewer than the pilot measured on. The 20% itself has no
  source; the cap is our convention.
- Rule 5 (final split) is dropped: the final split is drawn by `38_unet_selection.py split`
  (below).
- Rule 6 (learning curve), on the provisional training tiles after the buffer. Stopping rule: if
  100% still beats 75% by more than `s`, one more batch is extracted (`35_assemble_tiles.py
  --batch 3`, seed 44) and this pilot is run again on all tiles under this same README, in
  `unet_pilot3/batch3/`. After that, whatever the curve says, the selection goes ahead and a
  curve still climbing is reported as a limitation. Fractions 25, 50, 75 and 100% are kept from
  the first pilot; they are a convention.

## Rules fixed now for the steps after this pilot

- Final split (`38_unet_selection.py split`): test = every reserve block; the buffer above between
  pool and test; validation = the validation size of rule 4 (with its cap) in pool blocks, best of
  100 draws by labeled cells per class as in `../unet_selection/README.md`; then the buffer
  between training and validation. Tiles left out by the buffer are marked "buffer" and used by
  no step.
- Selection: as written in `../unet_selection/README.md` (grid, 5 seeds, edge rule, rerun near
  the cap, Random Forest grid, comparison by pooled standard deviation), with the inputs from this
  pilot. Early stopping scores the whole 192 px validation tile. The test trains each selected
  U-Net with the epoch cap its selection ended with (3 times the cap if it was re-run near it).
- Test: once, after the decision; its result is used for nothing else.

## Results

Run 2026-10-22 on the M4 (MPS), `results.json`, `pilot3.log` and MLflow `phase1-unet-pilot3`. The
pre-registration hash was checked before the run. Provisional split: 1,552 train tiles, 502
validation tiles (229 blocks); 727 pool tiles left out near the reserve, 384 near validation.

| Run | Best val macro Dice | Best epoch / 100 |
|---|---|---|
| lr 0.0001, seeds 42 / 1 | 0.7746 / 0.7889 | 36 / 29 |
| lr 0.0003, seeds 42 / 1 | 0.8002 / 0.7990 | 67 / 60 |
| lr 0.001, seeds 42 / 1 | 0.7977 / 0.7899 | 80 / 31 |

- Seed noise `s` = 0.0067 (0.0039 in the first pilot).
- Rule 1: no run peaked in the last 10 epochs, cap stays at 100.
- Rule 2: patience 24.
- Rule 3: test needs 400 blocks; the reserve has 333, all used, spread 0.0075 at 330 blocks.
- Absent classes: 7 of 6,000 draws of 10 blocks had no cultivo cell; none from 20 blocks up.
- Rule 4: validation needs 150 blocks (spread of the difference 0.0066), under the 229-block cap,
  so the cap does not apply.
- Rule 6: learning curve 0.7525 / 0.7740 / 0.7785 / 0.7996 at 25 / 50 / 75 / 100%; 100% beats 75%
  by 0.0211 > `s`, so more tiles are needed: by the stopping rule, one more batch, then this pilot
  again in `batch3/`. The 100% runs repeat the `lr` 0.0003 runs exactly (same tiles, seed and
  weights; the patience of 24 stops them after their best epoch).
- Rule 7: RF means 0.7998 / 0.7987 / 0.7968 / 0.7951 / 0.7934, `s_rf` = 0.0006, sample size
  25,000.
- Scores are about 0.025 below the first pilot's (best U-Net 0.800 vs 0.827, RF 0.800 vs 0.821),
  consistent with the buffer removing the train-validation proximity, though the tiles and the
  metric fixes also changed.
- Time: about 40 min per 100-epoch run at 96 px (18 min in the first pilot: more training tiles
  and whole-tile validation); 7 h of U-Net training in all, plus the Random Forest.

### After the third batch (`batch3/`)

Run 2026-10-22 19:53 to 2026-10-23 05:18 on the M4 (MPS), `batch3/results.json`,
`batch3/pilot3_batch3.log` and MLflow `phase1-unet-pilot3` (`pilot_val20_batch3`), under the same
hash. Batch 3: 2,004 points, 107 dropped for overlap, 1,897 tiles; now 5,749 tiles, reserve 986
in 443 blocks. Provisional split: 1,333 pool tiles left out near the reserve, 781 near
validation; 1,967 training tiles, 682 validation tiles in 291 blocks.

| Run | Best val macro Dice | Best epoch / 100 |
|---|---|---|
| lr 0.0001, seeds 42 / 1 | 0.8078 / 0.8098 | 79 / 43 |
| lr 0.0003, seeds 42 / 1 | 0.8169 / 0.8136 | 67 / 82 |
| lr 0.001, seeds 42 / 1 | 0.8172 / 0.8157 | 83 / 54 |

- Seed noise `s` = 0.0017.
- Rule 1: no run peaked in the last 10 epochs, cap stays at 100.
- Rule 2: patience 16.
- Rule 3: no size up to 400 blocks reaches `s` (spread 0.0068 at 400); the test is the whole
  reserve, 443 blocks.
- Absent classes: 3 of 6,000 draws of 10 blocks had no cultivo cell; none from 20 blocks up.
- Rule 4: no size up to 400 blocks reaches `s` (spread of the difference 0.0034 at 400, 0.0041 at
  290), so the cap applies: 291 blocks, all of the provisional validation.
- Rule 6: learning curve 0.7723 / 0.7968 / 0.8072 / 0.8152 at 25 / 50 / 75 / 100%; 100% beats 75%
  by 0.0080 > `s`. By the stopping rule no further batch: the selection goes ahead and the
  still-climbing curve is reported as a limitation.
- Rule 7: RF means 0.8126 / 0.8122 / 0.8091 / 0.8073 / 0.8050, `s_rf` = 0.0007, sample size
  25,000.
- Time: about 53 min per 100-epoch run at 96 px; 9 h 25 min in all.
- Amendment (2026-10-23, after the run): rule 4's cap names "the provisional validation's 229
  blocks", the count of the run before the third batch. Its stated reason (the selection trains
  on no fewer tiles than the pilot measured on) points to the provisional validation of the run
  whose decisions are used, 291 blocks here, which is what the code applies.
- Note (2026-10-26): the U-Net and RF figures above are not on the same cells. The U-Net is scored
  on whole 192 px tiles (`predict_counts_full`), the RF on the 96 px centre
  (`predict_counts_tiles`), so they only feed rules 1-7 and do not compare the two models. On the
  same 192 px cells (seeds 42 and 1, U-Net `lr` 0.001) they tie: macro Dice RF 0.818, U-Net
  0.817; bosque 0.947 / 0.945, pasto 0.841 / 0.833, cultivo 0.665 / 0.672. The selection
  (`38_unet_selection.py`) scores both on whole tiles.
