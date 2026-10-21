## Why

The tutor's design for the dataset was a 3x3 matrix of Sentinel-2 pixels (10 m) per MapBiomas pixel (30 m), keeping Sentinel-2's native resolution as input. The 3x3 block was implemented as the label alignment unit, but during `phase1-dataset-build` the CNN input was widened to a 33x33 patch (~330 m) centered on that block, to give the CNN spatial context to learn from. That widening was never evaluated against the tutor's original design.

Two observations make the comparison worth running now:

- The label belongs to the central 30 m block, while the 33x33 CNN sees 330 m. Part of what it looks at can belong to another class.
- The 33x33 CNN loses to Random Forest in Filadelfia, where forest comes in narrow strips between fields (`docs/PHASE1_SUMMARY.md`). A 3x3 input matches the label exactly and cannot be swayed by the surroundings.

No reference point has been interpreted yet, so a change of the operational CNN costs no interpretation work.

## What Changes

- **3x3 CNN candidate.** The same small CNN, fed only the central 3x3 block of each existing 33x33 patch (cropped inside the model, so the dataset, the held-out extraction and the AOI tiling stay as they are), without the pooling layers a 3x3 input cannot support.
- **Its hyperparameters selected on validation**, with the same grid, seeds, truncation rule and `ddof=1` as `phase1-hyperparameter-selection`.
- **Patch-size rule, pre-registered** (design D3): the 3x3 CNN becomes the operational classifier unless the 33x33 CNN beats it on validation by more than their pooled standard deviation. The 3x3 design is the default because it is the tutor's.
- **Test and held-out reported once** for the operational model; the 3x3 and 33x33 CNNs are both reported on test, for the record.
- **Downstream cascade** if the operational CNN changes (design D5), including a redraw of the AOI reference sample.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `land-cover-classifier`: the CNN candidate's input size becomes a selected design choice (3x3 or 33x33), decided on the validation split by a pre-registered rule.

## Non-goals

- Semantic segmentation (U-Net). Still open with the tutor; a separate change.
- New data, new features or a new split. The 3x3 input is a crop of the existing patches.
- Re-selecting the 33x33 CNN's or Random Forest's hyperparameters. Both keep the configurations chosen in `phase1-hyperparameter-selection`.
- Any use of the test split, the held-out regions or the reference sample to choose the patch size.

## Impact

- **Scripts:** `10_train_cnn.py` (`patch_px` in `SmallCNN`, `train()` and the checkpoint), new `31_patch_size_selection.py` (`preregister` and `score`), `21_grad_cam.py` (a 3x3 CAM is drawn over the central block only).
- **Data:** `data/study_area/patch_size_selection/` (pre-registered README, preregistration hash, results).
- **MLflow:** experiment `phase1-patch-size-selection`.
- **Compute:** 180 CNN trainings on 3x3 inputs, about 1-2 hours locally. The cascade needs GEE for the AOI and development-area classification.
- **Docs:** `docs/PHASE1_SUMMARY.md`, `docs/METODOLOGIA_PIPELINE.md`, thesis chapters 2 and 3, the `land-cover-classifier` spec.
- **Blocks** the interpretation of the AOI reference sample (`phase1-accuracy-assessment` 4.x) until this change says which CNN is operational.
