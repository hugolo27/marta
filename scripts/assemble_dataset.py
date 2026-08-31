"""Dataset assembly, phase1-dataset-build 6.1-6.3 (format also in docs/PIPELINE.md). Each
example: 33x33x13 Sentinel-2 window (12 bands + NDVI) centered on one MapBiomas 3x3 label block,
saved as .npy under data/study_area/dataset/<split>/<class>/, with a manifest. Stratified
sampling across the wider footprint (AOI alone has no cultivo), excluding the Filadelfia
held-out sub-region. Extraction runs in batches — a single sampleRegions() call for hundreds of
patches is too large/slow to be reliable.

Usage: .venv/bin/python scripts/assemble_dataset.py"""

import csv
import json
import random
from pathlib import Path

import ee
import numpy as np

import gee_session
import mapbiomas_legend

REPO_ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = REPO_ROOT / "data" / "study_area" / "aoi.geojson"
OUT_DIR = REPO_ROOT / "data" / "study_area" / "dataset"

MAPBIOMAS_ASSET = "projects/mapbiomas-public/assets/chaco/lulc/collection5/mapbiomas_chaco_collection5_integration_v2"
S2_BANDS = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B9", "B11", "B12"]
CLOUD_FREE_SCL = [4, 5, 6, 7, 11]
PERIODS = {"2019": ("2019-06-01", "2019-09-30"), "2023": ("2023-06-01", "2023-09-30")}
PATCH_RADIUS_PX = 16  # -> 33x33
N_PER_CLASS = 200  # real training volume (up from the 90-patch proof-of-mechanism run)
BATCH_SIZE = 25  # points per sampleRegions() call
SPLIT_RATIOS = {"train": 0.7, "val": 0.15, "test": 0.15}

HELDOUT_CENTER = (-60.03, -22.35)
HELDOUT_HALF_WIDTH_DEG = (0.20, 0.18)

CHACO_DEPARTMENTS = ["Alto Paraguay", "Boqueron", "Presidente Hayes"]


def load_aoi():
    geojson = json.loads(AOI_PATH.read_text())
    return ee.Geometry(geojson["features"][0]["geometry"])


def wider_footprint_minus_heldout():
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level1")
    chaco = gaul.filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Paraguay"),
            ee.Filter.inList("ADM1_NAME", CHACO_DEPARTMENTS),
        )
    )
    footprint = chaco.geometry().dissolve()
    lon, lat = HELDOUT_CENTER
    dlon, dlat = HELDOUT_HALF_WIDTH_DEG
    heldout = ee.Geometry.Rectangle([lon - dlon, lat - dlat, lon + dlon, lat + dlat])
    return footprint.difference(heldout, ee.ErrorMargin(1))


def mask_clouds(image):
    scl = image.select("SCL")
    clear = scl.remap(CLOUD_FREE_SCL, [1] * len(CLOUD_FREE_SCL), 0)
    return image.updateMask(clear)


def build_s2_with_ndvi(sampling_area, start, end):
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(sampling_area)
        .filterDate(start, end)
        .map(mask_clouds)
    )
    composite = collection.select(S2_BANDS).median().clip(sampling_area)
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
    return composite.addBands(ndvi)


def assign_split():
    r = random.random()
    if r < SPLIT_RATIOS["train"]:
        return "train"
    if r < SPLIT_RATIOS["train"] + SPLIT_RATIOS["val"]:
        return "val"
    return "test"


def main():
    random.seed(42)
    gee_session.init()
    sampling_area = wider_footprint_minus_heldout()

    manifest_rows = []
    counters = {"train": 0, "val": 0, "test": 0}

    for period, (start, end) in PERIODS.items():
        s2 = build_s2_with_ndvi(sampling_area, start, end)
        channels = S2_BANDS + ["NDVI"]

        mapbiomas = ee.Image(MAPBIOMAS_ASSET)
        from_codes, to_codes = mapbiomas_legend.remap_expression(f"classification_{period}")
        label = (
            mapbiomas.select(f"classification_{period}")
            .remap(from_codes, to_codes, defaultValue=0)
            .rename("label")
        )
        s2_projection = s2.select("B4").projection()
        label_aligned = label.reproject(s2_projection.atScale(30))

        target_classes = label_aligned.eq(1).Or(label_aligned.eq(2)).Or(label_aligned.eq(3)).selfMask()
        points = label_aligned.updateMask(target_classes).stratifiedSample(
            numPoints=N_PER_CLASS,
            classBand="label",
            region=sampling_area,
            scale=30,
            seed=42,
            geometries=True,
        )

        patch_image = s2.select(channels).neighborhoodToArray(ee.Kernel.square(PATCH_RADIUS_PX, "pixels"))

        point_list = points.toList(points.size())
        n_points = point_list.size().getInfo()
        print(f"{period}: {n_points} sample points across 3 classes, extracting in batches of {BATCH_SIZE}")

        extracted = 0
        for start_idx in range(0, n_points, BATCH_SIZE):
            batch = ee.FeatureCollection(point_list.slice(start_idx, start_idx + BATCH_SIZE))
            sampled = patch_image.sampleRegions(collection=batch, scale=10, geometries=True)
            features = sampled.getInfo()["features"]
            extracted += len(features)

            for feat in features:
                props = feat["properties"]
                class_id = int(props["label"])
                class_name = mapbiomas_legend.CLASS_NAMES[class_id]
                arrays = [np.array(props[ch]) for ch in channels]
                patch = np.stack(arrays, axis=-1)  # (33, 33, 13)

                split = assign_split()
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

    print(f"\nTotal patches: {len(manifest_rows)}")
    print(f"Split counts: {counters}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
