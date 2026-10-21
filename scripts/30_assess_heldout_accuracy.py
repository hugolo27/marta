"""Held-out accuracy for phase1-accuracy-assessment (task 6.3), two steps:
  classify -- pulls each held-out reference point's 33x33 2023 patch (same neighborhoodToArray +
              sampleRegions mechanism as 14_evaluate_filadelfia_holdout.py, reproject=False since
              Filadelfia straddles UTM 20S/21S) and classifies it with the reference checkpoint.
              Writes heldout_<region>_map.csv, a join file kept out of sight while labeling.
  assess   -- once heldout_<region>_sample.csv is interpreted, scores 2023 forest/non-forest with
              the Stehman (2014) estimator (strata are WorldCover, not our map) and the 90% bar.
A point whose patch has any all-zero pixel (cloud gap / outside) is reported as unclassified, not
fed to the CNN -- same convention as the held-out scripts.
Usage: .venv/bin/python scripts/30_assess_heldout_accuracy.py classify|assess"""

import csv
import importlib
import json
import sys
from pathlib import Path

import ee
import mlflow
import numpy as np

import accuracy_stats as st
import dataset_loader as dl
import gee_session
import holdout_eval
import reference_labels as rl
import s2_utils

assemble = importlib.import_module("08_assemble_dataset")
train_cnn = importlib.import_module("10_train_cnn")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area" / "accuracy_assessment"
EXPERIMENT_NAME = "phase1-accuracy-assessment"
PATCH_RADIUS_PX = 16
PERIOD = ("2023-06-01", "2023-09-30")
BATCH = 25


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def classify_region(name, model, device):
    region = assemble.heldout_rectangle(name)
    points = read_csv(OUT_DIR / f"heldout_{name}_sample_design.csv")
    s2, channels = s2_utils.build_season_composite(region, *PERIOD, model.season, reproject=False, clip=True)
    patch_image = s2.select(channels).neighborhoodToArray(ee.Kernel.square(PATCH_RADIUS_PX, "pixels"))

    rows, gaps = {}, set()
    for i in range(0, len(points), BATCH):
        batch = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([float(p["lon"]), float(p["lat"])]), {"point_id": p["point_id"]})
            for p in points[i:i + BATCH]
        ])
        for feat in patch_image.sampleRegions(collection=batch, scale=10, properties=["point_id"]).getInfo()["features"]:
            props = feat["properties"]
            patch = np.stack([np.array(props[ch]) for ch in channels], axis=-1)
            if np.any(np.all(patch == 0, axis=-1)):
                gaps.add(props["point_id"])
                continue
            rows[props["point_id"]] = {"patch": patch}

    ids = list(rows)
    preds = holdout_eval.predict_cnn([rows[i] for i in ids], model, device) if ids else []
    forest_id = dl.CLASS_NAMES.index("bosque")
    out = []
    for p in points:
        pid = p["point_id"]
        if pid in rows:
            pred = int(preds[ids.index(pid)])
            out.append({"point_id": pid, "map_class": dl.CLASS_NAMES[pred], "map_2023": "forest" if pred == forest_id else "nonforest"})
        else:
            out.append({"point_id": pid, "map_class": "", "map_2023": "", "reason": "gap" if pid in gaps else "not returned"})
    with open(OUT_DIR / f"heldout_{name}_map.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["point_id", "map_class", "map_2023", "reason"])
        w.writeheader()
        w.writerows(out)
    n_ok = sum(bool(o["map_2023"]) for o in out)
    print(f"{name}: {n_ok}/{len(points)} classified, {len(points) - n_ok} unclassified (gap/not returned)")


def accuracy(used, ref, mp, design, n_strata):
    e = st.stehman([design[p]["stratum"] for p in used], ref, mp, n_strata, classes=list(rl.LABELS))
    ci = lambda v, s: {"estimate": float(v), "ci95_low": float(v - st.Z95 * s), "ci95_high": float(v + st.Z95 * s)}
    return e, {
        "overall_accuracy": ci(e["oa"], e["se_oa"]),
        "users_accuracy": {c: ci(u, s) for c, u, s in zip(rl.LABELS, e["ua"], e["se_ua"])},
        "producers_accuracy": {c: ci(u, s) for c, u, s in zip(rl.LABELS, e["pa"], e["se_pa"])},
    }


def assess_region(name):
    design = {r["point_id"]: r for r in read_csv(OUT_DIR / f"heldout_{name}_sample_design.csv")}
    labels = {r["point_id"]: r for r in read_csv(OUT_DIR / f"heldout_{name}_sample.csv")}
    mapped = {r["point_id"]: r for r in read_csv(OUT_DIR / f"heldout_{name}_map.csv")}
    adjudication = OUT_DIR / f"heldout_{name}_adjudication.csv"
    if adjudication.exists():
        for a in read_csv(adjudication):
            for f in rl.DATE_FIELDS:
                if a.get(f, "").strip():
                    labels[a["point_id"]][f"{f}_2023"] = a[f]

    refs = {pid: rl.parse(labels[pid], "2023") for pid in design}
    used = [pid for pid in design if refs[pid] and mapped[pid]["map_2023"]]
    n_strata = {d["stratum"]: int(d["N_h"]) for d in design.values()}
    mp = [mapped[p]["map_2023"] for p in used]
    ref = [refs[p]["label"] for p in used]
    e, cdm = accuracy(used, ref, mp, design, n_strata)
    result = {
        "n_points": len(design), "n_used": len(used),
        "n_uninterpretable": sum(refs[p] is None for p in design),
        "n_unclassified_by_map": sum(not mapped[p]["map_2023"] for p in design),
        **cdm, "meets_90": bool(e["oa"] >= st.VM0007_MIN_OA), "vm0007_gate": st.vm0007_gate(ref, mp, e["oa"], rl.LABELS),
        "frel_secondary": accuracy(used, [rl.frel_label(refs[p]) for p in used], mp, design, n_strata)[1],
    }
    print(f"{name}: OA={e['oa']:.3f} ± {st.Z95 * e['se_oa']:.3f} (n={len(used)}), meets 90%: {result['meets_90']}, "
          f"FREL OA={result['frel_secondary']['overall_accuracy']['estimate']:.3f}")
    return result


def main():
    step = sys.argv[1]
    if step == "classify":
        gee_session.init()
        model, device = train_cnn.load_checkpoint()
        for name in assemble.HELDOUT_REGIONS:
            classify_region(name, model, device)
        return
    results = {name: assess_region(name) for name in assemble.HELDOUT_REGIONS}
    out_path = OUT_DIR / "heldout_accuracy_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="assess_heldout_accuracy"):
        for name, r in results.items():
            mlflow.log_metric(f"oa_{name}", r["overall_accuracy"]["estimate"])
        mlflow.log_artifact(str(out_path))


if __name__ == "__main__":
    main()
