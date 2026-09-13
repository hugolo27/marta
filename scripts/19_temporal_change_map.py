"""Diffs the 2019/2023 dense classification rasters (18_classify_aoi_temporal.py) into a
per-pixel change map and transition statistics (phase1-temporal-comparison tasks 3.1-3.3).
Named transitions, not a binary changed/unchanged flag, since Fase 2's carbon estimation needs
to know which transition happened (bosque->cultivo and bosque->pasto carry different carbon-
density deltas, design.md). A pixel unclassified in either date is excluded, not imputed --
same norm as phase1-classifier's masked-pixel handling.
Usage: .venv/bin/python scripts/19_temporal_change_map.py"""

import json
from pathlib import Path

import ee
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pyproj
from matplotlib.colors import ListedColormap

import gee_session
import s2_utils
from dataset_loader import CLASS_NAMES

EXPERIMENT_NAME = "phase1-temporal-comparison"

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "study_area"

UNCLASSIFIED = -1
NO_CHANGE = 0
TRANSITIONS = [(a, b) for a in range(len(CLASS_NAMES)) for b in range(len(CLASS_NAMES)) if a != b]
TRANSITION_CODE = {pair: i + 1 for i, pair in enumerate(TRANSITIONS)}
TRANSITION_NAMES = {code: f"{CLASS_NAMES[a]}_a_{CLASS_NAMES[b]}" for (a, b), code in TRANSITION_CODE.items()}

KNOWN_AOI_AREA_HA = 20_589  # 01_verify_gee_setup.py's GEE-measured polygon area

PALETTE = {
    UNCLASSIFIED: "#9ca3af",
    NO_CHANGE: "#e5e5e5",
    TRANSITION_CODE[(0, 1)]: "#f5a623",  # bosque -> pasto
    TRANSITION_CODE[(0, 2)]: "#d0342c",  # bosque -> cultivo
    TRANSITION_CODE[(1, 0)]: "#1f8d49",  # pasto -> bosque
    TRANSITION_CODE[(1, 2)]: "#8e44ad",  # pasto -> cultivo
    TRANSITION_CODE[(2, 0)]: "#0d9488",  # cultivo -> bosque
    TRANSITION_CODE[(2, 1)]: "#2563eb",  # cultivo -> pasto
}

VISUAL_CHECK_N = 2
VISUAL_CHECK_HALF_SIDE_M = 300


def build_change_map(before, after):
    change = np.full(before.shape, UNCLASSIFIED, dtype=np.int64)
    valid = (before != UNCLASSIFIED) & (after != UNCLASSIFIED)
    change[valid & (before == after)] = NO_CHANGE
    for (a, b), code in TRANSITION_CODE.items():
        change[valid & (before == a) & (after == b)] = code
    return change


def hectares(n_pixels, pixel_m):
    return n_pixels * (pixel_m ** 2) / 10_000


def report_stats(change, pixel_m):
    codes, counts = np.unique(change, return_counts=True)
    stats = {}
    for code, count in zip(codes.tolist(), counts.tolist()):
        name = "unclassified" if code == UNCLASSIFIED else "no_change" if code == NO_CHANGE else TRANSITION_NAMES[code]
        stats[name] = {"pixels": count, "ha": round(hectares(count, pixel_m), 1)}

    grid_total_ha = hectares(change.size, pixel_m)
    stats_total_ha = sum(v["ha"] for v in stats.values())
    print(f"Grid total: {grid_total_ha:,.1f} ha ({change.size:,} px)")
    print(f"Sum of all categories: {stats_total_ha:,.1f} ha (must match grid total)")
    assert abs(stats_total_ha - grid_total_ha) < 0.1, "pixel accounting mismatch"

    classified_ha = grid_total_ha - stats.get("unclassified", {"ha": 0.0})["ha"]
    relative_diff = abs(classified_ha - KNOWN_AOI_AREA_HA) / KNOWN_AOI_AREA_HA
    print(f"Classified area: {classified_ha:,.1f} ha vs. AOI's known polygon area "
          f"{KNOWN_AOI_AREA_HA:,} ha ({relative_diff:.1%} relative diff)")

    print("\nTransition breakdown:")
    for name, v in sorted(stats.items(), key=lambda kv: -kv[1]["ha"]):
        print(f"  {name}: {v['ha']:,.1f} ha ({v['pixels']:,} px)")
    return stats


def plot_change_map(change, out_path):
    codes = sorted(PALETTE)
    cmap = ListedColormap([PALETTE[c] for c in codes])
    index = np.searchsorted(codes, change)

    fig, ax = plt.subplots(figsize=(6, 12))
    ax.imshow(index, cmap=cmap, vmin=0, vmax=len(codes) - 1, interpolation="nearest")
    ax.axis("off")
    ax.set_title("Cambio de cobertura 2019 -> 2023, AOI Corazón Verde del Chaco")
    labels = {UNCLASSIFIED: "sin clasificar", NO_CHANGE: "sin cambio", **TRANSITION_NAMES}
    handles = [plt.Rectangle((0, 0), 1, 1, color=PALETTE[c]) for c in codes]
    fig.legend(handles, [labels[c] for c in codes], loc="lower center", ncol=2, frameon=False, fontsize=8)
    fig.tight_layout(rect=[0, 0.12, 1, 1])
    fig.savefig(out_path, dpi=150)
    print(f"saved: {out_path}")


def pixel_to_wgs84(row, col, meta):
    minx, _, _, maxy = meta["aoi_utm_bounds"]
    x, y = minx + col * meta["pixel_m"], maxy - row * meta["pixel_m"]
    to_wgs84 = pyproj.Transformer.from_crs(meta["utm_crs"], "EPSG:4326", always_xy=True).transform
    return to_wgs84(x, y)


def visual_check(change, meta):
    """Hand-picks a few pixels of whichever real transition has the most area (the AOI's most
    obvious detected change) and pulls true-color thumbnails for both dates around each, so it
    can be checked against a real image instead of trusting the diff (task 3.3) -- same spirit
    as 13_visualize_classification_map.py's side-by-side render."""
    codes, counts = np.unique(change, return_counts=True)
    transition_counts = {c: n for c, n in zip(codes, counts) if c in TRANSITION_NAMES}
    if not transition_counts:
        print("no transitions detected, skipping visual check")
        return
    target = max(transition_counts, key=transition_counts.get)
    print(f"\nvisual check target: {TRANSITION_NAMES[target]} ({transition_counts[target]:,} px, largest transition)")

    rows, cols = np.where(change == target)
    picks = np.linspace(0, len(rows) - 1, min(VISUAL_CHECK_N, len(rows)), dtype=int)

    for i, idx in enumerate(picks):
        row, col = int(rows[idx]), int(cols[idx])
        lon, lat = pixel_to_wgs84(row, col, meta)
        region = ee.Geometry.Point([lon, lat]).buffer(VISUAL_CHECK_HALF_SIDE_M).bounds()
        print(f"\nvisual check {i}: pixel (row={row}, col={col}) -> lon={lon:.5f}, lat={lat:.5f}")
        for period, (start, end) in {"2019": ("2019-06-01", "2019-09-30"), "2023": ("2023-06-01", "2023-09-30")}.items():
            composite = s2_utils.build_s2_composite(region, start, end, add_ndvi=False)
            thumb_url = composite.getThumbUrl({
                "bands": ["B4", "B3", "B2"], "min": 0, "max": 3000,
                "region": region, "dimensions": 300, "format": "png",
            })
            out_path = DATA_DIR / f"visual_check_{i}_{period}.png"
            import urllib.request
            urllib.request.urlretrieve(thumb_url, out_path)
            print(f"  {period}: {out_path}")


def main():
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="change_map_2019_2023"):
        gee_session.init()
        meta = json.loads((DATA_DIR / "aoi_classified_grid_meta.json").read_text())
        before = np.load(DATA_DIR / "aoi_classified_2019.npy")
        after = np.load(DATA_DIR / "aoi_classified_2023.npy")

        change = build_change_map(before, after)
        stats = report_stats(change, meta["pixel_m"])
        mlflow.log_metrics({f"ha_{name}": v["ha"] for name, v in stats.items()})

        np.save(DATA_DIR / "change_map_2019_2023.npy", change)
        stats_path = DATA_DIR / "change_stats_2019_2023.json"
        stats_path.write_text(json.dumps(stats, indent=2))
        print(f"saved: {DATA_DIR / 'change_map_2019_2023.npy'}")
        print(f"saved: {stats_path}")
        mlflow.log_artifact(str(stats_path))

        plot_change_map(change, DATA_DIR / "change_map_2019_2023.png")
        mlflow.log_artifact(str(DATA_DIR / "change_map_2019_2023.png"))
        visual_check(change, meta)


if __name__ == "__main__":
    main()
