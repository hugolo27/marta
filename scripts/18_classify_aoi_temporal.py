"""Dense per-date CNN classification over the case-study AOI for 2019 and 2023
(phase1-temporal-comparison tasks 2.1-2.3). Uses one persisted checkpoint
(10_train_cnn.py::load_checkpoint, seed 42) so both dates share the same decision boundary --
retraining per date would mix training-run variance (std ~0.01-0.02 macro-F1 across seeds,
phase1-classifier task 4.1) into what should be a real land-cover signal (design.md).

The AOI (~20,583 ha, an 8.8km x 24km bounding box) is too big for a single sampleRectangle()
pull: GEE caps it at 262,144 pixels and the bounding box is ~2.1M. Tiled into TILE_CORE_PX-sized
blocks in the AOI's own UTM zone (21S, single-zone -- same condition 06_align_3x3_patches.py
relies on, so reproject=True here unlike the multi-zone training footprint), each pulled with
PATCH_RADIUS_PX of padding for CNN context, classified with 13_visualize_classification_map.py's
row-chunked sliding-window approach, and stitched into one raster per date.

clip=True + sampleRectangle(defaultValue=0) means pixels outside the AOI polygon and real cloud
gaps both come through as all-zero across every band -- indistinguishable, and (matching
08_assemble_dataset.py's established all-zero-is-masked convention) both get marked UNCLASSIFIED
rather than fed to the CNN as if they were real pixels.

Also stores per-pixel softmax probabilities next to each class raster, and can run over the
change-development area and the in-between years -- both needed by
phase1-change-detection-hardening (confidence and persistence filters, and a second area with
real clearing to score them on). Same checkpoint, same June-September window for every year.

Usage: .venv/bin/python scripts/18_classify_aoi_temporal.py [--area aoi|dev] [--years 2019 2023]"""

import argparse

import json
from pathlib import Path

import ee
import mlflow
import numpy as np
import pyproj
from numpy.lib.stride_tricks import sliding_window_view
from shapely.geometry import box, shape
from shapely.ops import transform as shapely_transform

import gee_session
import s2_utils

train_cnn = __import__("importlib").import_module("10_train_cnn")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area"
AOI_PATH = REPO_ROOT / "data" / "study_area" / "aoi.geojson"
AREAS = {
    "aoi": {"path": AOI_PATH, "prefix": "aoi"},
    "dev": {"path": REPO_ROOT / "data" / "study_area" / "change_hardening" / "dev_area.geojson", "prefix": "dev"},
}

PERIODS = {str(y): (f"{y}-06-01", f"{y}-09-30") for y in range(2019, 2024)}
DEFAULT_YEARS = ["2019", "2023"]
PATCH_RADIUS_PX = 16  # -> 33x33, matches phase1-classifier's training patches
PIXEL_M = 10
TILE_CORE_PX = 400  # + 2*PATCH_RADIUS_PX padding = 432x432 = 186,624 px, under GEE's 262,144 cap
UTM_CRS = "EPSG:32721"  # zone 21S, matches the AOI's own longitude (~-58.4) and prior UTM usage
CNN_BATCH = 512
ROW_CHUNK = 40
UNCLASSIFIED = -1
CLASS_NAMES = ["bosque", "pasto", "cultivo"]
EXPERIMENT_NAME = "phase1-temporal-comparison"

to_utm = pyproj.Transformer.from_crs("EPSG:4326", UTM_CRS, always_xy=True).transform
to_wgs84 = pyproj.Transformer.from_crs(UTM_CRS, "EPSG:4326", always_xy=True).transform


def load_aoi_geom_wgs84(path=AOI_PATH):
    gj = json.loads(path.read_text())
    return shape(gj["features"][0]["geometry"])


def build_tile_grid(aoi_m):
    """Tiles the AOI's UTM bounding box into TILE_CORE_PX-pixel blocks. Returns a list of dicts
    with the core raster placement (row/col slice into the full-AOI output array) and the
    padded UTM bounds to pull from GEE (converted to WGS84 at call time)."""
    minx, miny, maxx, maxy = aoi_m.bounds
    core_m = TILE_CORE_PX * PIXEL_M
    pad_m = PATCH_RADIUS_PX * PIXEL_M
    n_cols = int(np.ceil((maxx - minx) / core_m))
    n_rows = int(np.ceil((maxy - miny) / core_m))

    tiles = []
    for row in range(n_rows):
        for col in range(n_cols):
            core_x0, core_y1 = minx + col * core_m, maxy - row * core_m  # UTM y decreases downward in raster rows
            core_x1, core_y0 = core_x0 + core_m, core_y1 - core_m
            tile_core = box(core_x0, core_y0, core_x1, core_y1)
            if not tile_core.intersects(aoi_m):
                continue
            padded = box(core_x0 - pad_m, core_y0 - pad_m, core_x1 + pad_m, core_y1 + pad_m)
            tiles.append({"row": row, "col": col, "padded_utm": padded})
    return tiles, n_rows, n_cols


def pull_tile(composite, channels, padded_utm):
    minx, miny, maxx, maxy = padded_utm.bounds
    lon0, lat0 = to_wgs84(minx, miny)
    lon1, lat1 = to_wgs84(maxx, maxy)
    rect = ee.Geometry.Rectangle([lon0, lat0, lon1, lat1])
    result = composite.select(channels).sampleRectangle(region=rect, defaultValue=0).getInfo()
    arrays = [np.array(result["properties"][ch], dtype=np.float32) for ch in channels]
    return np.stack(arrays, axis=-1)  # (H, W, 13), H/W close to but not exactly TILE_CORE_PX + 2*PATCH_RADIUS_PX


def classify_tile(grid, model, device):
    """Same row-chunked dense inference as 13_visualize_classification_map.py, but the output
    here is the tile's PADDED grid classified in full -- the caller crops to the core afterward,
    rather than reflect-padding at tile edges (which would fabricate context at every tile
    boundary, not just the AOI's true edge)."""
    h, w, c = grid.shape
    out_h, out_w = h - 2 * PATCH_RADIUS_PX, w - 2 * PATCH_RADIUS_PX
    out = np.full((out_h, out_w), UNCLASSIFIED, dtype=np.int64)
    out_proba = np.full((out_h, out_w, len(CLASS_NAMES)), np.nan, dtype=np.float16)

    model.eval()
    import torch
    with torch.no_grad():
        for row_start in range(0, out_h, ROW_CHUNK):
            row_end = min(row_start + ROW_CHUNK, out_h)
            strip = grid[row_start:row_end + 2 * PATCH_RADIUS_PX]
            windows = sliding_window_view(strip, (2 * PATCH_RADIUS_PX + 1, 2 * PATCH_RADIUS_PX + 1, c))[:, :, 0]
            n_rows = windows.shape[0]
            flat = windows.reshape(n_rows * out_w, 2 * PATCH_RADIUS_PX + 1, 2 * PATCH_RADIUS_PX + 1, c)
            flat = flat.transpose(0, 3, 1, 2)

            # A center pixel that's all-zero across every channel is a masked/gap/outside-AOI
            # pixel (08_assemble_dataset.py's established convention) -- never fed to the CNN as
            # if it were real, marked UNCLASSIFIED directly instead.
            centers = strip[PATCH_RADIUS_PX:PATCH_RADIUS_PX + (row_end - row_start), PATCH_RADIUS_PX:PATCH_RADIUS_PX + out_w]
            valid = ~np.all(centers == 0, axis=-1)  # (rows_here, out_w)

            preds = np.full(n_rows * out_w, UNCLASSIFIED, dtype=np.int64)
            proba = np.full((n_rows * out_w, len(CLASS_NAMES)), np.nan, dtype=np.float16)
            valid_flat = valid.reshape(-1)
            if valid_flat.any():
                valid_patches = flat[valid_flat]
                batch_proba = []
                for i in range(0, len(valid_patches), CNN_BATCH):
                    batch = torch.from_numpy(np.ascontiguousarray(valid_patches[i:i + CNN_BATCH])).to(device)
                    batch_proba.append(torch.softmax(model(batch), dim=1).cpu().numpy())
                valid_proba = np.concatenate(batch_proba)
                preds[valid_flat] = valid_proba.argmax(1)
                proba[valid_flat] = valid_proba
            out[row_start:row_end] = preds.reshape(row_end - row_start, out_w)
            out_proba[row_start:row_end] = proba.reshape(row_end - row_start, out_w, len(CLASS_NAMES))
    return out, out_proba


def classify_period(period, start, end, model, device, area_path, tiles, n_rows, n_cols):
    area_wgs84 = ee.Geometry(json.loads(area_path.read_text())["features"][0]["geometry"])
    composite = s2_utils.build_s2_composite(area_wgs84, start, end, add_ndvi=True, reproject=True, clip=True)
    channels = s2_utils.S2_BANDS + ["NDVI"]

    full = np.full((n_rows * TILE_CORE_PX, n_cols * TILE_CORE_PX), UNCLASSIFIED, dtype=np.int64)
    full_proba = np.full((n_rows * TILE_CORE_PX, n_cols * TILE_CORE_PX, len(CLASS_NAMES)), np.nan, dtype=np.float16)
    for i, t in enumerate(tiles):
        grid = pull_tile(composite, channels, t["padded_utm"])
        tile_out, tile_proba = classify_tile(grid, model, device)
        # GEE's rectangle snapping can return a few more/fewer pixels than requested; cap to the
        # core tile size so adjacent tiles never overlap in the stitched output (any extra rows/
        # cols beyond TILE_CORE_PX would just duplicate the next tile's own coverage).
        tile_out = tile_out[:TILE_CORE_PX, :TILE_CORE_PX]
        r0, c0 = t["row"] * TILE_CORE_PX, t["col"] * TILE_CORE_PX
        h, w = tile_out.shape
        full[r0:r0 + h, c0:c0 + w] = tile_out
        full_proba[r0:r0 + h, c0:c0 + w] = tile_proba[:TILE_CORE_PX, :TILE_CORE_PX]
        print(f"  {period} tile {i + 1}/{len(tiles)} (row={t['row']}, col={t['col']}): "
              f"{h}x{w}, {(tile_out != UNCLASSIFIED).sum()}/{h * w} classified")

    n_unclassified = int((full == UNCLASSIFIED).sum())
    print(f"{period}: {full.size} px total, {n_unclassified} unclassified "
          f"({n_unclassified / full.size:.1%})")
    return full, full_proba


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", choices=list(AREAS), default="aoi")
    parser.add_argument("--years", nargs="+", choices=list(PERIODS), default=DEFAULT_YEARS)
    args = parser.parse_args()
    area = AREAS[args.area]

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=f"classify_{area['prefix']}_{'_'.join(args.years)}"):
        gee_session.init()
        area_wgs84 = load_aoi_geom_wgs84(area["path"])
        area_m = shapely_transform(to_utm, area_wgs84)
        tiles, n_rows, n_cols = build_tile_grid(area_m)
        print(f"{args.area} tiled into {len(tiles)} blocks ({n_rows} rows x {n_cols} cols of up to "
              f"{TILE_CORE_PX}x{TILE_CORE_PX} px each)")

        model, device = train_cnn.load_checkpoint()
        print(f"Loaded checkpoint: {train_cnn.CHECKPOINT_PATH}")
        mlflow.log_params({
            "area": args.area, "years": ",".join(args.years),
            "n_tiles": len(tiles), "n_rows": n_rows, "n_cols": n_cols,
            "tile_core_px": TILE_CORE_PX, "pixel_m": PIXEL_M, "utm_crs": UTM_CRS,
        })

        # The rasters themselves aren't logged as MLflow artifacts (~27MB each, already excluded
        # from git for the same reason, .gitignore) -- fully reproducible by rerunning this script
        # against the same checkpoint, so the metrics are what's worth tracking per run.
        for period in args.years:
            start, end = PERIODS[period]
            print(f"\nClassifying {period}...")
            raster, proba = classify_period(period, start, end, model, device, area["path"], tiles, n_rows, n_cols)
            mlflow.log_metric(f"unclassified_fraction_{period}", float((raster == UNCLASSIFIED).mean()))
            for name, arr in [(f"{area['prefix']}_classified_{period}.npy", raster), (f"{area['prefix']}_proba_{period}.npy", proba)]:
                np.save(OUT_DIR / name, arr)
                print(f"saved: {OUT_DIR / name}")

        grid_meta = {
            "n_rows": n_rows, "n_cols": n_cols, "tile_core_px": TILE_CORE_PX, "pixel_m": PIXEL_M,
            "utm_crs": UTM_CRS, "aoi_utm_bounds": list(area_m.bounds),
            "class_names": CLASS_NAMES, "unclassified_value": UNCLASSIFIED,
        }
        meta_path = OUT_DIR / f"{area['prefix']}_classified_grid_meta.json"
        meta_path.write_text(json.dumps(grid_meta, indent=2))
        print(f"saved: {meta_path}")
        mlflow.log_artifact(str(meta_path))


if __name__ == "__main__":
    main()
