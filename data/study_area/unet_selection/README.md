# U-Net selection (phase1-segmentation D5)

Pre-registered after the pilot and before any configuration is scored: everything above
"## Results" is hashed and logged to MLflow (`phase1-unet-selection`), and
`scripts/38_unet_selection.py` refuses to score if it changed. Its rules were already fixed by
pilot 3's pre-registration (`../unet_pilot3/README.md`, "Rules fixed now"); this README only
restates them.

## Inputs fixed by the pilot

From `data/study_area/unet_pilot3/batch3/results.json` ("decisions", pilot 3 after the third batch): the validation size in 6 km blocks
(rule 4, capped at the provisional validation's blocks),
the epoch cap, the early-stopping patience and the Random Forest's per-tree sample size. Nothing
else from the pilot is reused; its models were discarded.

## Split

`38_unet_selection.py split`, run before this README is hashed: tiles within the autocorrelation
range (5,161 m, edge to edge) of a held-out region (added 2026-11-10), of the case-study AOI
(added 2026-11-12) or of the change-map development area (added 2026-11-13) are left out (design D2);
test = every block of the reserve; pool tiles within that range of a test tile are left out;
validation = the pilot's validation size in blocks of the remaining pool; training tiles within
that range of a validation tile are left out; the rest is training. Tiles left out are marked
"buffer" and used by no step (Roberts et al., 2017; design D2). 100 random
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
  7, 123, 2026), `ddof=1`. Early stopping on validation macro Dice, scored on the whole 192 px
  tiles, with the pilot's patience; best weights kept.
- Training draws one window of the configuration's tile size per tile and epoch, anywhere on the
  tile's 30 m grid, with channel statistics over the whole training tiles, so every tile size
  trains on all the labeled cells of the training tiles and the grid compares context, not amount
  of data (nnU-Net samples its training patches the same way, Isensee et al., 2021). The pilots
  trained on the 96 px center crop; their patience and epoch cap are reused as measured.
- Every configuration is scored on the whole 192 px validation tiles at 30 m, by windows of its own
  tile size with half-window overlap, so all configurations and the Random Forest are scored on
  the same cells.
- Selected configuration: the highest mean validation macro Dice. Ties go to the smaller tile, then
  the larger batch.
- Edge rule, once: if the selected `lr` is 0.0001 or 0.001, 0.00003 or 0.003 is added; if the
  selected batch is 8 or 32, 4 or 64 is added; each with the other two values fixed at the
  selection, and the selection is redone. Tile 48 cannot go lower (fewer than 4 px at the bottom
  level). If tile 192 is still selected after that, scoring stops before the selection is saved:
  tiles of 288 px are extracted around the same centers, the buffer is recomputed on their
  footprints (tiles it drops are left out of the 288 px runs only, and counted), the 288 px
  configuration is scored on the same 192 px cells as the others, and that value is added. Basis:
  a best value at the boundary of the search space suggests a better one beyond it (Godbole et
  al., 2023, Deep Learning Tuning Playbook, Google Research; a practitioner guide, not peer
  reviewed). The step size repeats the grid's own spacing (x3 for `lr`, x2 for batch) and is our
  convention.
- A configuration whose best epoch is within 10 epochs of the cap in any seed (epoch 90 or later
  with a cap of 100) is re-run with three times the cap.

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
  is used for nothing else. The U-Net is trained with the epoch cap its selection ended with (3
  times the pilot's if it was re-run near the cap).

## Hardware

- Every training of the selection and of the test runs on one device model, because PyTorch does
  not guarantee the same result for the same seed on different platforms (PyTorch documentation,
  "Reproducibility"), and a gap between configurations has to come from the configurations, not
  from the machine. `score` saves the device in `results.json` on its first run, and `score` and
  `test` stop if they find another one, so an interrupted session resumes only on the same model.
  If that model stops being available, every run done on it is discarded and the selection starts
  again on the new one; runs from two devices are never mixed. The Random Forest runs in the same
  process and follows the same rule.

## Results

Run 2026-11-18 02:04 to 2026-11-20 14:56 UTC on molab (NVIDIA RTX PRO 6000 Blackwell Server
Edition, PyTorch 2.11.0, CUDA 13.0), commit `0726a48`, under the hash above, through
`notebooks/molab_selection.py`. `results.json` (grid, edge rule, decision and test),
`test_runs.json` (test runs as they ended) and `sessions.json` (every molab session) come from the
`molab-state` branch. The seed 42 checkpoint is `unet_checkpoint.pt` on that branch (`*.pt` is
not versioned here), sha256 `eec2fb794861ade7640fe1497deb59ea784e14dba37c534f6fffb9cf3ab16fa9`.

### Selection (validation)

| Model | Configuration | Val macro Dice |
|---|---|---|
| U-Net, best of 48 px | lr 0.001, batch 32 | 0.8277 ± 0.0024 |
| U-Net, runner-up | 48 px, lr 0.0003, batch 32 | 0.8277 ± 0.0020 |
| U-Net, best of 96 px | | 0.8232 |
| U-Net, best of 192 px | | 0.8205 |
| Random Forest | 500 trees, no depth limit, `max_features` 0.5 | 0.8145 ± 0.0002 |

- 27 grid configurations and 18 Random Forest configurations, 5 seeds each. The best two U-Nets
  differ by 0.00002; the rule takes the higher mean.
- Epoch cap: 12 grid configurations and the batch 64 edge peaked near the cap of 100 and were
  re-run with 300, the selected one among them.
- Edge rule: lr 0.001 and batch 32 are grid edges, so lr 0.003 (0.8228) and batch 64 (0.8235)
  were run at 48 px; neither beat the selection. No 288 px tiles were needed.
- Comparison: U-Net minus Random Forest 0.0132, pooled standard deviation 0.0017, so the U-Net
  counts as better (`unet_better`).

### Test (once)

| Model | Test macro Dice | Bosque | Pasto | Cultivo |
|---|---|---|---|---|
| U-Net | 0.8159 ± 0.0104 | 0.948 | 0.870 | 0.630 |
| Random Forest | 0.8113 ± 0.0002 | 0.945 | 0.870 | 0.619 |

- U-Net per seed (42, 1, 7, 123, 2026): 0.8124, 0.8234, 0.8236, 0.8210, 0.7992. The difference,
  0.0047, is below the pooled standard deviation, 0.0074: on test the two are tied, against a
  clear gap on validation.
- Under the requirement "Operational classifier selection" of the `land-cover-classifier` spec, a
  tie makes the U-Net the operational classifier, because only it supports per-prediction
  Grad-CAM; the Random Forest stays as the baseline finding.

### How the test was run

- The test ran from the notebook, not as one `38 test` process, with the same calls on the same
  commit and device: the five U-Nets first, then the five Random Forests, each run pushed to
  `test_runs.json` as it ended and never rerun.
- The molab sandbox was reclaimed without an error whenever a Random Forest started next to the
  U-Net's cached tiles. Each Random Forest then ran in its own process, without the tile cache,
  limited to 8 threads (`LOKY_MAX_CPU_COUNT`) of the machine's 20 cores, after which it no longer
  failed. Neither the order nor the thread count changes a score: every run has its own seed and
  every tree its own seed. This departs from the Hardware rule's "same process" for the Random
  Forest, not from its device rule.
- `sessions.json` lists nine test sessions. The first two were reclaimed before any score was
  output or saved; the others resumed from the last pushed run.

### Repeating a seed

- The held-out regions are scored with the five seeds of the test, and the test kept only seed 42's
  checkpoint, so the other four were retrained (notebook mode `semillas`) on the same commit,
  device and configuration. Training on the GPU is not bit-for-bit deterministic, even with the
  same seed on the same device (PyTorch documentation, "Reproducibility"): the runs drift apart and
  early stopping ends them at different epochs. The Hardware rule removes differences between
  platforms, not this run-to-run variation.

| Seed | Test run | Retrained | Gap |
|---|---|---|---|
| 1 | 0.8234 | 0.8218 | -0.0016 |
| 7 | 0.8236 | 0.8210 | -0.0026 |
| 123 | 0.8210 | 0.8205 | -0.0005 |
| 2026 | 0.7992 | 0.8246 | +0.0254 |

- (A first retraining of seed 1, stopped by a stricter check that required identical scores, gave
  0.8215; its checkpoint was not kept.)
- Seed 2026, the lowest test run by far, comes out with the others when repeated: most of that run's
  gap was the run, not the seed. The U-Net's test spread (0.0104) is therefore driven largely by one
  unfavourable run, and the tie on test is a cautious result, not evidence that the U-Net is worse.
  The test result stays as pre-registered and run once: replacing a run after seeing it would be
  choosing the result. It does not change the operational classifier, which is the U-Net either way.
- The retrained checkpoints are new runs of the selected configuration, used only for the held-out
  regions; their test scores, measured only to quantify the gap, are in `retrained.json`. The test
  result above and the operational checkpoint (seed 42, sha256 eec2fb794861...) are the test's own.
