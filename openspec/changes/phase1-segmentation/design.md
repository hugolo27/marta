## Context

See proposal.md. Current state (phase1-dataset-v2): 5,993 patches of 33x33x26 with one label each, 6 km blocks, operational CNN 3x3 dry+wet (test 0.865) and RF dry+wet (0.841).

## Goals / Non-Goals

**Goals:**
- A U-Net that uses spatial context, measured against MapBiomas at its own 30 m resolution.
- No value without a source, a measurement or a geometric reason (D0).

**Non-Goals:** see proposal.md.

## Decisions

### D0. Where every value comes from

| Value | Choice | Basis |
|---|---|---|
| Tile size | 48, 96 or 192 px, chosen on validation | Multiple of 3 (MapBiomas grid) and of 16 (four halvings); Sentinel-2 U-Nets use up to 512 px (John and Zhang, 2022) |
| Depth | downsample until the map would drop below 4 px (4 levels at 96 px) | Isensee et al. (2021) |
| Filters | 32, doubled per level | Isensee et al. (2021) |
| Loss | cross-entropy + Dice | Isensee et al. (2021); Dice loss, Milletari et al. (2016) |
| Ignored pixels | MapBiomas classes outside the three | Cordts et al. (2016) |
| Optimizer, `lr` | Adam; 0.0001, 0.0003, 0.001 | Kingma and Ba (2014); John and Zhang (2022) |
| Batch | 8, 16, 32 | Minimum 2 and at most 5% of the data (Isensee et al., 2021); chosen on validation |
| Dropout | none | Isensee et al. (2021); John and Zhang (2022) |
| Augmentation | 90 degree rotations and flips | Isensee et al. (2021) |
| Patience | measured in the pilot (D4) | Early stopping on validation, Prechelt (1998) |
| Split sizes | measured in the pilot (D4) | Xu and Goodacre (2018): the estimate depends on the split |
| Number of tiles | learning curve (D4) | Ning et al. (2020) |
| RF per-tree sample | learning curve (D4) | Bagging trains each tree on a bootstrap sample; its size is measured, not fixed |
| Blocks | 6 km | Semivariogram, phase1-dataset-v2 D1 |
| Seeds, rule | 5 seeds, pooled std | Henderson et al. (2018); Cohen's d > 1 (Cohen, 1988) |
| Grad-CAM | Seg-Grad-CAM | Vinogradova et al. (2020) |

### D1. Tiles
- Points sampled as in phase1-dataset-v2 (stratified on the MapBiomas class of the center pixel, seed 42, 2019 and 2023), but a point is kept only if its whole 192 px tile (1.92 km) lies outside every held-out region.
- 2,000 tiles in total (the upper end of the learning curve in D4), split evenly by center class and year.
- Image: dry + wet composites, 26 channels, on Sentinel-2's own UTM 10 m grid (the zone of the tile center), with tile edges at multiples of 30 m, which are also native 10 m pixel edges, so the 10 m bands are not resampled. Stored as int16 (bands as delivered; NDVI x 10,000).
- Labels: MapBiomas resampled by nearest neighbour onto the 30 m grid of the same tile (64x64), remapped to bosque, pasto, cultivo and 0 for any other class. Each label cell covers exactly 3x3 image pixels.
- Why not the reverse (image onto MapBiomas' grid): MapBiomas is in EPSG:4326 at 0.000269 degrees, about 30 m north-south but 27-28 m east-west in the Chaco (cos of latitude at 19-25 degrees south), so a grid nested in it would resample every reflectance onto non-square pixels, and the model would later classify native Sentinel-2 that looks different. Checked on 5 tiles (task 1.1).
- Quality checks as in phase1-dataset-v2: no-data per composite; a tile with more than 5% no-data pixels is dropped.

### D2. Splits
- Final split (after the pilot): test = every reserve block, validation = the pilot's size in pool blocks, rest training. Of 100 random draws (blockCV's default, Valavi et al., 2019), the one whose share of each class's labeled 30 m cells in validation is closest to validation's share of all labeled cells (stratification, Kohavi, 1995; cells rather than center class, since Dice is scored on cells). Replaces a "10% of each class" floor that had no source.
- Same 6 km blocks, assigned regardless of class. The minimum distance between tiles of different splits becomes the tile diagonal (192 px: 2.7 km), so no two tiles of different splits share ground.
- The split proportions come from the pilot (D4), not from 70/15/15.

### D3. Model and metric
- U-Net with two convolutions per level, instance normalization and leaky ReLU (Isensee et al., 2021), input normalized per channel with train-split statistics stored in the checkpoint (as in phase1-dataset-v2 D4b).
- The 10 m class probabilities are averaged over each 3x3 block; loss and metrics are computed on the 30 m map. Ignored pixels contribute to neither.
- Metric: Dice per class and its mean (macro Dice) at 30 m.
- RF baseline: one example per 30 m pixel, features = the mean of the 26 channels over its 3x3 block, trained on the labeled pixels of the training tiles with the existing RF grid.

### D4. Pilot (training and validation only)
- 20% of the blocks are set aside as the test reserve before anything is trained; the pilot never reads them.
- On the remaining blocks, a provisional train/validation split. Three configurations (center of the grid and the two `lr` extremes, 96 px, batch 16) × 2 seeds, trained to the epoch cap without early stopping, validation macro Dice recorded every epoch.
- **Patience:** the smallest patience that, in every pilot run, loses less than the seed-to-seed standard deviation against the best epoch.
- **Split sizes:** bootstrap over 6 km blocks of the pilot's validation predictions; the test size is the smallest number of blocks whose macro Dice spread falls below the seed-to-seed standard deviation, the validation size the smallest whose spread of the difference between two configurations does. Test takes its blocks from the reserve; any left over go to training.
- **Learning curve:** the center configuration trained on 25%, 50%, 75% and 100% of the training tiles. If the last step still gains more than the seed-to-seed standard deviation, more tiles are extracted before the selection.
- **Random Forest sample size:** 5.5 million labeled cells do not fit a 500-tree forest in reasonable time, so each tree is trained on a bootstrap of 25,000 to 400,000 cells; the smallest size within the RF seed noise of the best one is kept.
- Seed noise is the pooled sample standard deviation of the best validation macro Dice across 2 seeds, over the 3 `lr` values. The provisional split is 80/20 of the pool's blocks, used only by the pilot.
- The pilot's models are discarded. Its rule is written and hashed before it runs: `data/study_area/unet_pilot/README.md`.
- **Sensitivity of the provisional split (pilot 2).** The 80/20 has no source, so the pilot's runs and decisions (seed noise, patience, split sizes, learning curve) are repeated with 50/50, 90/10 and 95/5 on the same 1,940 tiles. The four ratios are the fold counts Kohavi (1995) compares (k = 2, 5, 10, 20); 80/20 is also blockCV's default k = 5 (Valavi et al., 2019). If the decisions do not change, the 80/20 result stands; if they do, the spread is reported. Rule written and hashed before it runs: `data/study_area/unet_pilot_sensitivity/README.md`.
- **Tile count.** 2,000 tiles (about 2 million labeled cells at 96 px) was a starting point, not a sourced value: the number is set by measurement, with the learning curve (Ning et al., 2020). The curve still climbed (+0.009 > `s` from 75% to 100%), so a second batch of about 2,000 doubles it and the curve is measured again, together with the validation size (the same block bootstrap on the curve's 100% runs, since blocks will hold more tiles); doubling is a convention, since an inverse power law fit (Figueroa et al., 2012) found no plateau to extrapolate to.

### D5. Selection (pre-registered)
- Grid: tile {48, 96, 192} × `lr` {0.0001, 0.0003, 0.001} × batch {8, 16, 32}, 5 seeds (42, 1, 7, 123, 2026), `ddof=1`. Selected configuration: highest mean validation macro Dice; ties go to the smaller tile, then the larger batch.
- Edge rule, both directions on every axis, once: `lr` 0.00003 or 0.003, batch 4 or 64. Tile 48 cannot go lower (the U-Net would have fewer than 4 levels at 4 px); tile 192 winning triggers an extraction at 288 px. Basis: a best point near the boundary of the search space suggests a better one beyond it (Godbole et al., 2023, practitioner guide); the step repeats the grid spacing (x3 `lr`, x2 batch), a convention.
- U-Net vs. RF on validation: the U-Net counts as better only if its macro Dice beats RF's by more than their pooled standard deviation. Which one becomes operational follows the existing requirement "Operational classifier selection".
- Written in `data/study_area/unet_selection/README.md` above `## Results`, hashed and logged to MLflow before scoring. Test once after the decision.

### D6. Cascade
- AOI and development area 2019-2023 classified by overlapping tiles (half-tile overlap, probabilities averaged), then the change-map rule as before.
- Held-out regions re-run at 30 m against MapBiomas.
- Grad-CAM for segmentation (Vinogradova et al., 2020): the gradient of the class score summed over a region of the output.
- Redrawn AOI reference sample, as in phase1-dataset-v2.

## Risks / Trade-offs

- **Labels are resampled, not the image.** A 30 m UTM cell takes the MapBiomas pixel under its center; MapBiomas pixels are 27-28 m wide east-west, so now and then one is skipped or repeated along a row. The same approximation was already in the patch dataset ("one MapBiomas pixel = 3x3 Sentinel-2 pixels" holds north-south, not exactly east-west).
- **Compute.** Unknown until the pilot; measured there and reported before the grid.
- **Labels are MapBiomas.** Dice measures agreement with MapBiomas; accuracy against the ground still comes from the reference samples.
- **Rare classes.** Cultivo covers few pixels outside its tiles; Dice in the loss and class-stratified tile centers mitigate it, and per-class Dice is reported.

## References

- Cohen, J. (1988). Statistical power analysis for the behavioral sciences (2nd ed.). https://doi.org/10.4324/9780203771587
- Cordts, M., et al. (2016). The Cityscapes dataset for semantic urban scene understanding. CVPR. https://doi.org/10.1109/CVPR.2016.350
- Godbole, V., Dahl, G. E., Gilmer, J., Shallue, C. J., and Nado, Z. (2023). Deep Learning Tuning Playbook. Google Research. https://github.com/google-research/tuning_playbook
- Henderson, P., et al. (2018). Deep reinforcement learning that matters. AAAI 32(1). https://doi.org/10.1609/aaai.v32i1.11694
- Isensee, F., et al. (2021). nnU-Net. Nature Methods 18, 203-211. https://doi.org/10.1038/s41592-020-01008-z
- John, D., and Zhang, C. (2022). An attention-based U-Net for detecting deforestation within satellite sensor imagery. JAG 107, 102685. https://doi.org/10.1016/j.jag.2022.102685
- Kingma, D. P., and Ba, J. (2014). Adam. arXiv:1412.6980.
- Kohavi, R. (1995). A study of cross-validation and bootstrap for accuracy estimation and model selection. IJCAI 14, 1137-1145. https://mlanthology.org/ijcai/1995/kohavi1995ijcai-study
- Milletari, F., et al. (2016). V-Net. 3DV, 565-571. https://doi.org/10.1109/3DV.2016.79
- Ning, H., et al. (2020). Choosing an appropriate training set size. Annals of GIS 26(4), 329-342. https://doi.org/10.1080/19475683.2020.1803402
- Prechelt, L. (1998). Early stopping - but when? LNCS 1524, 55-69. https://doi.org/10.1007/3-540-49430-8_3
- Ronneberger, O., et al. (2015). U-Net. MICCAI, 234-241. https://doi.org/10.1007/978-3-319-24574-4_28
- Valavi, R., et al. (2019). blockCV. Methods in Ecology and Evolution 10(2), 225-232. https://doi.org/10.1111/2041-210X.13107
- Vinogradova, K., et al. (2020). Towards interpretable semantic segmentation via gradient-weighted class activation mapping. AAAI 34(10), 13943-13944. https://doi.org/10.1609/aaai.v34i10.7244
- Xu, Y., and Goodacre, R. (2018). On splitting training and validation set. J. Anal. Test. 2, 249-262. https://doi.org/10.1007/s41664-018-0068-2
