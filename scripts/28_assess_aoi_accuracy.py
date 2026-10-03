"""AOI accuracy assessment for phase1-accuracy-assessment (tasks 5.1-5.4), run once the interpreter
has filled data/study_area/accuracy_assessment/aoi_sample.csv (and aoi_adjudication.csv after the
blind repeat).

- Per-date (2019, 2023) forest/non-forest accuracy of each date's own map + the VM0007 gate.
  The sample was stratified by change class, not by each date's map class, so this uses the
  Stehman (2014) estimator (accuracy_stats.stehman).
- Error-adjusted area of loss / gain / stable forest / stable non-forest with 95% CIs. Strata are
  the map's change classes here, so this is Olofsson et al. (2014); stehman() is used anyway
  because it reproduces olofsson() exactly in that case and also copes with a reference change
  class the map never produced.
- aoi_change_areas.json is the file Fase 2 reads: error-adjusted area first, mapped area only as
  a labeled secondary value.
Point-dates marked uninterpretable are excluded and counted per stratum, never guessed.
Usage: .venv/bin/python scripts/28_assess_aoi_accuracy.py"""

import csv
import json
from pathlib import Path

import mlflow
import numpy as np

import accuracy_stats as st

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area" / "accuracy_assessment"
EXPERIMENT_NAME = "phase1-accuracy-assessment"
PIXEL_HA = 0.01
DATES = ("2019", "2023")
LABELS = ("forest", "nonforest")
CHANGE_CLASSES = ["loss", "gain", "stable_forest", "stable_nonforest"]
TOP_UP_REL_HALF_WIDTH = 0.50


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_points():
    labels = {r["point_id"]: r for r in read_csv(OUT_DIR / "aoi_sample.csv")}
    design = {r["point_id"]: r for r in read_csv(OUT_DIR / "aoi_sample_design.csv")}
    adjudication_path = OUT_DIR / "aoi_adjudication.csv"
    if adjudication_path.exists():
        for a in read_csv(adjudication_path):
            labels[a["point_id"]][f"label_{a['date']}"] = a["adjudicated_label"]
    points = []
    for pid, d in design.items():
        lab = labels[pid]
        for date in DATES:
            value = lab[f"label_{date}"].strip()
            if value and value not in LABELS:
                raise ValueError(f"{pid} label_{date}={value!r}, expected one of {LABELS} or blank (uninterpretable)")
        points.append({**d, **{f"label_{y}": lab[f"label_{y}"].strip() for y in DATES},
                       "flag_sparse_woody": lab["flag_sparse_woody"].strip().lower() in ("1", "true", "yes", "si", "sí", "x")})
    return points


def change_label(before, after):
    return {("forest", "forest"): "stable_forest", ("nonforest", "nonforest"): "stable_nonforest",
            ("forest", "nonforest"): "loss", ("nonforest", "forest"): "gain"}[(before, after)]


def ci(value, se):
    return {"estimate": float(value), "ci95_low": float(value - st.Z95 * se), "ci95_high": float(value + st.Z95 * se)}


def exclusions(points, keep):
    out = {}
    for p in points:
        if not keep(p):
            out[p["stratum"]] = out.get(p["stratum"], 0) + 1
    return out


def main():
    points = load_points()
    n_strata = {p["stratum"]: int(p["N_h"]) for p in points}
    results = {"n_points": len(points), "per_date": {}}

    for date in DATES:
        used = [p for p in points if p[f"label_{date}"]]
        e = st.stehman([p["stratum"] for p in used], [p[f"label_{date}"] for p in used],
                       [p[f"map_{date}"] for p in used], n_strata, classes=list(LABELS))
        gate = st.vm0007_gate([p[f"label_{date}"] for p in used], [p[f"map_{date}"] for p in used], e["oa"], LABELS)
        results["per_date"][date] = {
            "n_used": len(used), "excluded_uninterpretable": exclusions(points, lambda p: p[f"label_{date}"]),
            "overall_accuracy": ci(e["oa"], e["se_oa"]),
            "users_accuracy": {c: ci(u, s) for c, u, s in zip(LABELS, e["ua"], e["se_ua"])},
            "producers_accuracy": {c: ci(u, s) for c, u, s in zip(LABELS, e["pa"], e["se_pa"])},
            "error_matrix_area_proportions": {"rows_map_cols_reference": list(LABELS), "matrix": e["matrix"].tolist()},
            "vm0007_gate": gate,
        }
        print(f"{date}: OA={e['oa']:.3f} ± {st.Z95 * e['se_oa']:.3f}, gate passed={gate['passed']} "
              f"(points by map class {gate['points_by_map_class']}, by reference class {gate['points_by_reference_class']})")

    mapped_forest = [p for p in points if "forest" in (p["map_2019"], p["map_2023"])]
    results["map_forest_flagged_sparse_woody"] = {
        "n_map_forest_points": len(mapped_forest),
        "n_flagged": sum(p["flag_sparse_woody"] for p in mapped_forest),
        "share": (sum(p["flag_sparse_woody"] for p in mapped_forest) / len(mapped_forest)) if mapped_forest else None,
    }

    both = [p for p in points if p["label_2019"] and p["label_2023"]]
    e = st.stehman([p["stratum"] for p in both], [change_label(p["label_2019"], p["label_2023"]) for p in both],
                   [p["stratum"] for p in both], n_strata, classes=CHANGE_CLASSES)
    total_ha = sum(n_strata.values()) * PIXEL_HA
    areas = {}
    for i, c in enumerate(CHANGE_CLASSES):
        areas[c] = {
            "error_adjusted_ha": ci(e["area"][i] * total_ha, e["se_area"][i] * total_ha),
            "mapped_ha_secondary": n_strata.get(c, 0) * PIXEL_HA,
            "users_accuracy": ci(e["ua"][i], e["se_ua"][i]) if not np.isnan(e["ua"][i]) else None,
            "producers_accuracy": ci(e["pa"][i], e["se_pa"][i]) if not np.isnan(e["pa"][i]) else None,
        }
        print(f"{c}: mapped {areas[c]['mapped_ha_secondary']:,.1f} ha -> error-adjusted "
              f"{areas[c]['error_adjusted_ha']['estimate']:,.1f} ha "
              f"[{areas[c]['error_adjusted_ha']['ci95_low']:,.1f}, {areas[c]['error_adjusted_ha']['ci95_high']:,.1f}]")
    loss = areas["loss"]["error_adjusted_ha"]
    half_width = (loss["ci95_high"] - loss["ci95_low"]) / 2
    top_up = loss["estimate"] > 0 and half_width > TOP_UP_REL_HALF_WIDTH * loss["estimate"]
    below_min = any(not results["per_date"][d]["vm0007_gate"]["enough_points"] for d in DATES)
    results["change_areas"] = {"n_used": len(both), "excluded_uninterpretable": exclusions(points, lambda p: p["label_2019"] and p["label_2023"]), "areas": areas}
    results["top_up_needed"] = {"loss_ci_too_wide": bool(top_up), "class_below_50_points": bool(below_min)}
    results["gate_passed_both_dates"] = all(results["per_date"][d]["vm0007_gate"]["passed"] for d in DATES)

    (OUT_DIR / "aoi_accuracy_results.json").write_text(json.dumps(results, indent=2))
    (OUT_DIR / "aoi_change_areas.json").write_text(json.dumps({
        "note": "error_adjusted_ha is the figure to use; mapped_ha_secondary is the raw pixel count, not an assessed area",
        "period": "2019-2023", "areas": {c: {"error_adjusted_ha": a["error_adjusted_ha"], "mapped_ha_secondary": a["mapped_ha_secondary"]} for c, a in areas.items()},
    }, indent=2))
    print(f"gate passed (both dates): {results['gate_passed_both_dates']}, top-up needed: {results['top_up_needed']}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="assess_aoi_accuracy"):
        for d in DATES:
            mlflow.log_metric(f"oa_{d}", results["per_date"][d]["overall_accuracy"]["estimate"])
        mlflow.log_metric("gate_passed", int(results["gate_passed_both_dates"]))
        mlflow.log_metric("loss_error_adjusted_ha", loss["estimate"])
        mlflow.log_artifact(str(OUT_DIR / "aoi_accuracy_results.json"))
        mlflow.log_artifact(str(OUT_DIR / "aoi_change_areas.json"))


if __name__ == "__main__":
    main()
