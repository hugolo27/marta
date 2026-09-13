"""Cross-checks the CNN-derived change map (19_temporal_change_map.py) against MapBiomas' own
year-over-year transitions at the same pixels (phase1-temporal-comparison task 4.1-4.2). A
sanity check on the diff, not a re-validation of per-date accuracy (already settled in
phase1-classifier) -- catches a classifier that's individually accurate on each date but flips
between visually-similar classes (bosque/pasto, the dominant confusion per phase1-classifier
tasks 2.2/3.3) inconsistently between dates, producing spurious "transitions" that are actually
just noise (design.md).
Pulls MapBiomas on the exact same UTM tile grid as 18_classify_aoi_temporal.py (same CRS, same
pixel size) for a direct pixel-index comparison, but without that script's CNN context padding
-- MapBiomas is read directly, no sliding-window inference needed.
Usage: .venv/bin/python scripts/20_mapbiomas_cross_check.py"""

import importlib
import json
from pathlib import Path

import ee
import numpy as np
from shapely.geometry import box
from shapely.ops import transform as shapely_transform

import gee_session
import mapbiomas_legend

classify_aoi = importlib.import_module("18_classify_aoi_temporal")
change_map = importlib.import_module("19_temporal_change_map")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"
PERIOD_BANDS = {"2019": "classification_2019", "2023": "classification_2023"}


def remap_to_our_classes(image, band):
    """MapBiomas' own codes -> our (bosque=0, pasto=1, cultivo=2) scheme directly, treating its
    'other' bucket (natural grassland/bare/water/n/a) as unclassified (-1) rather than a 4th
    class -- we only ever compare the 3 classes our own classifier can produce."""
    from_codes = mapbiomas_legend.BOSQUE + mapbiomas_legend.PASTO + mapbiomas_legend.CULTIVO
    to_codes = [0] * len(mapbiomas_legend.BOSQUE) + [1] * len(mapbiomas_legend.PASTO) + [2] * len(mapbiomas_legend.CULTIVO)
    return image.select(band).remap(from_codes, to_codes, defaultValue=change_map.UNCLASSIFIED).rename(band)


def pull_core(image, band, core_utm):
    minx, miny, maxx, maxy = core_utm.bounds
    lon0, lat0 = classify_aoi.to_wgs84(minx, miny)
    lon1, lat1 = classify_aoi.to_wgs84(maxx, maxy)
    rect = ee.Geometry.Rectangle([lon0, lat0, lon1, lat1])
    result = image.select(band).sampleRectangle(region=rect, defaultValue=change_map.UNCLASSIFIED).getInfo()
    return np.array(result["properties"][band], dtype=np.int64)


def classify_period(mapbiomas, band, tiles, n_rows, n_cols):
    remapped = remap_to_our_classes(mapbiomas, band).reproject(
        crs=classify_aoi.UTM_CRS, scale=classify_aoi.PIXEL_M
    )
    core_px = classify_aoi.TILE_CORE_PX
    full = np.full((n_rows * core_px, n_cols * core_px), change_map.UNCLASSIFIED, dtype=np.int64)
    for t in tiles:
        px0, py0, px1, py1 = t["padded_utm"].bounds
        pad_m = classify_aoi.PATCH_RADIUS_PX * classify_aoi.PIXEL_M
        core_utm = box(px0 + pad_m, py0 + pad_m, px1 - pad_m, py1 - pad_m)
        tile = pull_core(remapped, band, core_utm)
        tile = tile[:core_px, :core_px]
        r0, c0 = t["row"] * core_px, t["col"] * core_px
        h, w = tile.shape
        full[r0:r0 + h, c0:c0 + w] = tile
    return full


def report_agreement(ours, mapbiomas_diff):
    mask = (ours != change_map.UNCLASSIFIED) & (mapbiomas_diff != change_map.UNCLASSIFIED)
    print(f"\nComparable pixels: {mask.sum():,} / {ours.size:,} "
          f"({mask.sum() / ours.size:.1%}) -- both rasters classified\n")

    codes = {change_map.NO_CHANGE: "no_change", **change_map.TRANSITION_NAMES}
    table = {}
    print(f"{'category':<18}{'n_px':>10}{'agree_px':>10}{'agreement':>12}")
    for code, name in codes.items():
        sel = mask & (ours == code)
        n = int(sel.sum())
        if n == 0:
            continue
        agree = int((mapbiomas_diff[sel] == code).sum())
        rate = agree / n
        table[name] = {"n_px": n, "agree_px": agree, "agreement": round(rate, 3)}
        flag = "  <- low agreement, likely classifier noise" if code != change_map.NO_CHANGE and rate < 0.3 else ""
        print(f"{name:<18}{n:>10,}{agree:>10,}{rate:>11.1%}{flag}")
    return table


def main():
    gee_session.init()
    meta = json.loads((DATA_DIR / "aoi_classified_grid_meta.json").read_text())
    ours = np.load(DATA_DIR / "change_map_2019_2023.npy")

    aoi_wgs84 = classify_aoi.load_aoi_geom_wgs84()
    aoi_m = shapely_transform(classify_aoi.to_utm, aoi_wgs84)
    tiles, n_rows, n_cols = classify_aoi.build_tile_grid(aoi_m)
    assert (n_rows, n_cols) == (meta["n_rows"], meta["n_cols"]), "tile grid drifted from 18's saved grid"

    mapbiomas = ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET)
    rasters = {}
    for period, band in PERIOD_BANDS.items():
        print(f"pulling MapBiomas {period}...")
        rasters[period] = classify_period(mapbiomas, band, tiles, n_rows, n_cols)

    mb_diff = change_map.build_change_map(rasters["2019"], rasters["2023"])
    np.save(DATA_DIR / "mapbiomas_change_map_2019_2023.npy", mb_diff)

    table = report_agreement(ours, mb_diff)
    (DATA_DIR / "mapbiomas_agreement.json").write_text(json.dumps(table, indent=2))
    print(f"\nsaved: {DATA_DIR / 'mapbiomas_agreement.json'}")


if __name__ == "__main__":
    main()
