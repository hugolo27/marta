"""Spatial autocorrelation of the labels and the imagery, phase1-dataset-v2 (task 1.1). Sets the side
of the train/val/test blocks from a measurement instead of a chosen distance (design D1): blocks
should be at least as large as the range over which nearby points still resemble each other
(Roberts et al., 2017; Valavi et al., 2019).

Two steps:
  pull -- per year, 30 random windows of 20 km over the sampling area (held-out regions carved
          out), 300 points per window at 30 m, with the MapBiomas class and the dry-season NDVI
  fit  -- per year and variable, the empirical semivariogram over within-window pairs (NDVI: half
          the mean squared difference; class: half the share of pairs with different classes), an
          exponential fit, and its practical range (distance at 95% of the sill). Block side = the
          largest of the four ranges, rounded up to the next whole km, capped at half the window
          (10 km), beyond which the windows can't measure

Usage: .venv/bin/python scripts/33_spatial_autocorrelation.py pull|fit"""

import importlib
import json
import math
import sys
from pathlib import Path

import mlflow
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area" / "spatial_autocorrelation"
POINTS_PATH = OUT_DIR / "points.json"
RESULTS_PATH = OUT_DIR / "results.json"
EXPERIMENT_NAME = "phase1-spatial-autocorrelation"

WINDOW_HALF_M = 10000
WINDOWS_PER_YEAR = 30
POINTS_PER_WINDOW = 300
WINDOW_SEEDS = {"2019": 7, "2023": 8}
BIN_EDGES_M = [0, 60, 120, 200, 300, 450, 650, 900, 1200, 1600, 2000, 2500, 3000, 4000, 5000, 6500, 8000,
               10000, 12000, 14000, 17000, 20000]
MIN_PAIRS_PER_BIN = 30


def pull():
    import ee

    import gee_session
    import mapbiomas_legend
    import s2_utils

    assemble = importlib.import_module("08_assemble_dataset")
    gee_session.init()
    area = assemble.wider_footprint_minus_heldout()
    out = []
    for period, (start, end) in assemble.PERIODS.items():
        from_codes, to_codes = mapbiomas_legend.remap_expression(f"classification_{period}")
        label = (ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET).select(f"classification_{period}")
                 .remap(from_codes, to_codes, defaultValue=0).rename("label"))
        centers = ee.FeatureCollection.randomPoints(area, WINDOWS_PER_YEAR, seed=WINDOW_SEEDS[period]).getInfo()["features"]
        for k, c in enumerate(centers):
            lon, lat = c["geometry"]["coordinates"]
            window = ee.Geometry.Point([lon, lat]).buffer(WINDOW_HALF_M).bounds()
            s2 = s2_utils.build_s2_composite(window, start, end, add_ndvi=True, reproject=False)
            sampled = label.addBands(s2.select("NDVI")).sample(
                region=window, scale=30, numPixels=POINTS_PER_WINDOW, seed=k, geometries=True).getInfo()["features"]
            for f in sampled:
                out.append({"period": period, "win": k, "lon": f["geometry"]["coordinates"][0],
                            "lat": f["geometry"]["coordinates"][1], "label": f["properties"].get("label"),
                            "ndvi": f["properties"].get("NDVI")})
            print(period, k, len(sampled), flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    POINTS_PATH.write_text(json.dumps(out))
    print(f"saved {len(out)} points: {POINTS_PATH}")


def haversine_m(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * np.arcsin(np.sqrt(a))


def exponential(h, nugget, partial_sill, practical_range):
    return nugget + partial_sill * (1 - np.exp(-3 * h / practical_range))


def semivariogram(points):
    dist, differ, sq = [], [], []
    for w in sorted({p["win"] for p in points}):
        q = [p for p in points if p["win"] == w]
        lon, lat = np.array([p["lon"] for p in q]), np.array([p["lat"] for p in q])
        label, ndvi = np.array([p["label"] for p in q]), np.array([p["ndvi"] for p in q])
        i, j = np.triu_indices(len(q), 1)
        dist.append(haversine_m(lon[i], lat[i], lon[j], lat[j]))
        differ.append(label[i] != label[j])
        sq.append((ndvi[i] - ndvi[j]) ** 2)
    dist, differ, sq = map(np.concatenate, (dist, differ, sq))
    rows = []
    for lo, hi in zip(BIN_EDGES_M[:-1], BIN_EDGES_M[1:]):
        m = (dist >= lo) & (dist < hi)
        if m.sum() >= MIN_PAIRS_PER_BIN:
            rows.append({"lag_m": float(dist[m].mean()), "pairs": int(m.sum()),
                         "class": float(0.5 * differ[m].mean()), "ndvi": float(0.5 * sq[m].mean())})
    return rows


def fit_range(rows, variable, sill):
    from scipy.optimize import curve_fit

    lags = np.array([r["lag_m"] for r in rows])
    gamma = np.array([r[variable] for r in rows])
    (nugget, partial_sill, practical_range), _ = curve_fit(
        exponential, lags, gamma, p0=[gamma[0], sill - gamma[0], 2000],
        bounds=([0, 0, 50], [2 * sill, 2 * sill, 100000]))
    return {"nugget": float(nugget), "partial_sill": float(partial_sill), "practical_range_m": float(practical_range)}


def plot(results):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, variable in zip(axes, ("ndvi", "class")):
        for period, color in (("2019", "#2a78d6"), ("2023", "#d95926")):
            r = results[period]
            lags = np.array([b["lag_m"] for b in r["bins"]])
            ax.scatter(lags / 1000, [b[variable] for b in r["bins"]], color=color, s=14, label=period)
            f = r["fits"][variable]
            h = np.linspace(0, lags.max(), 200)
            ax.plot(h / 1000, exponential(h, f["nugget"], f["partial_sill"], f["practical_range_m"]), color=color)
            ax.axvline(f["practical_range_m"] / 1000, color=color, ls=":", lw=1)
        ax.axvline(2, color="grey", ls="--", lw=1)
        ax.set_title("NDVI" if variable == "ndvi" else "MapBiomas class")
        ax.set_xlabel("distance (km)")
        ax.set_ylabel("semivariance")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend()
    fig.suptitle("Dotted: practical range per year. Dashed: the previous 2 km blocks.", fontsize=9)
    fig.tight_layout()
    path = OUT_DIR / "semivariograms.png"
    fig.savefig(path, dpi=150)
    return path


def fit():
    points = [p for p in json.loads(POINTS_PATH.read_text()) if p["label"] is not None and p["ndvi"] is not None]
    results = {}
    for period in sorted({p["period"] for p in points}):
        pts = [p for p in points if p["period"] == period]
        labels = np.array([p["label"] for p in pts])
        sills = {"ndvi": float(np.var([p["ndvi"] for p in pts])),
                 "class": float(0.5 * (1 - sum(np.mean(labels == c) ** 2 for c in np.unique(labels))))}
        bins = semivariogram(pts)
        fits = {v: fit_range(bins, v, sills[v]) for v in ("ndvi", "class")}
        results[period] = {"points": len(pts), "sills": sills, "bins": bins, "fits": fits}
        for v, f in fits.items():
            print(f"{period} {v}: practical range {f['practical_range_m']:.0f} m (nugget {f['nugget']:.4f}, partial sill {f['partial_sill']:.4f})")

    ranges = [results[p]["fits"][v]["practical_range_m"] for p in results for v in ("ndvi", "class")]
    capped = max(ranges) > WINDOW_HALF_M
    block_km = WINDOW_HALF_M // 1000 if capped else math.ceil(max(ranges) / 1000)
    results["block_side_km"] = block_km
    results["capped_at_half_window"] = capped
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    plot_path = plot(results)
    print(f"max practical range {max(ranges):.0f} m -> block side {block_km} km" + (" (capped at half the window)" if capped else ""))

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="semivariogram_20km_windows"):
        mlflow.log_params({"window_half_m": WINDOW_HALF_M, "windows_per_year": WINDOWS_PER_YEAR,
                           "points_per_window": POINTS_PER_WINDOW, "block_side_km": block_km, "capped": capped})
        for period in ("2019", "2023"):
            for v in ("ndvi", "class"):
                mlflow.log_metric(f"range_m_{v}_{period}", results[period]["fits"][v]["practical_range_m"])
        mlflow.log_artifact(str(RESULTS_PATH))
        mlflow.log_artifact(str(plot_path))


if __name__ == "__main__":
    {"pull": pull, "fit": fit}[sys.argv[1]]()
