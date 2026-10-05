"""AOI accuracy assessment for phase1-accuracy-assessment (tasks 5.1-5.4), run once the interpreter
has filled data/study_area/accuracy_assessment/aoi_sample.csv (and aoi_adjudication.csv after the
blind repeat).

The sample's strata (27_draw_reference_sample.py) are not the map's classes, so everything here
uses the Stehman (2014) estimator with each point's stored map class.
- Per-date (2019, 2023) forest/non-forest accuracy of each date's own map + the VM0007 gate, under
  the PD's CDM definition (primary, fixed before interpretation). The FREL definition is reported
  as a secondary analysis, derived from the recorded crown/patch/height attributes. The gate uses
  the area-weighted overall accuracy; the unweighted count the PD's formula literally describes is
  reported next to it, since on a sample that oversamples change it is not an estimate of the
  map's accuracy.
- Error-adjusted area of loss / gain / stable forest / stable non-forest with 95% CIs. The user's
  accuracy of loss is the headline number: in a near-intact AOI the overall accuracy says little.
  When a stratum shows no reference loss at all, its contribution to the loss SE is zero, so the
  rule-of-three upper bound (3 * stratum area / n) is reported instead of a falsely narrow CI.
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
import reference_labels as rl

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area" / "accuracy_assessment"
EXPERIMENT_NAME = "phase1-accuracy-assessment"
PIXEL_HA = 0.01
DATES = ("2019", "2023")
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
            for f in rl.DATE_FIELDS:
                if a.get(f, "").strip():
                    labels[a["point_id"]][f"{f}_{a['date']}"] = a[f]
    return [{**d, **{f"ref_{y}": rl.parse(labels[pid], y) for y in DATES}} for pid, d in design.items()]


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


def per_date_accuracy(used, date, n_strata, reference):
    ref = [reference(p[f"ref_{date}"]) for p in used]
    mapped = [p[f"map_{date}"] for p in used]
    e = st.stehman([p["stratum"] for p in used], ref, mapped, n_strata, classes=list(rl.LABELS))
    return e, ref, mapped, {
        "n_used": len(used),
        "overall_accuracy": ci(e["oa"], e["se_oa"]),
        "overall_accuracy_unweighted": float(np.mean(np.array(ref) == np.array(mapped))),
        "users_accuracy": {c: ci(u, s) for c, u, s in zip(rl.LABELS, e["ua"], e["se_ua"])},
        "producers_accuracy": {c: ci(u, s) for c, u, s in zip(rl.LABELS, e["pa"], e["se_pa"])},
        "error_matrix_area_proportions": {"rows_map_cols_reference": list(rl.LABELS), "matrix": e["matrix"].tolist()},
    }


def zero_omission_bounds(both, n_strata):
    """Rule of three per stratum with no reference loss among its interpreted points."""
    out = {}
    for stratum, big_n in n_strata.items():
        pts = [p for p in both if p["stratum"] == stratum]
        if pts and not any(change_label(p["ref_2019"]["label"], p["ref_2023"]["label"]) == "loss" for p in pts):
            out[stratum] = 3 * big_n * PIXEL_HA / len(pts)
    return out


def main():
    points = load_points()
    strata_info = json.loads((OUT_DIR / "aoi_sample_strata.json").read_text())
    n_strata = {p["stratum"]: int(p["N_h"]) for p in points}
    results = {"n_points": len(points), "primary_definition": "CDM (PD): >= 25% crown, >= 0.5 ha, >= 5 m", "per_date": {}}

    for date in DATES:
        used = [p for p in points if p[f"ref_{date}"]]
        e, ref, mapped, cdm = per_date_accuracy(used, date, n_strata, lambda r: r["label"])
        cdm["excluded_uninterpretable"] = exclusions(points, lambda p: p[f"ref_{date}"])
        cdm["vm0007_gate"] = st.vm0007_gate(ref, mapped, e["oa"], rl.LABELS)
        clear = [p for p in used if not p[f"ref_{date}"]["near_threshold"]]
        cdm["without_near_threshold"] = per_date_accuracy(clear, date, n_strata, lambda r: r["label"])[3]
        frel = {
            "height_indeterminate_counts_as_met": per_date_accuracy(used, date, n_strata, rl.frel_label)[3],
            "height_indeterminate_counts_as_not_met": per_date_accuracy(
                used, date, n_strata, lambda r: rl.frel_label(r, indeterminate_height_ok=False))[3],
            "n_height_indeterminate": sum(p[f"ref_{date}"]["height"] == "indeterminate" for p in used),
        }
        results["per_date"][date] = {"cdm": cdm, "frel_secondary": frel}
        gate = cdm["vm0007_gate"]
        print(f"{date}: OA={e['oa']:.3f} ± {st.Z95 * e['se_oa']:.3f} (unweighted {cdm['overall_accuracy_unweighted']:.3f}), "
              f"gate passed={gate['passed']} (by map class {gate['points_by_map_class']}, by reference class "
              f"{gate['points_by_reference_class']}); FREL OA={frel['height_indeterminate_counts_as_met']['overall_accuracy']['estimate']:.3f}")

    mapped_forest = [p for p in points if any(p[f"map_{y}"] == "forest" and p[f"ref_{y}"] for y in DATES)]
    n_sparse = sum(any(p[f"map_{y}"] == "forest" and p[f"ref_{y}"] and rl.sparse_woody(p[f"ref_{y}"]) for y in DATES)
                   for p in mapped_forest)
    results["map_forest_on_sparse_woody"] = {
        "n_map_forest_points": len(mapped_forest), "n_sparse_woody": n_sparse,
        "share": n_sparse / len(mapped_forest) if mapped_forest else None,
    }

    both = [p for p in points if p["ref_2019"] and p["ref_2023"]]
    e = st.stehman([p["stratum"] for p in both], [change_label(p["ref_2019"]["label"], p["ref_2023"]["label"]) for p in both],
                   [p["map_change"] for p in both], n_strata, classes=CHANGE_CLASSES)
    total_ha = sum(n_strata.values()) * PIXEL_HA
    areas = {}
    for i, c in enumerate(CHANGE_CLASSES):
        areas[c] = {
            "error_adjusted_ha": ci(e["area"][i] * total_ha, e["se_area"][i] * total_ha),
            "mapped_ha_secondary": strata_info["map_change_px"][c] * PIXEL_HA,
            "users_accuracy": ci(e["ua"][i], e["se_ua"][i]) if not np.isnan(e["ua"][i]) else None,
            "producers_accuracy": ci(e["pa"][i], e["se_pa"][i]) if not np.isnan(e["pa"][i]) else None,
        }
        print(f"{c}: mapped {areas[c]['mapped_ha_secondary']:,.1f} ha -> error-adjusted "
              f"{areas[c]['error_adjusted_ha']['estimate']:,.1f} ha "
              f"[{areas[c]['error_adjusted_ha']['ci95_low']:,.1f}, {areas[c]['error_adjusted_ha']['ci95_high']:,.1f}]")
    loss = areas["loss"]["error_adjusted_ha"]
    bounds = zero_omission_bounds(both, n_strata)
    areas["loss"]["zero_omission_rule_of_three_ha"] = bounds
    areas["loss"]["upper_bound_ha"] = loss["ci95_high"] + sum(bounds.values())
    if areas["loss"]["users_accuracy"]:
        print(f"HEADLINE loss user's accuracy: {areas['loss']['users_accuracy']['estimate']:.3f} "
              f"[{areas['loss']['users_accuracy']['ci95_low']:.3f}, {areas['loss']['users_accuracy']['ci95_high']:.3f}]")
    print(f"loss upper bound incl. rule of three on zero-omission strata: {areas['loss']['upper_bound_ha']:,.1f} ha ({bounds})")

    half_width = (loss["ci95_high"] - loss["ci95_low"]) / 2
    top_up = loss["estimate"] > 0 and half_width > TOP_UP_REL_HALF_WIDTH * loss["estimate"]
    below_min = any(not results["per_date"][d]["cdm"]["vm0007_gate"]["enough_points"] for d in DATES)
    results["change_areas"] = {"n_used": len(both), "excluded_uninterpretable": exclusions(points, lambda p: p["ref_2019"] and p["ref_2023"]), "areas": areas}
    results["top_up_needed"] = {"loss_ci_too_wide": bool(top_up), "class_below_50_points": bool(below_min)}
    results["gate_passed_both_dates"] = all(results["per_date"][d]["cdm"]["vm0007_gate"]["passed"] for d in DATES)

    (OUT_DIR / "aoi_accuracy_results.json").write_text(json.dumps(results, indent=2))
    (OUT_DIR / "aoi_change_areas.json").write_text(json.dumps({
        "note": "error_adjusted_ha is the figure to use; mapped_ha_secondary is the raw pixel count, not an assessed area",
        "period": "2019-2023",
        "areas": {c: {k: a[k] for k in ("error_adjusted_ha", "mapped_ha_secondary", "upper_bound_ha") if k in a} for c, a in areas.items()},
    }, indent=2))
    print(f"gate passed (both dates): {results['gate_passed_both_dates']}, top-up needed: {results['top_up_needed']}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="assess_aoi_accuracy"):
        for d in DATES:
            mlflow.log_metric(f"oa_{d}", results["per_date"][d]["cdm"]["overall_accuracy"]["estimate"])
        mlflow.log_metric("gate_passed", int(results["gate_passed_both_dates"]))
        mlflow.log_metric("loss_error_adjusted_ha", loss["estimate"])
        if areas["loss"]["users_accuracy"]:
            mlflow.log_metric("loss_users_accuracy", areas["loss"]["users_accuracy"]["estimate"])
        mlflow.log_artifact(str(OUT_DIR / "aoi_accuracy_results.json"))
        mlflow.log_artifact(str(OUT_DIR / "aoi_change_areas.json"))


if __name__ == "__main__":
    main()
