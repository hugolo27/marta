# U-Net pilot 2: sensitivity of the provisional split (phase1-segmentation task 3.3)

Pre-registered before any run: everything above "## Results" is hashed and logged to MLflow
(`phase1-unet-pilot-sensitivity`), and `scripts/37_unet_pilot.py --val-share X` refuses to run if
it changed.

## Question

The first pilot (`../unet_pilot/README.md`) split the pool 80% train / 20% validation. That share
has no source. Do its decisions change with another share?

## Data

The same 1,940 tiles as the first pilot (batch 1 of `../tiles/manifest.csv`), pool group only.
Tiles of the second batch are not read.

## Runs

The first pilot's runs and rules 1 to 7, unchanged, with the provisional validation share set to
50%, 10% and 5% of the pool blocks (same seed-42 shuffle). With the 80% / 20% split already run,
these are the fold counts k = 2, 5, 10 and 20 compared by Kohavi (1995). Each share writes to its
own folder (`val50/`, `val10/`, `val5/`) and to its own MLflow run.

Provisional splits (tiles, validation blocks): 50% 787 train / 790 val (410 blocks); 10% 1,428 /
149 (82 blocks); 5% 1,509 / 68 (41 blocks).

## Comparison

For each share, the decisions of the first pilot are listed next to the 80/20 ones: seed noise
`s`, epoch cap, patience, test and validation sizes in blocks, learning curve and whether more
tiles are needed, Random Forest sample size. If none changes, the 80/20 result stands. If some
change, the 80/20 result is still the one used (design, "Sensitivity of the provisional split")
and the range across the four shares is reported.

## Results

Run 2026-10-21 on the M4 (MPS), `val50/`, `val10/`, `val5/results.json` and MLflow
`phase1-unet-pilot-sensitivity`. The pre-registration hash was checked before each run.

| Train / val | Tiles (blocks in val) | `s` | Cap | Patience | Val blocks | Test blocks | Curve 25 / 50 / 75 / 100% | More tiles | RF sample |
|---|---|---|---|---|---|---|---|---|---|
| 80 / 20 (pilot 1) | 1,251 / 326 (164) | 0.0039 | 300 | 20 | 390 | > 400 | 0.792 / 0.803 / 0.815 / 0.825 | yes | 25,000 |
| 50 / 50 | 787 / 790 (410) | 0.0034 | 100 | 24 | > 400 | > 400 | 0.759 / 0.787 / 0.803 / 0.810 | yes | 50,000 |
| 90 / 10 | 1,428 / 149 (82) | 0.0079 | 300 | 21 | 100 | 300 | 0.791 / 0.805 / 0.810 / 0.818 | yes | 50,000 |
| 95 / 5 | 1,509 / 68 (41) | 0.0103 | 100 | 17 | 80 | 160 | 0.773 / 0.782 / 0.786 / 0.807 | yes | 200,000 |

- The decision that matters for the next step, whether more tiles are needed, is the same under
  all four shares, so the second batch (task 3.4) does not depend on the 80/20 choice.
- The other decisions move, and as pre-registered the 80/20 ones are kept and the range is
  reported: patience 17 to 24, epoch cap 100 or 300, Random Forest sample 25,000 to 200,000 (its
  means differ by less than 0.001 across sample sizes in every share).
- Seed noise grows as validation shrinks (0.0034 with 410 blocks, 0.0103 with 41), as expected from
  scoring on fewer blocks. The validation and test sizes are measured against each share's own
  `s`, so the smaller shares, with a larger `s`, need fewer blocks; those sizes are not comparable
  across shares.
- Amendment (2026-10-21, during the 95/5 run): the run stopped at rule 5 because no draw met the
  10% floor, which had already been replaced (see `../unet_pilot/README.md`, rule 5 amendment).
  `37_unet_pilot.py` now records the miss (`final_split_seed` null) instead of stopping, and the
  95/5 run resumed from its six stored runs. The 80/20, 50/50 and 90/10 runs met the floor and are
  unaffected.
- Time: 147 to 193 minutes of training per share.
