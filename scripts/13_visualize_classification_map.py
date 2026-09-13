"""Runs the winning classifier (Random Forest) and the CNN candidate over a real image tile
inside the AOI, rendered side by side with true-color Sentinel-2, so the comparison is visible
as a map, not just accuracy numbers. Small tile (2km x 2km) pulled via sampleRectangle() to keep
the single getInfo() call light. Refuses to classify a tile with real cloud gaps rather than
silently zero-filling missing pixels."""

import importlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from numpy.lib.stride_tricks import sliding_window_view

import gee_session
import s2_utils

train_cnn = importlib.import_module("10_train_cnn")
train_rf = importlib.import_module("09_train_random_forest")

OUT_PNG = Path(__file__).resolve().parents[1] / "data" / "study_area" / "classification_map.png"

TILE_HALF_SIDE_M = 1000  # -> ~2km x 2km at 10m
PALETTE = ["1f8d49", "edde8e", "e974ed"]  # bosque, pasto, cultivo
CNN_BATCH = 512
ROW_CHUNK = 40  # output rows processed per CNN pass, bounds peak memory


def classify_with_cnn(grid, model, device):
    """Dense per-pixel inference: one 33x33 window per output pixel. Processed in row chunks
    instead of materializing all windows at once (a 200x200 tile is already ~2GB unchunked)."""
    h, w, c = grid.shape
    padded = np.pad(grid, ((16, 16), (16, 16), (0, 0)), mode="reflect")
    out = np.zeros((h, w), dtype=np.int64)

    model.eval()
    with torch.no_grad():
        for row_start in range(0, h, ROW_CHUNK):
            row_end = min(row_start + ROW_CHUNK, h)
            strip = padded[row_start:row_end + 32]  # includes the +-16 context for this row block
            windows = sliding_window_view(strip, (33, 33, c))[:, :, 0]  # (rows, w, 33, 33, c)
            n_rows = windows.shape[0]
            flat = windows.reshape(n_rows * w, 33, 33, c).transpose(0, 3, 1, 2)

            preds = []
            for i in range(0, len(flat), CNN_BATCH):
                batch = torch.from_numpy(np.ascontiguousarray(flat[i:i + CNN_BATCH])).to(device)
                preds.append(model(batch).argmax(1).cpu().numpy())
            out[row_start:row_end] = np.concatenate(preds).reshape(n_rows, w)
    return out


def main():
    gee_session.init()
    aoi = s2_utils.load_aoi()
    tile = aoi.centroid(1).buffer(TILE_HALF_SIDE_M).bounds()

    print("Pulling pixel grid from Earth Engine...")
    composite = s2_utils.build_s2_composite(tile, "2023-06-01", "2023-09-30", add_ndvi=True, raise_on_gap=True)
    channels = s2_utils.S2_BANDS + ["NDVI"]
    result = composite.select(channels).sampleRectangle(region=tile, defaultValue=0).getInfo()
    arrays = [np.array(result["properties"][ch], dtype=np.float32) for ch in channels]
    grid = np.stack(arrays, axis=-1)  # (H, W, 13)
    h, w, _ = grid.shape
    print(f"Tile shape: {h} x {w} pixels")

    print("Training Random Forest and classifying every pixel...")
    rf = train_rf.train(verbose=False)
    rf_pred = rf.predict(grid.reshape(-1, 13)).reshape(h, w)

    print("Training CNN and classifying every pixel (dense sliding-window inference)...")
    cnn_model, device, _ = train_cnn.train(verbose=False)
    cnn_pred = classify_with_cnn(grid, cnn_model, device)

    rgb = np.clip(np.stack([grid[..., 3], grid[..., 2], grid[..., 1]], axis=-1) / 3000, 0, 1)  # B4,B3,B2
    palette_rgb = np.array([[int(c[i:i+2], 16) / 255 for i in (0, 2, 4)] for c in PALETTE])

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5))
    axes[0].imshow(rgb)
    axes[0].set_title("Sentinel-2 real (RGB), 2023")
    axes[1].imshow(palette_rgb[rf_pred])
    axes[1].set_title("Random Forest (ganador)")
    axes[2].imshow(palette_rgb[cnn_pred])
    axes[2].set_title("CNN (candidata)")
    for ax in axes:
        ax.axis("off")

    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in ["#1f8d49", "#edde8e", "#e974ed"]]
    fig.legend(handles, ["bosque", "pasto", "cultivo"], loc="lower center", ncol=3, frameon=False)
    fig.suptitle("AOI Corazón Verde del Chaco, recorte 2km x 2km", fontsize=12)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(OUT_PNG, dpi=150)
    print(f"saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
