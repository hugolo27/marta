## Why

On 2026-10-19 the tutor reviewed the dataset-v2 results and said a CNN on a 3x3 input is too large a model for such a small input (100,707 weights on 3x3x26 = 234 numbers), and asked to drop it and move to semantic segmentation with a U-Net, evaluated with the Dice coefficient.

The anteproyecto already left this open ("clasificación por parches o segmentación se definirá con el tutor") and its objective OE1 (a classifier with spatial context against a per-pixel one) still holds: the U-Net is the classifier with spatial context and Random Forest stays the per-pixel baseline.

Every value in this change is traced to a verified source, to a measurement, or to the geometry of the data (design D0).

## What Changes

- **Tiles instead of patches.** Each example is a Sentinel-2 tile (dry + wet, 26 channels) with the MapBiomas label map of the same ground, one label per 30 m pixel. Tiles of 192 px are extracted once; 96 and 48 px tiles are center crops.
- **U-Net** with nnU-Net's rules for depth, filters and loss (Isensee et al., 2021). The 10 m output is averaged over each 3x3 block, so training and evaluation happen at 30 m, the resolution of the label.
- **Pixels outside the three classes** (water, natural grassland, urban...) are ignored in the loss and the metrics, as Cityscapes does with void pixels (Cordts et al., 2016).
- **Pilot study** on training and validation only, to measure the early-stopping patience and the size of the validation and test splits instead of choosing them.
- **Pre-registered selection** of tile size, `lr` and batch on validation, then U-Net vs. Random Forest (per 30 m pixel) by the anteproyecto's rule, test once.
- **Cascade** with the selected model: held-out regions, AOI 2019-2023, change map, Grad-CAM for segmentation, redrawn reference sample.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `training-dataset`: tiles with per-pixel label maps replace single-label patches.
- `land-cover-classifier`: the U-Net replaces the patch CNN; pilot study; evaluation at 30 m with Dice.

## Non-goals

- autoresearch (karpathy/autoresearch). It can replace or complement the grid later, once a U-Net exists; it is a separate decision.
- More seasons than dry + wet, new classes, a new label source.
- Changing the held-out regions, the AOI, the 6 km blocks or the change-map rule.

## Impact

- **Scripts:** new tile extraction (`35_assemble_tiles.py`), U-Net training (`36_train_unet.py`), pilot (`37_unet_pilot.py`), selection (`38_unet_selection.py`); `dataset_loader.py` (tiles), RF at 30 m; `14`, `16`, `17`, `18`, `21`, `22`, `30` to classify with tiles.
- **Data:** `data/study_area/tiles/` (new; the patch dataset stays as it is), `data/study_area/unet_pilot/`, `data/study_area/unet_selection/`.
- **Compute:** GEE extraction of ~2,000 tiles of 192x192x26 (int16, ~4 GB). Training cost is measured in the pilot before the grid is launched; if the local machine is too slow, a cloud GPU is proposed then.
- **Supersedes** the 3x3 patch CNN as candidate; its results stay in the thesis as the path that led here.
