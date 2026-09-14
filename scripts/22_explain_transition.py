"""Explains a detected temporal transition with Grad-CAM, phase1-grad-cam tasks 3.1-3.2. Picks
the same hand-picked pixels as 19_temporal_change_map.py's own visual check (its largest
detected transition), extracts each one's 33x33 window for both 2019 and 2023, and renders
Grad-CAM overlays for both dates side by side -- evidence for *why* the CNN called each half of
the transition, not just that the diff changed.

Extraction reuses 18_classify_aoi_temporal.py's own tile pull + array-slice window mechanism
(pull_tile + the same local-offset slice classify_tile uses internally), NOT an independent small
sampleRectangle() query at the pixel's own bounding box. Task 3.1's own verification step (compare
the fresh prediction against the class already recorded in that date's raster) caught that the
independent-query approach silently snapped to a different pixel grid than the tile pipeline did
-- close enough everywhere except right at boundary pixels like these, where it flipped the
predicted class. Re-using the exact same tile array + slice is the only way to guarantee the
identical window 18_classify_aoi_temporal.py itself classified on.
Usage: .venv/bin/python scripts/22_explain_transition.py"""

import importlib
import json
from pathlib import Path

import ee
import numpy as np
import torch
from shapely.ops import transform as shapely_transform

import dataset_loader as dl
import gee_session
import s2_utils

classify_aoi = importlib.import_module("18_classify_aoi_temporal")
change_map = importlib.import_module("19_temporal_change_map")
grad_cam = importlib.import_module("21_grad_cam")
train_cnn = importlib.import_module("10_train_cnn")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"
PATCH_RADIUS_PX = classify_aoi.PATCH_RADIUS_PX  # 16 -> 33x33, same alignment as training patches
PATCH_SIZE_PX = 2 * PATCH_RADIUS_PX + 1
PERIODS = {"2019": ("2019-06-01", "2019-09-30"), "2023": ("2023-06-01", "2023-09-30")}
N_PIXELS = 2  # same count as 19's own visual check


def pick_transition_pixels(change):
    """Mirrors 19_temporal_change_map.py's visual_check() pixel-picking exactly, so the same
    pixels get both a true-color visual check (there) and a Grad-CAM explanation (here) -- the
    two checks corroborate each other (design.md, tasks.md 3.2)."""
    codes, counts = np.unique(change, return_counts=True)
    transition_counts = {c: n for c, n in zip(codes, counts) if c in change_map.TRANSITION_NAMES}
    target = max(transition_counts, key=transition_counts.get)
    rows, cols = np.where(change == target)
    picks = np.linspace(0, len(rows) - 1, min(N_PIXELS, len(rows)), dtype=int)
    return change_map.TRANSITION_NAMES[target], [(int(rows[i]), int(cols[i])) for i in picks]


def extract_patch(composite, channels, tiles, row, col):
    """Pulls the whole padded tile containing (row, col) and slices out the exact 33x33 window
    classify_tile() itself would use for that core pixel -- see module docstring for why this,
    not a standalone small sampleRectangle() query."""
    core_px = classify_aoi.TILE_CORE_PX
    tile_row, tile_col = row // core_px, col // core_px
    tile = next(t for t in tiles if t["row"] == tile_row and t["col"] == tile_col)
    grid = classify_aoi.pull_tile(composite, channels, tile["padded_utm"])
    local_r, local_c = row % core_px, col % core_px
    return grid[local_r:local_r + PATCH_SIZE_PX, local_c:local_c + PATCH_SIZE_PX]


def main():
    gee_session.init()
    meta = json.loads((DATA_DIR / "aoi_classified_grid_meta.json").read_text())
    change = np.load(DATA_DIR / "change_map_2019_2023.npy")
    rasters = {p: np.load(DATA_DIR / f"aoi_classified_{p}.npy") for p in PERIODS}
    model, device = train_cnn.load_checkpoint()
    print(f"Loaded checkpoint: {train_cnn.CHECKPOINT_PATH}")

    aoi_wgs84_shapely = classify_aoi.load_aoi_geom_wgs84()
    aoi_m = shapely_transform(classify_aoi.to_utm, aoi_wgs84_shapely)
    tiles, n_rows, n_cols = classify_aoi.build_tile_grid(aoi_m)
    assert (n_rows, n_cols) == (meta["n_rows"], meta["n_cols"]), "tile grid drifted from 18's saved grid"
    aoi_wgs84_ee = ee.Geometry(json.loads(classify_aoi.AOI_PATH.read_text())["features"][0]["geometry"])
    channels = s2_utils.S2_BANDS + ["NDVI"]

    transition_name, pixels = pick_transition_pixels(change)
    print(f"Explaining transition: {transition_name} ({len(pixels)} pixels)")

    for i, (row, col) in enumerate(pixels):
        lon, lat = change_map.pixel_to_wgs84(row, col, meta)
        print(f"\npixel {i}: (row={row}, col={col}) -> lon={lon:.5f}, lat={lat:.5f}")

        for period, (start, end) in PERIODS.items():
            composite = s2_utils.build_s2_composite(aoi_wgs84_ee, start, end, add_ndvi=True, reproject=True, clip=True)
            patch = extract_patch(composite, channels, tiles, row, col)
            patch_chw = torch.from_numpy(np.ascontiguousarray(patch.transpose(2, 0, 1)))
            pred = int(model(patch_chw.unsqueeze(0).to(device)).argmax(1).item())
            recorded = int(rasters[period][row, col])
            match = "matches" if pred == recorded else "MISMATCH"
            print(f"  {period}: fresh-pull prediction={dl.CLASS_NAMES[pred]}, "
                  f"recorded={dl.CLASS_NAMES[recorded]} ({match})")

            result = grad_cam.guided_grad_cam(model, patch_chw, pred, device)
            out_path = DATA_DIR / f"gradcam_transition_{i}_{period}.png"
            grad_cam.render_overlay(
                patch, result["sharpened"],
                f"{transition_name} pixel {i}, {period} (predicted: {dl.CLASS_NAMES[pred]})",
                out_path,
            )
            print(f"  saved: {out_path}")


if __name__ == "__main__":
    main()
