## 1. Tiles

- [x] 1.1 Check the tile grid on 5 tiles (one per class and year 2019, 192 px): image pixels against the composite sampled in the same projection and label cells against MapBiomas sampled natively at the cell center, verified by matching values and boundaries: B4 20/20 and labels 30/30 on every tile, no zero pixels, label boundaries on forest strips and field edges with no visible shift (`data/study_area/tiles/alignment_check/`). Native scenes have x and y offsets that are multiples of 10 m in both UTM 20S and 21S, so tile edges at multiples of 30 m keep the 10 m bands unresampled. Finding: MapBiomas is in EPSG:4326 (0.000269 degrees, 27-28 x 30 m in the Chaco), so design D1 resamples the labels onto Sentinel-2's grid, not the image onto MapBiomas'
- [x] 1.2 `35_assemble_tiles.py`: 2,000 tiles of 192x192x26 (int16) with 64x64 label maps, held-out exclusion of the whole tile, no-data check, 6 km blocks, test reserve of 20% of the blocks (D1, D2, D4), verified by tile counts per class and year, drop counts and no tile touching a held-out region: run 2026-10-20, 2,004 points sampled (334 per class and year), 64 dropped for sitting within the tile diagonal (2.7 km) of a tile of the other group, 0 dropped for gaps; 1,940 tiles (2.1 GB), pool 1,577 and reserve 363 (209 of 1,043 blocks; 16-21% of each center class). Label cells: bosque 49.1%, pasto 39.3%, cultivo 11.6%, other (ignored) 0.7%. Held-out exclusion by sampling outside each held-out rectangle grown by half the tile diagonal; checked afterwards from the tile corners: 0 of 1,940 tiles touch a held-out rectangle
- [x] 1.3 `dataset_loader.py`: tile loading with center crops to 96 and 48 px and label maps cropped to match, verified on a few tiles: crops equal the matching slice of the 192 px tile and label map at every size, NDVI back in [-1, 1], other classes served as `IGNORE`; also `tile_channel_stats` and `block_features` (RF at 30 m)

## 2. Model

- [x] 2.1 `36_train_unet.py`: U-Net (D3), normalization stored in the checkpoint, 3x3 averaging to 30 m, cross-entropy + Dice ignoring label 0, rotations and flips, verified by a forward pass at 48, 96 and 192 px and by overfitting a handful of tiles: 3, 4 and 5 levels with 1.9, 7.8 and 20.6 million weights; 8 tiles reach macro Dice 1.0 by step 150. Time per training tile and epoch (Apple M4): 20 ms at 96 px and 45 ms at 192 px on the GPU (MPS), 45 and 189 ms on the CPU, so training runs on MPS
- [x] 2.2 RF at 30 m (D3): `09_train_random_forest.train_tiles` and `predict_counts_tiles`, Dice counts shared in `classifier_report`, verified by one fit on 160 tiles (50,000 cells per tree, 15 s) scored on 40 others

## 3. Pilot

- [x] 3.1 Write the pilot rule (D4), hash it and log it to MLflow before any pilot run: `data/study_area/unet_pilot/README.md`, sha256 1d9f9545..., 2026-10-20 03:19 UTC, logged to `phase1-unet-pilot` before any pilot run (the script was smoke-tested on 120 tiles with 3 epochs in a scratch MLflow store, including a resume)
- [x] 3.2 `37_unet_pilot.py`: 6 runs without early stopping, patience, split sizes by block bootstrap, learning curve, verified by the recorded values and the time per epoch; report compute before the grid: ran 2026-10-20 on MPS, 18.3 min per 100-epoch run at 96 px. `s` = 0.0039, cap raised to 300, patience 20, validation 390 blocks, test needs more than 400 blocks so all 196 reserve blocks are used (spread 0.0099); split train 829, val 748, test 363 tiles. Learning curve 0.792 / 0.803 / 0.815 / 0.825, still climbing (+0.009 > `s`): more tiles needed before 4.1. RF sample size 25,000 (RF val macro Dice 0.821 vs best U-Net run 0.827). Detail in `data/study_area/unet_pilot/README.md`
- [x] 3.3 Pilot 2, sensitivity of the provisional split: write `data/study_area/unet_pilot_sensitivity/README.md` (50/50, 90/10, 95/5 on the same 1,940 tiles; Kohavi's k = 2, 10, 20), hash it and log it to MLflow before running; run and compare its decisions with the 80/20 pilot: sha256 1be8cd13..., logged 2026-10-21 before any run; `37_unet_pilot.py --val-share`, batch 1 only. All four shares say more tiles are needed; patience 17-24, cap 100 or 300, RF sample 25,000-200,000, so the 80/20 decisions are kept and the range reported. Seed noise 0.0034 (50/50) to 0.0103 (95/5). The 95/5 run stopped at the superseded 10% floor; the script now records the miss and the run resumed (amendment in the README)
- [ ] 3.4 (batch done 2026-10-21: `35_assemble_tiles.py --batch 2`, 2,004 points, 92 dropped for overlap, 0 for gaps, 1,912 tiles in 759 new blocks, 152 of them to the reserve; now 3,852 tiles, pool 3,165, reserve 687; existing tiles tagged batch 1 in `points.json` and `manifest.csv`. Learning curve on all tiles pending) Second batch of about 2,000 tiles with `35_assemble_tiles.py` (seed 43; existing blocks keep their group, new blocks 20% to the reserve), then the learning curve again on all tiles; repeat while it still climbs by more than `s`. The validation size (390 blocks, measured with about 2 tiles per block) is measured again with the same bootstrap on the curve's 100% runs, since blocks with more tiles may need fewer of them; no extra training

## 4. Selection and test

- [ ] 4.1 Final splits from the pilot (`38 split`: best of 100 draws stratified by labeled cells per class, replacing the unsourced 10% floor; on the current 1,940 tiles: seed 126, each class's cells in validation within 0.3 points of its 38.4% overall, train 832 / val 745 / test 363; the fixed test reserve has 12.5% of the cultivo cells against 18.7% overall; rerun after the second batch of tiles); write `data/study_area/unet_selection/README.md` (D5), hash it and log it to MLflow before scoring
- [ ] 4.2 `38_unet_selection.py`: grid, edge rule, U-Net vs. RF on validation, verified by every configuration in `results.json` and the decision
- [ ] 4.3 Test once with the selected models

## 5. Cascade

- [ ] 5.1 Tile-based classification in `18` and the held-out scripts, verified on a synthetic tile against direct predictions
- [ ] 5.2 Held-out regions, AOI and development area 2019-2023, change-map rule, Seg-Grad-CAM, redrawn AOI sample

## 6. Documentation

- [ ] 6.1 Thesis chapters 2 and 3, `docs/PHASE1_SUMMARY.md`, `docs/METODOLOGIA_PIPELINE.md`
- [ ] 6.2 `openspec validate phase1-segmentation --strict`, thesis compiles
