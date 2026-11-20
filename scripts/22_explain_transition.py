"""Explains forest loss in the AOI's change map with Seg-Grad-CAM (phase1-segmentation D6). For a
few loss cells of the filtered forest/non-forest map (change_map_2019_2023_fnf.npy), the region
explained is the whole connected loss patch the cell belongs to, and the window is the one of 18's
classification grid whose center is nearest the patch's. Both dates side by side: why the U-Net called
the patch bosque in 2019 and what it called it in 2023.

The window is pulled from 18's own grid, so it holds the exact pixels 18 classified. Checked per
cell and date, as the CNN version was: re-predicting every window that covers the cell and
averaging gives back the probability stored in that date's raster.
Usage: .venv/bin/python scripts/22_explain_transition.py"""

import importlib
import json
from pathlib import Path

import numpy as np
import torch
from scipy import ndimage

import dataset_loader as dl
import gee_session
import s2_utils
import tile_inference

classify_aoi = importlib.import_module("18_classify_aoi_temporal")
change_map = importlib.import_module("19_temporal_change_map")
grad_cam = importlib.import_module("21_grad_cam")
unet = importlib.import_module("36_train_unet")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"
PERIODS = {"2019": classify_aoi.PERIODS["2019"], "2023": classify_aoi.PERIODS["2023"]}
N_PIXELS = 2  # same count as 19's own visual check
PROBA_TOLERANCE = 2e-3  # the stored probabilities are float16


def pick_fnf_loss_pixels(change):
    rows, cols = np.where(change == change_map.LOSS)
    picks = np.linspace(0, len(rows) - 1, min(N_PIXELS, len(rows)), dtype=int)
    return [(int(rows[i]), int(cols[i])) for i in picks]


def covering_windows(row, col, grid):
    """Top-left corners (10 m px) of the grid's windows that cover cell (row, col)."""
    size, step = grid["tile_px"], grid["tile_px"] // 2

    def starts(cell, extent):
        return [s for s in range(0, extent - size + 1, step) if s <= 3 * cell < s + size]
    return [(r, c) for r in starts(row, grid["height"]) for c in starts(col, grid["width"])]


def main():
    gee_session.init()
    meta = json.loads((DATA_DIR / "aoi_classified_grid_meta.json").read_text())
    grid = tile_inference.grid_from_meta(meta)
    change = np.load(DATA_DIR / "change_map_2019_2023_fnf.npy")
    rasters = {p: np.load(DATA_DIR / f"aoi_classified_{p}.npy") for p in PERIODS}
    probas = {p: np.load(DATA_DIR / f"aoi_proba_{p}.npy") for p in PERIODS}
    model, device = unet.load_checkpoint()
    size = model.tile_px
    patches, _ = ndimage.label(change == change_map.LOSS, structure=np.ones((3, 3), dtype=int))
    predict = tile_inference.unet_predictor(model, device)

    for i, (row, col) in enumerate(pick_fnf_loss_pixels(change)):
        lon, lat = change_map.pixel_to_wgs84(row, col, meta)
        windows = covering_windows(row, col, grid)
        patch = patches == patches[row, col]
        # Centered on the patch, not the picked cell, so the region explained sits inside the window
        pr, pc = (3 * np.mean(np.nonzero(patch)[k]) + 1.5 for k in (0, 1))
        step = size // 2
        r0, c0 = (int(np.clip(round((p - size / 2) / step), 0, (extent - size) // step)) * step
                  for p, extent in ((pr, grid["height"]), (pc, grid["width"])))
        region = np.kron(patch[r0 // 3:(r0 + size) // 3, c0 // 3:(c0 + size) // 3], np.ones((3, 3)))
        print(f"\ncell {i}: (row={row}, col={col}) -> lon={lon:.5f}, lat={lat:.5f}, loss patch of {int(patch.sum())} cells "
              f"({int(region.sum() / 9)} inside the window)")

        for period, (start, end) in PERIODS.items():
            composite, channels = s2_utils.build_season_composite(tile_inference.grid_region(grid), start, end, "drywet", reproject=False)
            fetch = tile_inference.gee_fetcher(grid, composite, channels)
            rmin, cmin = min(r for r, _ in windows), min(c for _, c in windows)
            span = dl.tile_to_float(fetch(rmin, cmin, max(r for r, _ in windows) - rmin + size, max(c for _, c in windows) - cmin + size))
            probs = predict(span, [(r - rmin, c - cmin) for r, c in windows])
            mean = np.mean([p[:, row - r // 3, col - c // 3] for p, (r, c) in zip(probs, windows)], axis=0)
            diff = float(np.abs(mean - probas[period][row, col].astype(np.float32)).max())
            recorded = int(rasters[period][row, col])
            print(f"  {period}: recorded {dl.CLASS_NAMES[recorded]}, re-predicted probabilities differ by {diff:.1e} "
                  f"({'matches' if diff < PROBA_TOLERANCE else 'MISMATCH'})")

            window = dl.tile_to_float(fetch(r0, c0, size, size))
            window_chw = torch.from_numpy(np.ascontiguousarray(window.transpose(2, 0, 1)))
            result = grad_cam.guided_seg_grad_cam(model, window_chw, torch.from_numpy(region).float(), recorded, device)
            out_path = DATA_DIR / f"gradcam_loss_{i}_{period}.png"
            grad_cam.render_overlay(window, result["sharpened"], region,
                                    f"forest loss patch {i}, {period} (explained: {dl.CLASS_NAMES[recorded]})",
                                    out_path, cam_px=result["raw_cam"].shape[0])
            print(f"  saved: {out_path}")


if __name__ == "__main__":
    main()
