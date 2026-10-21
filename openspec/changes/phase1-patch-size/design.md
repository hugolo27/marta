## Context

See proposal.md for motivation. Relevant current state:

- Each training example is a 33x33x13 patch (12 Sentinel-2 L2A bands + NDVI) centered on the 3x3 block that one 30 m MapBiomas pixel covers. Split by ~2 km spatial blocks: train 1,673, val 361, test 359.
- `SmallCNN`: three 3x3 conv blocks (32, 64, 128 filters), max pooling after the first two (33 -> 16 -> 8), global average pooling, dropout, linear. Selected configuration: `lr` 0.0003, `dropout` 0.5, `batch_size` 16. Val macro-F1 0.844 ± 0.008 (5 seeds, `ddof=1`).
- RF on the central pixel: val 0.827 ± 0.003, test 0.811 ± 0.005. CNN 33x33 on test: 0.860 ± 0.008.
- Held-out regions (CNN 33x33 vs. RF): Filadelfia RF wins (0.706 vs. 0.831), Bahía Negra CNN narrowly (0.619 vs. 0.611), Pozo Colorado CNN (0.727 vs. 0.661).
- Grad-CAM hooks the last conv block: an 8x8 map over the 33x33 patch.

## Goals / Non-Goals

**Goals:**
- Evaluate the tutor's 3x3 design under the same protocol as the current CNN.
- Decide the operational CNN with a rule fixed before scoring.

**Non-Goals:** see proposal.md.

## Decisions

### D1. The 3x3 model
- Same `SmallCNN`, with a `patch_px` argument (33 or 3). With `patch_px=3`, `forward()` crops the central 3x3 block of whatever patch it receives, and the two max-pooling layers become identities (pooling a 3x3 map twice is not possible). The conv stack, global average pooling, dropout and classifier are unchanged, so the parameter count is the same and the comparison isolates the input size.
- Cropping inside the model means every data path stays as it is: the 33x33 training patches, the held-out extraction (`14`, `16`, `17`) and the AOI tiling (`18`). Rotation and flip augmentation keep the central block in the center, so augmentation applies unchanged.
- `patch_px` is saved in the checkpoint and read back by `load_checkpoint()`.

### D2. Hyperparameters of the 3x3 CNN
- Same grid as `phase1-hyperparameter-selection` D1: `lr` {0.0001, 0.0003, 0.001, 0.01} × `dropout` {0.3, 0.4, 0.5} × `batch_size` {16, 32, 64}, seeds 42, 1, 7, 123, 2026, validation split only, `ddof=1`, same truncation rule (re-run at 300 epochs if any run reaches 100).
- There is no current 3x3 configuration to keep, so the best mean is selected. Ties go to the configuration closest to the selected 33x33 one, then to the lower mean stop epoch.
- The 33x33 CNN is not re-scored: its per-seed validation scores for the selected configuration are taken from `data/study_area/hyperparameter_selection/results.json` (same seeds, same split, same code path, since `patch_px=33` leaves `forward()` unchanged). A seed-42 re-run checks that it reproduces.

### D3. Patch-size rule (pre-registered)
- 3x3 is the default because it is the tutor's design.
- Pooled std = sqrt((s_33² + s_3²) / 2), from the 5 validation scores of each selected configuration.
- If mean_33 − mean_3 > pooled std, the 33x33 CNN stays operational. Otherwise the 3x3 CNN becomes operational.
- Written in `data/study_area/patch_size_selection/README.md` above `## Results`, hashed and logged to MLflow before the first 3x3 run, checked by the scoring step, as in `24_hyperparameter_selection.py`.

### D4. Test and held-out, once
- `11_compare_classifiers.py` is run once with the operational CNN, 5 seeds, `ddof=1`, same RF vs. CNN criterion.
- The patch-size results also report both selected CNNs on test (5 seeds each), for the record. Nothing is chosen with those numbers.
- If the operational CNN changes, `14`, `16` and `17` are re-run. The current held-out JSONs are copied into `patch_size_selection/` first, so the 33x33 held-out numbers stay available next to the 3x3 ones.

### D5. Cascade if the 3x3 CNN becomes operational
Same order as `phase1-hyperparameter-selection` D5:
1. Retrain and save the seed-42 checkpoint with `patch_px=3`.
2. Re-run `18_classify_aoi_temporal.py` over the AOI and the development area, 2019-2023.
3. Re-apply `26_score_change_configs.py score` without changing its rule, and rebuild the change map (`19_temporal_change_map.py`).
4. Re-run Grad-CAM (`21_grad_cam.py`, `22_explain_transition.py`). With a 3x3 input the CAM is 3x3 and covers only the central 30 m block; it is drawn over that block, not stretched over the 33x33 patch.
5. Redraw the AOI reference sample (`27_draw_reference_sample.py`). The held-out samples are stratified by WorldCover and stay as they are.

If the 33x33 CNN stays, nothing downstream changes.

## Risks / Trade-offs

- **Grad-CAM loses spatial detail with 3x3.** A 3x3 map over 30 m can only say which of the 9 pixels weighed most. This was weighed against matching the tutor's design and accepted; the thesis reports it as the cost of the choice.
- **A 3x3 CNN is close to a per-pixel classifier.** If it behaves like Random Forest, the RF vs. CNN comparison becomes a comparison of two near-pixel models. The test and held-out results will show it, and the thesis reports it as found.
- **The default favours 3x3.** Deliberate, and stated before scoring: the 33x33 design has to beat noise to stay.
