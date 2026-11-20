"""Wall-to-wall classification of an area larger than one tile, with the U-Net and the Random Forest
(phase1-segmentation D6, task 5.1). Used by 18 (AOI and development area) and the held-out scripts.

The area goes on Sentinel-2's own UTM 10 m grid in its zone, with edges at multiples of 30 m, as the
training tiles did (35_assemble_tiles.py), so no band is resampled and every 30 m cell is an exact
3x3 block. A region crossing a UTM zone boundary is split at it and each part classified in its own
zone. The grid is padded by half a window on every side, so every cell of the area is covered by
four windows, like the inner cells of a 192 px tile.

U-Net: windows of the model's tile size with half-window overlap, 30 m probabilities averaged, the
rule of 36_train_unet.predict_full applied to the whole grid. Random Forest: the mean of each 3x3
block, as in training. The image comes in blocks small enough for one computePixels request; each
block brings the extra half window its last windows reach into, so every window is classified
exactly once and the result does not depend on the block size (checked by main()).

A cell with a gap pixel in either composite, or whose center lies outside the area, is UNCLASSIFIED,
the same cells 35 set to ignored in the labels.

Usage: .venv/bin/python scripts/tile_inference.py (the synthetic-tile check of task 5.1)"""

import importlib
import math

import ee
import numpy as np
import shapely
import torch
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

import dataset_loader as dl

unet = importlib.import_module("36_train_unet")
tiles = importlib.import_module("35_assemble_tiles")

BLOCK_PX = 384  # (384 + 24)^2 px x 26 channels x 8 bytes = 35 MB, under computePixels' 48 MB per request
UNCLASSIFIED = -1
N_CLASSES = len(dl.CLASS_NAMES)


def utm_epsg(lon):
    return 32700 + int((lon + 180) // 6) + 1


def zone_parts(geom):
    """The area split at UTM zone boundaries, as (epsg, part in WGS84)."""
    lon0, _, lon1, _ = geom.bounds
    parts = []
    for zone_lon in range(int((lon0 + 180) // 6) * 6 - 180, math.ceil(lon1), 6):
        part = geom.intersection(box(zone_lon, -90, zone_lon + 6, 90))
        if part.area > 0:
            parts.append((utm_epsg(zone_lon + 3), part))
    return parts


def area_grid(epsg, part, tile_px):
    """Top-left corner (m) and size (10 m px) of the padded grid. Sides are whole numbers of
    half windows, so the windows tile it exactly."""
    step_m = tile_px // 2 * 10
    minx, miny, maxx, maxy = transform(Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True).transform,
                                       part.segmentize(0.01)).bounds
    x0 = math.floor(minx / 30) * 30 - step_m
    y0 = math.ceil(maxy / 30) * 30 + step_m
    width = (math.ceil((maxx - x0) / step_m) + 1) * tile_px // 2
    height = (math.ceil((y0 - miny) / step_m) + 1) * tile_px // 2
    return {"epsg": epsg, "x0": x0, "y0": y0, "width": width, "height": height, "tile_px": tile_px}


def grid_region(grid):
    """The grid as an Earth Engine rectangle, the region a composite for it is built over."""
    return ee.Geometry.Rectangle([grid["x0"], grid["y0"] - grid["height"] * 10, grid["x0"] + grid["width"] * 10, grid["y0"]],
                                 f"EPSG:{grid['epsg']}", False)


def inside_mask(grid, part):
    """True for the 30 m cells whose center lies inside the area."""
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{grid['epsg']}", always_xy=True).transform
    rows, cols = np.mgrid[:grid["height"] // 3, :grid["width"] // 3]
    return shapely.contains_xy(transform(to_utm, part.segmentize(0.01)),
                               grid["x0"] + (cols + 0.5) * 30, grid["y0"] - (rows + 0.5) * 30)


def pixel_grid(grid, r0, c0, width, height, px):
    return {"dimensions": {"width": width, "height": height},
            "affineTransform": {"scaleX": px, "shearX": 0, "translateX": grid["x0"] + c0 * 10,
                                "shearY": 0, "scaleY": -px, "translateY": grid["y0"] - r0 * 10},
            "crsCode": f"EPSG:{grid['epsg']}"}


def gee_fetcher(grid, composite, channels):
    """fetch(r0, c0, height, width) for classify(): the composite over that window of the grid,
    stored and read back as 35 does, so the model sees the same rounding it trained on."""
    def fetch(r0, c0, height, width):
        pixels = ee.data.computePixels({"expression": composite.select(channels), "fileFormat": "NUMPY_NDARRAY",
                                        "grid": pixel_grid(grid, r0, c0, width, height, 10)})
        return tiles.quantize(np.stack([pixels[c] for c in channels], axis=-1).astype(np.float64), channels)
    return fetch


def label_cells(grid, image):
    """A single-band image (MapBiomas, WorldCover) on the 30 m cells of the grid, nearest neighbour."""
    cells = ee.data.computePixels({"expression": image, "fileFormat": "NUMPY_NDARRAY",
                                   "grid": pixel_grid(grid, 0, 0, grid["width"] // 3, grid["height"] // 3, 30)})
    return cells[cells.dtype.names[0]]


def unet_predictor(model, device, batch_size=64):
    def predict(image, starts):
        windows = torch.stack([torch.from_numpy(np.ascontiguousarray(image[r:r + model.tile_px, c:c + model.tile_px]
                                                                     .transpose(2, 0, 1))) for r, c in starts])
        with torch.no_grad():
            return torch.cat([unet.probs_30m(model(windows[i:i + batch_size].to(device))).cpu()
                              for i in range(0, len(windows), batch_size)]).numpy()
    predict.tile_px = model.tile_px
    return predict


def rf_predictor(rf):
    def predict(image):
        h, w = image.shape[0] // 3, image.shape[1] // 3
        cells = image.reshape(h, 3, w, 3, 26).mean(axis=(1, 3)).reshape(-1, 26)
        return rf.predict_proba(cells).T.reshape(N_CLASSES, h, w).astype(np.float32)
    return predict


def classify(fetch, grid, unets=(), rfs=(), block_px=BLOCK_PX):
    """30 m probabilities (3, H/3, W/3) per model, U-Nets first, and the gap mask (H/3, W/3).
    All U-Nets share the grid's tile size, so one fetch serves every model."""
    size, step = grid["tile_px"], grid["tile_px"] // 2
    height, width = grid["height"], grid["width"]
    shape = (height // 3, width // 3)
    totals = [np.zeros((N_CLASSES, *shape), np.float32) for _ in range(len(unets) + len(rfs))]
    weight = np.zeros(shape, np.float32)
    gap = np.zeros(shape, bool)
    for r0 in range(0, height - size + 1, block_px):
        for c0 in range(0, width - size + 1, block_px):
            h, w = min(block_px + step, height - r0), min(block_px + step, width - c0)
            image = dl.tile_to_float(fetch(r0, c0, h, w))
            n = 13
            gap_px = np.all(image[..., :n] == 0, axis=-1) | np.all(image[..., n:] == 0, axis=-1)
            cells = (slice(r0 // 3, (r0 + h) // 3), slice(c0 // 3, (c0 + w) // 3))
            gap[cells] = gap_px.reshape(h // 3, 3, w // 3, 3).any(axis=(1, 3))
            starts = [(r, c) for r in range(0, min(block_px, h - size + 1), step) for c in range(0, min(block_px, w - size + 1), step)]
            for total, predict in zip(totals, unets):
                for (r, c), p in zip(starts, predict(image, starts)):
                    total[:, (r0 + r) // 3:(r0 + r + size) // 3, (c0 + c) // 3:(c0 + c + size) // 3] += p
            for (r, c) in starts:
                weight[(r0 + r) // 3:(r0 + r + size) // 3, (c0 + c) // 3:(c0 + c + size) // 3] += 1
            for total, predict in zip(totals[len(unets):], rfs):
                total[(slice(None), *cells)] = predict(image)
    for total in totals[:len(unets)]:
        total /= weight
    return totals, gap


def to_classes(probs, gap, inside):
    classes = probs.argmax(axis=0)
    classes[gap | ~inside] = UNCLASSIFIED
    return classes


def main():
    """Task 5.1 check: on a synthetic 192 px tile, classify() equals predict_full (the direct
    prediction of 36) for 48 and 96 px windows with blocks smaller than the tile, so windows cross
    block edges; on a larger synthetic grid, small blocks equal one block; the Random Forest equals
    predicting the 3x3 means directly."""
    from sklearn.ensemble import RandomForestClassifier

    rng = np.random.default_rng(0)
    torch.manual_seed(0)

    def synthetic(height, width):
        image = rng.integers(0, 6000, (height, width, 26)).astype(np.int16)
        image[..., dl.TILE_NDVI_CHANNELS] = rng.integers(-2000, 9000, (height, width, 2))
        image[:9, :12] = 0  # a gap, to check the mask
        return image

    for tile_px in (48, 96):
        model = unet.UNet(tile_px).eval()
        tile = synthetic(192, 192)
        direct = unet.predict_full(model, torch.from_numpy(dl.tile_to_float(tile).transpose(2, 0, 1)[None].copy()), "cpu")[0].numpy()
        grid = {"tile_px": tile_px, "height": 192, "width": 192}
        fetch = lambda r0, c0, h, w: tile[r0:r0 + h, c0:c0 + w]  # noqa: E731
        (tiled,), gap = classify(fetch, grid, unets=[unet_predictor(model, "cpu")], block_px=tile_px)
        diff = float(np.abs(tiled - direct).max())
        assert diff < 1e-5 and gap[:3, :4].all() and not gap[3:].any(), diff
        print(f"{tile_px} px windows, {tile_px} px blocks on a 192 px tile: max |diff| vs predict_full {diff:.1e}")

        big = synthetic(tile_px // 2 * 21, tile_px // 2 * 17)
        grid = {"tile_px": tile_px, "height": big.shape[0], "width": big.shape[1]}
        fetch = lambda r0, c0, h, w: big[r0:r0 + h, c0:c0 + w]  # noqa: E731
        (one,), _ = classify(fetch, grid, unets=[unet_predictor(model, "cpu")], block_px=10 ** 6)
        (many,), _ = classify(fetch, grid, unets=[unet_predictor(model, "cpu")], block_px=2 * tile_px)
        diff = float(np.abs(one - many).max())
        assert diff < 1e-5 and not np.isnan(one).any(), diff
        print(f"{tile_px} px windows on a {big.shape[0]}x{big.shape[1]} px grid: max |diff| one block vs {2 * tile_px} px blocks {diff:.1e}")

    tile = synthetic(192, 192)
    cells = dl.tile_to_float(tile).reshape(64, 3, 64, 3, 26).mean(axis=(1, 3)).reshape(-1, 26)
    rf = RandomForestClassifier(n_estimators=10, random_state=0).fit(cells, rng.integers(0, 3, len(cells)))
    (tiled,), _ = classify(lambda r0, c0, h, w: tile[r0:r0 + h, c0:c0 + w], {"tile_px": 48, "height": 192, "width": 192},
                           rfs=[rf_predictor(rf)], block_px=48)
    assert np.array_equal(tiled.argmax(axis=0).reshape(-1), rf.predict(cells))
    print("Random Forest, 48 px blocks: same classes as predicting the 3x3 means directly")


if __name__ == "__main__":
    main()
