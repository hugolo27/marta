"""Tile dataset for the U-Net (phase1-segmentation D1, D2). Each example: a 192x192 Sentinel-2
tile (26 channels: dry composite then wet, as in 08_assemble_dataset.py) on Sentinel-2's own UTM
10 m grid, plus the MapBiomas label map of the same ground at 30 m (64x64), saved as
data/study_area/tiles/data/<period>_<n>.npz with a manifest. 96 and 48 px tiles are center crops.

Tile edges sit at multiples of 30 m in the UTM zone of the tile center. Native scenes have offsets
that are multiples of 10 m in both zones of the footprint, so the 10 m bands are not resampled;
MapBiomas (EPSG:4326, 27-28 x 30 m here) is resampled by nearest neighbour onto the 30 m cells
instead, each one an exact 3x3 block of image pixels (checked on 5 tiles, task 1.1). A 3-department
footprint spans UTM 20S and 21S, so each tile is pulled in its own zone with computePixels rather
than through one shared projection (see s2_utils.build_s2_composite's reproject param).

Points are sampled as in 08 (stratified on the center class, both years) but a point is kept only
if its whole tile stays out of the held-out regions. Splits: 6 km blocks regardless of class; 20%
of the blocks go to the test reserve, which the pilot never reads, and the rest to a pool that the
pilot splits into train and validation (D4). Tiles of different groups closer than the tile
diagonal are dropped, so no two of them share ground.

Bands are stored as int16 (reflectance as delivered) and NDVI as int16 x NDVI_SCALE; the loader
divides it back. A tile with more than MAX_GAP_FRACTION gap pixels in either composite is dropped;
label cells over the remaining gap pixels are set to 0 (ignored).

More tiles (task 3.4): --batch 2 samples new points with seed 43 and appends them. Blocks already
in the dataset keep their group and a shuffled 20% of the new blocks go to the reserve; a new point
closer than the tile diagonal to a tile of the other group is dropped, existing tiles never are.

Usage: .venv/bin/python scripts/35_assemble_tiles.py [--batch N] [--limit N]"""

import argparse
import csv
import importlib
import json
import math
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee
import numpy as np
from pyproj import Transformer

import gee_session
import mapbiomas_legend
import s2_utils

assemble = importlib.import_module("08_assemble_dataset")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area" / "tiles"
DATA_DIR = OUT_DIR / "data"

TILE_PX = 192
LABEL_PX = TILE_PX // 3
TILE_M = TILE_PX * 10
N_TILES = 2000  # upper end of the learning curve (D4); more are extracted if it still climbs
N_PER_CLASS = math.ceil(N_TILES / (3 * len(assemble.PERIODS)))
RESERVE_SHARE = 0.20  # test reserve, set aside before the pilot (D4)
MIN_EVAL_SHARE = assemble.MIN_EVAL_SHARE
MAX_GAP_FRACTION = s2_utils.MAX_GAP_FRACTION
NDVI_SCALE = 10000
WORKERS = 8
CHANNELS = s2_utils.S2_BANDS + ["NDVI"] + [f"{c}_wet" for c in s2_utils.S2_BANDS + ["NDVI"]]


def sampling_area():
    """The 08 footprint minus each held-out region grown by half the tile diagonal, so no tile
    centered in it reaches into a held-out region."""
    area = assemble.wider_footprint_minus_heldout()
    for name in assemble.HELDOUT_REGIONS:
        area = area.difference(assemble.heldout_rectangle(name).buffer(TILE_M / math.sqrt(2)), ee.ErrorMargin(1))
    return area


def sample_points(area, batch):
    points = []
    for period in assemble.PERIODS:
        label = label_image(period)
        sample = label.updateMask(label.gt(0)).stratifiedSample(
            numPoints=N_PER_CLASS, classBand="label", region=area, scale=30, seed=41 + batch, geometries=True,
        ).getInfo()["features"]
        points += [{"lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
                    "class_id": int(f["properties"]["label"]), "period": period, "batch": batch} for f in sample]
    return points


def label_image(period):
    band = f"classification_{period}"
    return ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET).select(band).remap(
        *mapbiomas_legend.remap_expression(band), defaultValue=0).rename("label")


def assign_groups(points, existing=(), seed=42):
    """6 km blocks regardless of class (phase1-dataset-v2 D2); a shuffled 20% of them is the test
    reserve, the rest the pool. Blocks of existing tiles keep their group."""
    known = {assemble.block_key(p["lon"], p["lat"]): p["group"] for p in existing}
    blocks = sorted({assemble.block_key(p["lon"], p["lat"]) for p in points} - known.keys())
    random.Random(seed).shuffle(blocks)
    reserve = set(blocks[:round(len(blocks) * RESERVE_SHARE)])
    for p in points:
        b = assemble.block_key(p["lon"], p["lat"])
        p["group"] = known.get(b) or ("reserve" if b in reserve else "pool")
    print(f"  {len(blocks)} new blocks of {assemble.BLOCK_KM} km: {len(reserve)} reserve, {len(blocks) - len(reserve)} pool")


def drop_overlapping(points, existing=()):
    """Drops both tiles of any reserve/pool pair closer than the tile diagonal, and any point that
    close to an existing tile of the other group."""
    lon = np.array([p["lon"] for p in points])
    lat = np.array([p["lat"] for p in points])
    group = np.array([p["group"] for p in points])
    old_lon = np.array([p["lon"] for p in existing])
    old_lat = np.array([p["lat"] for p in existing])
    old_group = np.array([p["group"] for p in existing])
    to_drop = set()
    for i in range(len(points)):
        d = assemble.haversine_m(lon[i], lat[i], lon[i + 1:], lat[i + 1:])
        close = np.nonzero((group[i + 1:] != group[i]) & (d < TILE_M * math.sqrt(2)))[0]
        if close.size:
            to_drop.add(i)
            to_drop.update((close + i + 1).tolist())
        if len(existing) and np.any((old_group != group[i]) &
                                    (assemble.haversine_m(lon[i], lat[i], old_lon, old_lat) < TILE_M * math.sqrt(2))):
            to_drop.add(i)
    print(f"  overlap check: dropping {len(to_drop)} tiles")
    return [p for i, p in enumerate(points) if i not in to_drop], len(to_drop)


def check_class_balance(points):
    counts = {}
    for p in points:
        counts.setdefault(p["class_id"], {"reserve": 0, "pool": 0})[p["group"]] += 1
    for class_id, c in sorted(counts.items()):
        share = c["reserve"] / sum(c.values())
        print(f"  class {class_id}: {c} ({share:.1%} reserve)")
        if share < MIN_EVAL_SHARE:
            sys.exit(f"class {class_id} below {MIN_EVAL_SHARE:.0%} in the test reserve -- refusing to build")
    return counts


def tile_grid(p):
    epsg = 32700 + int((p["lon"] + 180) // 6) + 1
    x, y = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True).transform(p["lon"], p["lat"])
    x0 = math.floor(x / 30) * 30 - TILE_M // 2
    y0 = math.floor(y / 30) * 30 + 30 + TILE_M // 2
    return epsg, x0, y0


def grid(epsg, x0, y0, px, size):
    return {"dimensions": {"width": size, "height": size},
            "affineTransform": {"scaleX": px, "shearX": 0, "translateX": x0, "shearY": 0, "scaleY": -px, "translateY": y0},
            "crsCode": f"EPSG:{epsg}"}


def extract(p):
    epsg, x0, y0 = tile_grid(p)
    region = ee.Geometry.Rectangle([x0, y0 - TILE_M, x0 + TILE_M, y0], f"EPSG:{epsg}", False)
    start, end = assemble.PERIODS[p["period"]]
    s2, channels = s2_utils.build_season_composite(region, start, end, "drywet", reproject=False)
    pixels = ee.data.computePixels({"expression": s2.select(channels), "fileFormat": "NUMPY_NDARRAY",
                                    "grid": grid(epsg, x0, y0, 10, TILE_PX)})
    image = np.stack([pixels[c] for c in channels], axis=-1).astype(np.float64)
    label = ee.data.computePixels({"expression": label_image(p["period"]), "fileFormat": "NUMPY_NDARRAY",
                                   "grid": grid(epsg, x0, y0, 30, LABEL_PX)})["label"].astype(np.uint8)

    n = len(s2_utils.S2_BANDS) + 1
    gap = np.all(image[..., :n] == 0, axis=-1) | np.all(image[..., n:] == 0, axis=-1)
    dry_gap = float(np.all(image[..., :n] == 0, axis=-1).mean())
    wet_gap = float(np.all(image[..., n:] == 0, axis=-1).mean())
    label[gap.reshape(LABEL_PX, 3, LABEL_PX, 3).any(axis=(1, 3))] = 0

    ndvi = [channels.index("NDVI"), channels.index("NDVI_wet")]
    image[..., ndvi] *= NDVI_SCALE
    image = np.clip(np.rint(image), -32768, 32767).astype(np.int16)
    return image, label, {"epsg": epsg, "x0": x0, "y0": y0, "dry_gap": round(dry_gap, 4), "wet_gap": round(wet_gap, 4)}


def process(item):
    i, p = item
    path = DATA_DIR / f"{p['period']}_{i:04d}.npz"
    meta_path = path.with_suffix(".json")
    if meta_path.exists():
        return {**json.loads(meta_path.read_text()), **p}
    image, label, meta = extract(p)
    row = {**p, **meta, "path": str(path.relative_to(REPO_ROOT)),
           "center_class": mapbiomas_legend.CLASS_NAMES[p["class_id"]],
           **{f"px_{name}": int((label == k).sum()) for k, name in mapbiomas_legend.CLASS_NAMES.items()}}
    row["kept"] = max(meta["dry_gap"], meta["wet_gap"]) <= MAX_GAP_FRACTION
    if row["kept"]:
        np.savez_compressed(path, image=image, label=label)
    meta_path.write_text(json.dumps(row))
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--limit", type=int, help="extract only the first N tiles of the batch (timing run)")
    args = parser.parse_args()

    gee_session.init()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    points_path = OUT_DIR / "points.json"
    points = json.loads(points_path.read_text()) if points_path.exists() else []
    stats = json.loads((OUT_DIR / "build_stats.json").read_text()) if points else {"tile_px": TILE_PX, "block_km": assemble.BLOCK_KM}
    if not any(p["batch"] == args.batch for p in points):
        new = sample_points(sampling_area(), args.batch)
        assign_groups(new, points, seed=41 + args.batch)
        new, n_overlap = drop_overlapping(new, points)
        points += new
        balance = check_class_balance(points)
        points_path.write_text(json.dumps(points))
        stats.setdefault("batches", {})[str(args.batch)] = {"points_sampled": len(new) + n_overlap, "dropped_overlap": n_overlap}
        stats["center_class_by_group"] = {mapbiomas_legend.CLASS_NAMES[k]: v for k, v in balance.items()}
        (OUT_DIR / "build_stats.json").write_text(json.dumps(stats, indent=2))

    items = list(enumerate(points))
    if args.limit:
        items = [(i, p) for i, p in items if p["batch"] == args.batch][:args.limit]
    rows = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for n, row in enumerate(pool.map(process, items), 1):
            rows.append(row)
            if n % 50 == 0 or n == len(items):
                print(f"  {n}/{len(items)} tiles", flush=True)
    if args.limit:
        return

    kept = [r for r in rows if r["kept"]]
    fields = ["path", "period", "center_class", "group", "batch", "lon", "lat", "epsg", "x0", "y0", "dry_gap", "wet_gap"] + \
             [f"px_{name}" for name in mapbiomas_legend.CLASS_NAMES.values()]
    with open(OUT_DIR / "manifest.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept)

    label_px = {name: sum(r[f"px_{name}"] for r in kept) for name in mapbiomas_legend.CLASS_NAMES.values()}
    stats.update({"tiles": len(kept), "dropped_gap": len(rows) - len(kept),
                  "tiles_by_group": {g: sum(r["group"] == g for r in kept) for g in ("pool", "reserve")},
                  "tiles_by_batch": {str(b): sum(r["batch"] == b for r in kept) for b in sorted({r["batch"] for r in kept})},
                  "label_px": label_px, "ignored_share": round(label_px["other"] / sum(label_px.values()), 4)})
    (OUT_DIR / "build_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
