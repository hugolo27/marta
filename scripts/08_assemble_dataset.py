"""Dataset assembly, phase1-dataset-build 6.1-6.3 (format also in docs/METODOLOGIA_PIPELINE.md). Each
example: 33x33x13 Sentinel-2 window (12 bands + NDVI) centered on one MapBiomas 3x3 label block,
saved as .npy under data/study_area/dataset/<split>/<class>/, with a manifest. Stratified
sampling across the wider footprint (AOI alone has no cultivo), excluding 3 held-out sub-regions
(Filadelfia, Bahia Negra, Pozo Colorado — see HELDOUT_REGIONS, added 2026-09-11 for a broader
generalization check, phase1-classifier task 4.4). Extraction runs in batches — a single
sampleRegions() call for hundreds of patches is too large/slow to be reliable.

Splits are assigned by spatial block, not per point (fixed 2026-09-03: a leakage check found
train/test patches from the same real-world scene, since 33x33 patches are 330m across and
per-point random assignment can land two points from the same field on opposite sides of a
split). Blocking is done per class, since a spatially clustered rare class (cultivo) could
otherwise get starved out of a split entirely by a single global blocking. class_id/split are
attached as feature properties before extraction and carried through by sampleRegions(), not
re-derived afterward by matching coordinates from a second independent GEE call.

Split assignment and the buffer check run once over BOTH periods' points combined, not per
period (fixed 2026-09-11: `assign_splits_by_spatial_block`/`enforce_spatial_buffer` used to run
separately inside the per-period loop, so a 2019 point and a 2023 point could sit meters apart —
sometimes the exact same coordinates, since the two years' stratified samples aren't independent
of each other where land cover didn't change — and land in different splits with nothing ever
comparing across periods to catch it. Found via an independent check while building a demo
notebook: 187 cross-split pairs under 330m in the manifest this bug produced, several at 0m.)

Samples directly against MapBiomas' own native resolution/projection, not reprojected onto
Sentinel-2's grid (code review 2026-09-03: the 3-department sampling footprint spans two UTM
zones, so forcing it onto one arbitrary scene's zone would distort points outside it — see
s2_utils.build_s2_composite's reproject param). The exact 3x3 pixel-block alignment is
demonstrated on the single-UTM-zone AOI in 06_align_3x3_patches.py instead; patch extraction here
still pulls genuine local 10m Sentinel-2 pixels via sampleRegions(scale=10), which resolves
scale explicitly regardless of the composite's own declared projection metadata.

Usage: .venv/bin/python scripts/08_assemble_dataset.py"""

import csv
import random
from pathlib import Path

import ee
import numpy as np

import gee_session
import mapbiomas_legend
import s2_utils

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "study_area" / "dataset"

PERIODS = {"2019": ("2019-06-01", "2019-09-30"), "2023": ("2023-06-01", "2023-09-30")}
PATCH_RADIUS_PX = 16  # -> 33x33
N_PER_CLASS = 400  # scaled up from 200 (2026-09-11): the RF-vs-CNN comparison flipped conclusions
# 3 times across 6 code-review rounds at n=200/class, itself evidence the comparison was
# underpowered relative to the effect size at stake
BATCH_SIZE = 25  # points per sampleRegions() call
SPLIT_RATIOS = {"train": 0.7, "val": 0.15, "test": 0.15}
GRID_SIZE_DEG = 0.02  # ~2km at this latitude, >6x the 330m patch side, buffers train/test separation
PATCH_SIDE_M = 330  # 33px * 10m, the patch-overlap distance the buffer check enforces

# 3 held-out sub-regions, one per landscape topology, so a generalization check (phase1-classifier
# task 4.4) can tell a landscape-specific failure apart from a general one — not just Filadelfia's
# agricultural-colony landscape, but a forest-dominated area (Bahia Negra) and a pasture/ranching
# one (Pozo Colorado) too. Town-center approximations, not surveyed boundaries, same convention as
# the original Filadelfia box. Verified 2026-09-11: none of the 3 overlap each other or the
# case-study AOI (0 ha each, checked via ee intersection().area()).
HELDOUT_REGIONS = {
    "filadelfia": {"center": (-60.03, -22.35), "half_width_deg": (0.20, 0.18)},  # Boqueron, agricultural colonies
    "bahia_negra": {"center": (-58.18, -20.23), "half_width_deg": (0.20, 0.18)},  # Alto Paraguay, remote/forest
    "pozo_colorado": {"center": (-58.80, -23.49), "half_width_deg": (0.20, 0.18)},  # Presidente Hayes, cattle ranching
}

CHACO_DEPARTMENTS = ["Alto Paraguay", "Boqueron", "Presidente Hayes"]


def heldout_rectangle(name):
    lon, lat = HELDOUT_REGIONS[name]["center"]
    dlon, dlat = HELDOUT_REGIONS[name]["half_width_deg"]
    return ee.Geometry.Rectangle([lon - dlon, lat - dlat, lon + dlon, lat + dlat])


def wider_footprint_minus_heldout():
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level1")
    chaco = gaul.filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Paraguay"),
            ee.Filter.inList("ADM1_NAME", CHACO_DEPARTMENTS),
        )
    )
    footprint = chaco.geometry().dissolve()
    for name in HELDOUT_REGIONS:
        footprint = footprint.difference(heldout_rectangle(name), ee.ErrorMargin(1))
    return footprint


def block_key(lon, lat, grid_size=GRID_SIZE_DEG):
    return (round(lon / grid_size), round(lat / grid_size))


def haversine_m(lon1, lat1, lon2, lat2):
    r = 6371000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dlmb = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def assign_splits_by_spatial_block(points_info, seed=42):
    """Groups points into ~2km blocks per class and assigns whole blocks to one split, so no
    train/test pair can share a near-duplicate patch. Returns {(lon, lat): split}.

    Guarantees at least 1 block per split when there are >= 3 blocks for a class (naive
    round() could allocate every block to train, silently leaving val/test with 0 examples of
    that class — found via code review 2026-09-04); warns instead of silently degrading when
    there are too few blocks to guarantee it.

    A location can carry a different class_id per period (a real land-cover transition, not a
    bug) — grouping by one canonical class per coordinate first means each location goes
    through exactly one block/split decision, instead of one computed independently per class
    occurrence that could silently overwrite another's in the shared split_lookup below (code
    review 2026-09-13: audited the manifest, found 64 locations affected — the later period's
    class wins as canonical, an explicit and deterministic choice, not an arbitrary one)."""
    canonical = {(round(p["lon"], 6), round(p["lat"], 6)): p for p in points_info}

    by_class = {}
    for p in canonical.values():
        by_class.setdefault(p["class_id"], []).append(p)

    split_lookup = {}
    for class_id, pts in by_class.items():
        blocks = {}
        for p in pts:
            blocks.setdefault(block_key(p["lon"], p["lat"]), []).append(p)
        block_keys = list(blocks.keys())
        rng = random.Random(seed + class_id)
        rng.shuffle(block_keys)

        n = len(block_keys)
        if n < 3:
            print(f"  WARNING: class {class_id} has only {n} spatial block(s) — "
                  f"cannot guarantee all 3 splits contain this class")
            n_val = n_test = 0
        else:
            n_val = max(1, round(n * SPLIT_RATIOS["val"]))
            n_test = max(1, round(n * SPLIT_RATIOS["test"]))
        n_train = n - n_val - n_test

        for i, key in enumerate(block_keys):
            split = "train" if i < n_train else ("val" if i < n_train + n_val else "test")
            for p in blocks[key]:
                split_lookup[(round(p["lon"], 6), round(p["lat"], 6))] = split
    return split_lookup


def enforce_spatial_buffer(points_info, split_lookup, threshold_m=PATCH_SIDE_M):
    """Drops any point whose nearest opposite-split neighbor is closer than threshold_m. The
    per-class block grid doesn't by itself guarantee separation right at a block boundary —
    two points a few meters apart can round into different blocks (found via code review
    2026-09-04) — this closes that gap for real regardless of where points happen to fall,
    rather than relying on empirically checking one generated point set after the fact."""
    n = len(points_info)
    splits = [split_lookup[(round(p["lon"], 6), round(p["lat"], 6))] for p in points_info]
    to_drop = set()
    for i in range(n):
        for j in range(i + 1, n):
            if splits[i] == splits[j] or (i in to_drop and j in to_drop):
                continue
            d = haversine_m(points_info[i]["lon"], points_info[i]["lat"], points_info[j]["lon"], points_info[j]["lat"])
            if d < threshold_m:
                to_drop.add(i)
                to_drop.add(j)
    if to_drop:
        print(f"  buffer check: dropping {len(to_drop)} points within {threshold_m}m of an opposite-split point")
    return [p for idx, p in enumerate(points_info) if idx not in to_drop]


def sample_period_points(sampling_area, period):
    """Light client-side pull (coordinates + class only, no patch data) for one period, so
    splits can be assigned across all periods together before any heavy extraction runs."""
    mapbiomas = ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET)
    from_codes, to_codes = mapbiomas_legend.remap_expression(f"classification_{period}")
    label = (
        mapbiomas.select(f"classification_{period}")
        .remap(from_codes, to_codes, defaultValue=0)
        .rename("label")
    )
    target_classes = label.eq(1).Or(label.eq(2)).Or(label.eq(3)).selfMask()
    points = label.updateMask(target_classes).stratifiedSample(
        numPoints=N_PER_CLASS,
        classBand="label",
        region=sampling_area,
        scale=30,
        seed=42,
        geometries=True,
    )
    light_info = points.getInfo()["features"]
    return [
        {"lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
         "class_id": int(f["properties"]["label"]), "period": period}
        for f in light_info
    ]


def main():
    gee_session.init()
    sampling_area = wider_footprint_minus_heldout()

    # Split assignment and the buffer check need every period's points in hand at once —
    # otherwise a 2019 point and a 2023 point near (or at) the same location can land in
    # different splits with nothing ever comparing across periods to catch it (module
    # docstring, fixed 2026-09-11).
    all_points = []
    for period in PERIODS:
        all_points.extend(sample_period_points(sampling_area, period))
    split_lookup = assign_splits_by_spatial_block(all_points, seed=42)
    all_points = enforce_spatial_buffer(all_points, split_lookup)

    points_by_period = {period: [] for period in PERIODS}
    for p in all_points:
        points_by_period[p["period"]].append(p)

    manifest_rows = []
    counters = {"train": 0, "val": 0, "test": 0}
    skipped_gap = 0

    for period, (start, end) in PERIODS.items():
        points_info = points_by_period[period]
        if not points_info:
            continue

        # reproject=False: this footprint spans multiple UTM zones, see module docstring.
        # clip=True: sampling_area has the Filadelfia held-out rectangle carved out as a hole —
        # without clipping, a point's 330m extraction window near that hole's boundary could pull
        # real pixels from inside the excluded region (code review 2026-09-11).
        s2 = s2_utils.build_s2_composite(sampling_area, start, end, add_ndvi=True, reproject=False, clip=True)
        channels = s2_utils.S2_BANDS + ["NDVI"]

        points_with_split = ee.FeatureCollection([
            ee.Feature(
                ee.Geometry.Point([p["lon"], p["lat"]]),
                {"class_id": p["class_id"], "split": split_lookup[(round(p["lon"], 6), round(p["lat"], 6))]},
            )
            for p in points_info
        ])

        patch_image = s2.select(channels).neighborhoodToArray(ee.Kernel.square(PATCH_RADIUS_PX, "pixels"))

        point_list = points_with_split.toList(points_with_split.size())
        n_points = len(points_info)
        print(f"{period}: {n_points} sample points across 3 classes, extracting in batches of {BATCH_SIZE}")

        extracted = 0
        for start_idx in range(0, n_points, BATCH_SIZE):
            batch = ee.FeatureCollection(point_list.slice(start_idx, start_idx + BATCH_SIZE))
            sampled = patch_image.sampleRegions(
                collection=batch, scale=10, geometries=True, properties=["class_id", "split"]
            )
            features = sampled.getInfo()["features"]
            extracted += len(features)

            for feat in features:
                props = feat["properties"]
                class_id = props["class_id"]
                split = props["split"]
                class_name = mapbiomas_legend.CLASS_NAMES[class_id]
                arrays = [np.array(props[ch]) for ch in channels]
                patch = np.stack(arrays, axis=-1)  # (33, 33, 13)

                # A real Sentinel-2 pixel is never exactly 0 across all 13 channels at once;
                # that pattern only comes from a masked/cloud-gap pixel. Skip rather than train
                # on fabricated data (code review 2026-09-03).
                if np.any(np.all(patch == 0, axis=-1)):
                    skipped_gap += 1
                    continue

                counters[split] += 1
                idx = counters[split]

                out_class_dir = OUT_DIR / split / class_name
                out_class_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_class_dir / f"{period}_{idx:04d}.npy"
                np.save(out_path, patch)

                lon, lat = feat["geometry"]["coordinates"]
                manifest_rows.append({
                    "path": str(out_path.relative_to(REPO_ROOT)),
                    "period": period, "class": class_name, "split": split,
                    "lon": lon, "lat": lat, "shape": str(patch.shape),
                })
            print(f"  batch {start_idx // BATCH_SIZE + 1}: {extracted}/{n_points} patches extracted")

    manifest_path = OUT_DIR / "manifest.csv"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "period", "class", "split", "lon", "lat", "shape"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"\nTotal patches: {len(manifest_rows)} ({skipped_gap} skipped for containing masked/gap pixels)")
    print(f"Split counts: {counters}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
