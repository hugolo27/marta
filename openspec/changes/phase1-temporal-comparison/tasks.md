## 1. Persist a reusable trained CNN checkpoint

- [ ] 1.1 Add a checkpoint save/load path to `scripts/10_train_cnn.py`'s `train()` flow (or a thin wrapper), verified by training once with seed 42 and confirming a `.pt` file is written and reloadable into a fresh `SmallCNN` instance producing identical predictions on a held-out batch
- [ ] 1.2 Train the reference checkpoint once (seed 42, matching the seed already used as the reference throughout `phase1-classifier`) and verify its test-split accuracy matches the already-reported single-run numbers (`phase1-classifier` task 3.3) before using it for anything downstream

## 2. Dense per-date classification over the AOI

- [ ] 2.1 Build the 2019 and 2023 Sentinel-2 composites for the case-study AOI (`reproject=True`, `clip=True` per design.md), verified by confirming 0% residual cloud gap or an explicit reported gap fraction, not a silent assumption
- [ ] 2.2 Run dense CNN inference (reusing `13_visualize_classification_map.py`'s row-chunked sliding-window approach) over each date's composite using the persisted checkpoint from 1.2, verified by producing one per-pixel class raster per date covering the full AOI extent
- [ ] 2.3 Mark pixels with no valid observation in either date as unclassified rather than imputing a class, verified by confirming the raster has an explicit no-data value distinct from the 3 real classes

## 3. Change map and transition statistics

- [ ] 3.1 Diff the two per-date rasters into a change map labeling every valid pixel as no-change or one of the 6 named pairwise transitions, verified by confirming every valid pixel gets exactly one label and unclassified pixels propagate to unclassified in the change map
- [ ] 3.2 Compute and report hectares per transition type from the change map's pixel counts, verified by cross-checking the total (all transitions + no-change + unclassified) equals the AOI's known total area within rounding
- [ ] 3.3 Produce a visualization of the change map (e.g. a categorical map with one color per transition type plus no-change), verified by visual inspection against the true-color composites for a handful of hand-picked pixels with an obvious real transition (e.g. a known cleared area)

## 4. Independent sanity check

- [ ] 4.1 For the same AOI pixels, extract MapBiomas' own classification for both 2019 and 2023 and compute its own transition label per pixel, verified by producing a raster in the same encoding as 3.1
- [ ] 4.2 Report the agreement rate between the change map's detected transitions and MapBiomas' own detected transitions, verified by a per-transition-type agreement table (not just one overall number), with an explicit note if a specific transition type shows notably low agreement (a candidate sign of classifier noise rather than real change, per design.md)
