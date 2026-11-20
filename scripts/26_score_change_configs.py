"""Scores the 12 change-map configurations on the U-Net maps against Hansen and MapBiomas over the
change-development area, then applies the selection rule pre-registered in
data/study_area/unet_change/README.md (phase1-segmentation D6). The AOI is scored too, for the
record, but plays no part in the choice.

Two steps, run in this order:
  preregister -- hashes the README's pre-registered part (everything above "## Results") and logs
                 it to MLflow before any configuration has been scored
  score       -- refuses to run if that part changed since, then scores and selects

Hansen and MapBiomas are development references, not truth (the interpreted sample in
phase1-accuracy-assessment is the final test and is never used here). Both are 30 m, like the
U-Net maps, so they are pulled by nearest neighbour onto the map's own 30 m cells
(tile_inference.label_cells) and compared cell by cell. The CNN version, on 10 m pixels and 3x3
blocks with false loss measured in the AOI, is in git history and in change_hardening/.
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

import gee_session
import mapbiomas_legend
import tile_inference

classify_aoi = importlib.import_module("18_classify_aoi_temporal")
change_map = importlib.import_module("19_temporal_change_map")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"
OUT_DIR = DATA_DIR / "unet_change"
README = OUT_DIR / "README.md"
PREREG_PATH = OUT_DIR / "preregistration.json"
EXPERIMENT_NAME = "phase1-segmentation-change"

HANSEN_ASSET = "UMD/hansen/global_forest_change_2025_v1_13"
LOSS_YEARS = (20, 23)
TREECOVER_MIN = 25
CELL_HA = classify_aoi.PIXEL_M ** 2 / 10_000
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


def reference_images():
    h = ee.Image(HANSEN_ASSET)
    loss = (h.select("lossyear").gte(LOSS_YEARS[0]).And(h.select("lossyear").lte(LOSS_YEARS[1]))
            .And(h.select("treecover2000").gte(TREECOVER_MIN))).unmask(0).toInt16().rename("hansen_loss")
    mb = ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET)
    from_codes = mapbiomas_legend.BOSQUE + mapbiomas_legend.PASTO + mapbiomas_legend.CULTIVO + mapbiomas_legend.OTHER
    to_codes = [1] * len(mapbiomas_legend.BOSQUE) + [0] * (len(from_codes) - len(mapbiomas_legend.BOSQUE))
    mb_forest = {
        f"mb_forest_{y}": mb.select(f"classification_{y}").remap(from_codes, to_codes, defaultValue=NODATA)
        .unmask(NODATA).toInt16().rename(f"mb_forest_{y}")
        for y in (2019, 2023)
    }
    return {"hansen_loss": loss, **mb_forest}


def references(meta):
    refs = {b: tile_inference.label_cells(tile_inference.grid_from_meta(meta), image).astype(np.int64) for b, image in reference_images().items()}
    valid = (refs["mb_forest_2019"] != NODATA) & (refs["mb_forest_2023"] != NODATA)
    hansen = refs["hansen_loss"] == 1
    mb_loss = (refs["mb_forest_2019"] == 1) & (refs["mb_forest_2023"] == 0)
    return {
        "valid": valid, "hansen": hansen & valid, "mapbiomas": mb_loss & valid,
        "confirmed_loss": hansen & mb_loss & valid,
        "confirmed_stable_forest": (refs["mb_forest_2019"] == 1) & (refs["mb_forest_2023"] == 1) & ~hansen & valid,
    }


def load_area(prefix):
    meta = json.loads((DATA_DIR / f"{prefix}_classified_grid_meta.json").read_text())
    rasters = {y: np.load(DATA_DIR / f"{prefix}_classified_{y}.npy") for y in ("2019", "2022", "2023")}
    probas = {y: np.load(DATA_DIR / f"{prefix}_proba_{y}.npy") for y in ("2019", "2023")}
    return meta, rasters, probas


def score_area(change, ref):
    valid = ref["valid"] & (change != change_map.UNCLASSIFIED)
    loss = (change == change_map.LOSS) & valid

    def rate(num, den):
        return round(float(num.sum() / den.sum()), 4) if den.sum() else None

    cl = ref["confirmed_loss"] & valid
    csf = ref["confirmed_stable_forest"] & valid
    return {
        "map_loss_ha": round(float(loss.sum() * CELL_HA), 1),
        "confirmed_loss_ha": round(float(cl.sum() * CELL_HA), 1),
        "retention": rate(loss & cl, cl),
        "false_loss_ha": round(float((loss & csf).sum() * CELL_HA), 1),
        "loss_not_confirmed_ha": round(float((loss & ~cl).sum() * CELL_HA), 1),
        "stable_forest_kept": rate(csf & ~loss, csf),
        "vs_hansen": {"map_loss_confirmed": rate(loss & ref["hansen"], loss), "hansen_loss_captured": rate(loss & ref["hansen"], ref["hansen"] & valid)},
        "vs_mapbiomas": {"map_loss_confirmed": rate(loss & ref["mapbiomas"], loss), "mapbiomas_loss_captured": rate(loss & ref["mapbiomas"], ref["mapbiomas"] & valid)},
    }


def n_active(cfg):
    return (cfg["confidence"] is not None) + cfg["persistence"] + cfg["mmu"]


def select(rows):
    qualifying = [r for r in rows if (r["dev"]["retention"] or 0) >= MIN_RETENTION]
    if not qualifying:
        return None
    m = min(r["dev"]["false_loss_ha"] for r in qualifying)
    near = [r for r in qualifying if r["dev"]["false_loss_ha"] <= TIE_FACTOR * m]
    return min(near, key=lambda r: (n_active(r["config"]), r["dev"]["false_loss_ha"], r["config"]["confidence"] or 0))


def score():
    prereg = json.loads(PREREG_PATH.read_text())
    digest = hashlib.sha256(preregistered_text().encode()).hexdigest()
    if digest != prereg["sha256"]:
        sys.exit("pre-registered part of README changed since preregistration -- refusing to score")

    gee_session.init()
    data, refs = {}, {}
    for name in ("aoi", "dev"):
        meta, rasters, probas = load_area(name)
        print(f"pulling references for {name}...")
        # Only cells the map classified: the grid's padding outside the area is not part of it
        refs[name] = {k: v & (rasters["2019"] != change_map.UNCLASSIFIED) for k, v in references(meta).items()}
        data[name] = (rasters, probas)
        print(f"  confirmed loss: {refs[name]['confirmed_loss'].sum() * CELL_HA:,.1f} ha, "
              f"confirmed stable forest: {refs[name]['confirmed_stable_forest'].sum() * CELL_HA:,.1f} ha")

    rows = []
    for cfg in GRID:
        row = {"config": cfg}
        for name, (rasters, probas) in data.items():
            change = change_map.build_fnf_change_map(rasters, probas, cfg["confidence"], cfg["persistence"], cfg["mmu"])
            row[name] = score_area(change, refs[name])
        rows.append(row)
        print(f"{cfg}: dev retention={row['dev']['retention']}, dev map loss={row['dev']['map_loss_ha']:,.1f} ha, "
              f"dev false loss={row['dev']['false_loss_ha']:,.1f} ha")

    selected = select(rows)
    result = {
        "preregistration": prereg, "references": {"hansen": HANSEN_ASSET, "mapbiomas": mapbiomas_legend.MAPBIOMAS_ASSET},
        "confirmed_loss_ha": {n: round(float(refs[n]["confirmed_loss"].sum() * CELL_HA), 1) for n in refs},
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
            mlflow.log_metrics({f"cfg{i}_dev_retention": r["dev"]["retention"] or 0, f"cfg{i}_dev_false_loss_ha": r["dev"]["false_loss_ha"]})
        mlflow.log_artifact(str(out_path))


if __name__ == "__main__":
    {"preregister": preregister, "score": score}[sys.argv[1]]()
