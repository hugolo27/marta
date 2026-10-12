"""Scores the 12 change-map configurations of phase1-change-detection-hardening against Hansen and
MapBiomas over the AOI and the change-development area, then applies the selection rule
pre-registered in data/study_area/change_hardening/README.md (tasks 1.1, 4.1-4.3).

Two steps, run in this order:
  preregister -- hashes the README's pre-registered part (everything above "## Results") and logs
                 it to MLflow before any configuration has been scored
  score       -- refuses to run if that part changed since, then scores and selects

Hansen and MapBiomas are development references, not truth (the interpreted sample in
phase1-accuracy-assessment is the final test and is never used here). Both are 30 m, so they are
pulled on the map's own 10 m UTM tile grid (nearest neighbour, same mechanism as
20_mapbiomas_cross_check.py) and every layer is compared on 3x3-pixel (30 m) blocks.
Usage: .venv/bin/python scripts/26_score_change_configs.py preregister|score"""

import hashlib
import importlib
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import ee
import mlflow
import numpy as np
from shapely.ops import transform as shapely_transform

import gee_session
import mapbiomas_legend

classify_aoi = importlib.import_module("18_classify_aoi_temporal")
change_map = importlib.import_module("19_temporal_change_map")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"
OUT_DIR = DATA_DIR / "change_hardening"
README = OUT_DIR / "README.md"
PREREG_PATH = OUT_DIR / "preregistration.json"
EXPERIMENT_NAME = "phase1-change-detection-hardening"

HANSEN_ASSET = "UMD/hansen/global_forest_change_2025_v1_13"
LOSS_YEARS = (20, 23)
TREECOVER_MIN = 25
BLOCK = 3  # 3x3 px of 10 m = one 30 m block
BLOCK_HA = (BLOCK * classify_aoi.PIXEL_M) ** 2 / 10_000
NODATA = -1

CONFIDENCES = [None, 0.7, 0.9]
GRID = [
    {"confidence": c, "persistence": p, "mmu": m}
    for c, p, m in itertools.product(CONFIDENCES, [False, True], [False, True])
]
MIN_RETENTION = 0.50
TIE_FACTOR = 1.10


def preregistered_text():
    text = README.read_text()
    return text[:text.index("## Results")]


def preregister():
    digest = hashlib.sha256(preregistered_text().encode()).hexdigest()
    record = {"sha256": digest, "utc": datetime.now(timezone.utc).isoformat()}
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="preregistration"):
        mlflow.log_param("readme_sha256", digest)
        mlflow.log_artifact(str(README))
    PREREG_PATH.write_text(json.dumps(record, indent=2))
    print(f"pre-registered {README} sha256={digest}")


def reference_image(area_ee):
    h = ee.Image(HANSEN_ASSET)
    loss = (h.select("lossyear").gte(LOSS_YEARS[0]).And(h.select("lossyear").lte(LOSS_YEARS[1]))
            .And(h.select("treecover2000").gte(TREECOVER_MIN))).unmask(0).rename("hansen_loss")
    mb = ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET)
    from_codes = mapbiomas_legend.BOSQUE + mapbiomas_legend.PASTO + mapbiomas_legend.CULTIVO + mapbiomas_legend.OTHER
    to_codes = [1] * len(mapbiomas_legend.BOSQUE) + [0] * (len(from_codes) - len(mapbiomas_legend.BOSQUE))
    mb_forest = [
        mb.select(f"classification_{y}").remap(from_codes, to_codes, defaultValue=NODATA).rename(f"mb_forest_{y}")
        for y in (2019, 2023)
    ]
    # int16: Hansen's loss band is unsigned and sampleRectangle rejects the -1 default otherwise
    return (ee.Image.cat([loss, *mb_forest]).toInt16().clip(area_ee)
            .reproject(crs=classify_aoi.UTM_CRS, scale=classify_aoi.PIXEL_M))


def pull_references(area_path, meta):
    """Same tile grid and core-only pull as 20_mapbiomas_cross_check.py, so reference pixel
    (r, c) is the same ground location as map pixel (r, c)."""
    area_m = shapely_transform(classify_aoi.to_utm, classify_aoi.load_aoi_geom_wgs84(area_path))
    tiles, n_rows, n_cols = classify_aoi.build_tile_grid(area_m)
    assert (n_rows, n_cols) == (meta["n_rows"], meta["n_cols"]), "tile grid drifted from 18's saved grid"
    area_ee = ee.Geometry(json.loads(area_path.read_text())["features"][0]["geometry"])
    image = reference_image(area_ee)
    bands = ["hansen_loss", "mb_forest_2019", "mb_forest_2023"]

    core_px, pad_m = classify_aoi.TILE_CORE_PX, classify_aoi.PATCH_RADIUS_PX * classify_aoi.PIXEL_M
    full = {b: np.full((n_rows * core_px, n_cols * core_px), NODATA, dtype=np.int64) for b in bands}
    for t in tiles:
        px0, py0, px1, py1 = t["padded_utm"].bounds
        x0, y0, x1, y1 = px0 + pad_m, py0 + pad_m, px1 - pad_m, py1 - pad_m
        lon0, lat0 = classify_aoi.to_wgs84(x0, y0)
        lon1, lat1 = classify_aoi.to_wgs84(x1, y1)
        result = image.sampleRectangle(region=ee.Geometry.Rectangle([lon0, lat0, lon1, lat1]), defaultValue=NODATA).getInfo()
        r0, c0 = t["row"] * core_px, t["col"] * core_px
        for b in bands:
            tile = np.array(result["properties"][b], dtype=np.int64)[:core_px, :core_px]
            full[b][r0:r0 + tile.shape[0], c0:c0 + tile.shape[1]] = tile
    return full


def blocks(arr):
    h, w = (arr.shape[0] // BLOCK) * BLOCK, (arr.shape[1] // BLOCK) * BLOCK
    return arr[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK).swapaxes(1, 2).reshape(h // BLOCK, w // BLOCK, BLOCK * BLOCK)


def majority_is(arr, value):
    return (blocks(arr) == value).sum(-1) > (BLOCK * BLOCK) // 2


def block_references(refs):
    valid = ~majority_is(refs["hansen_loss"], NODATA) & ~majority_is(refs["mb_forest_2019"], NODATA) & ~majority_is(refs["mb_forest_2023"], NODATA)
    hansen = majority_is(refs["hansen_loss"], 1)
    mb_loss = majority_is(refs["mb_forest_2019"], 1) & majority_is(refs["mb_forest_2023"], 0)
    return {
        "valid": valid, "hansen": hansen & valid, "mapbiomas": mb_loss & valid,
        "confirmed_loss": hansen & mb_loss & valid,
        "confirmed_stable_forest": majority_is(refs["mb_forest_2019"], 1) & majority_is(refs["mb_forest_2023"], 1) & ~hansen & valid,
    }


def load_area(prefix):
    meta = json.loads((DATA_DIR / f"{prefix}_classified_grid_meta.json").read_text())
    rasters = {y: np.load(DATA_DIR / f"{prefix}_classified_{y}.npy") for y in ("2019", "2022", "2023")}
    probas = {y: np.load(DATA_DIR / f"{prefix}_proba_{y}.npy") for y in ("2019", "2023")}
    return meta, rasters, probas


def score_area(change, ref):
    mapped_valid = ~majority_is(change, change_map.UNCLASSIFIED)
    valid = ref["valid"] & mapped_valid
    loss = majority_is(change, change_map.LOSS) & valid

    def rate(num, den):
        return round(float(num.sum() / den.sum()), 4) if den.sum() else None

    cl = ref["confirmed_loss"] & valid
    return {
        "map_loss_ha": round(float(loss.sum() * BLOCK_HA), 1),
        "confirmed_loss_ha": round(float(cl.sum() * BLOCK_HA), 1),
        "retention": rate(loss & cl, cl),
        "false_loss_ha": round(float((loss & ~cl).sum() * BLOCK_HA), 1),
        "stable_forest_kept": rate(ref["confirmed_stable_forest"] & valid & ~loss, ref["confirmed_stable_forest"] & valid),
        "vs_hansen": {"map_loss_confirmed": rate(loss & ref["hansen"], loss), "hansen_loss_captured": rate(loss & ref["hansen"], ref["hansen"] & valid)},
        "vs_mapbiomas": {"map_loss_confirmed": rate(loss & ref["mapbiomas"], loss), "mapbiomas_loss_captured": rate(loss & ref["mapbiomas"], ref["mapbiomas"] & valid)},
    }


def n_active(cfg):
    return (cfg["confidence"] is not None) + cfg["persistence"] + cfg["mmu"]


def select(rows):
    qualifying = [r for r in rows if (r["dev"]["retention"] or 0) >= MIN_RETENTION]
    if not qualifying:
        return None
    m = min(r["aoi"]["false_loss_ha"] for r in qualifying)
    near = [r for r in qualifying if r["aoi"]["false_loss_ha"] <= TIE_FACTOR * m]
    return min(near, key=lambda r: (n_active(r["config"]), r["aoi"]["false_loss_ha"], r["config"]["confidence"] or 0))


def score():
    prereg = json.loads(PREREG_PATH.read_text())
    digest = hashlib.sha256(preregistered_text().encode()).hexdigest()
    if digest != prereg["sha256"]:
        sys.exit("pre-registered part of README changed since preregistration -- refusing to score")

    gee_session.init()
    areas = {"aoi": classify_aoi.AREAS["aoi"]["path"], "dev": classify_aoi.AREAS["dev"]["path"]}
    data, refs = {}, {}
    for name, path in areas.items():
        meta, rasters, probas = load_area(name)
        print(f"pulling references for {name}...")
        refs[name] = block_references(pull_references(path, meta))
        data[name] = (rasters, probas)
        print(f"  confirmed loss: {refs[name]['confirmed_loss'].sum() * BLOCK_HA:,.1f} ha, "
              f"confirmed stable forest: {refs[name]['confirmed_stable_forest'].sum() * BLOCK_HA:,.1f} ha")

    rows = []
    for cfg in GRID:
        row = {"config": cfg}
        for name, (rasters, probas) in data.items():
            change = change_map.build_fnf_change_map(rasters, probas, cfg["confidence"], cfg["persistence"], cfg["mmu"])
            row[name] = score_area(change, refs[name])
        rows.append(row)
        print(f"{cfg}: dev retention={row['dev']['retention']}, dev map loss={row['dev']['map_loss_ha']:,.1f} ha, "
              f"AOI false loss={row['aoi']['false_loss_ha']:,.1f} ha")

    selected = select(rows)
    result = {
        "preregistration": prereg, "references": {"hansen": HANSEN_ASSET, "mapbiomas": mapbiomas_legend.MAPBIOMAS_ASSET},
        "confirmed_loss_ha": {n: round(float(refs[n]["confirmed_loss"].sum() * BLOCK_HA), 1) for n in refs},
        "rows": rows, "selected": selected["config"] if selected else None,
    }
    out_path = OUT_DIR / "scores.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nselected: {result['selected']}")
    print(f"saved: {out_path}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="score_change_configs"):
        mlflow.log_param("readme_sha256", digest)
        mlflow.log_param("selected", json.dumps(result["selected"]))
        for i, r in enumerate(rows):
            mlflow.log_metrics({f"cfg{i}_dev_retention": r["dev"]["retention"] or 0, f"cfg{i}_aoi_false_loss_ha": r["aoi"]["false_loss_ha"]})
        mlflow.log_artifact(str(out_path))


if __name__ == "__main__":
    {"preregister": preregister, "score": score}[sys.argv[1]]()
