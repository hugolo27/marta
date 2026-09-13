"""3x3 S2-patch-per-MapBiomas-pixel alignment (phase1-dataset-build 4.2-4.3). Reprojecting
MapBiomas onto S2's own 30m grid makes each label cell exactly cover a 3x3 block of native 10m
S2 pixels, no separate alignment math needed. QA: spot-checks real bosque/pasto boundary pixels
(via neighborhood-diversity edge mask), not arbitrary points.

This reproject is only valid on a single-UTM-zone region like the AOI used here — it's a
demonstration that the alignment mechanism works, not the method 08_assemble_dataset.py uses for
bulk sampling over the multi-zone footprint (see that script's docstring, code review 2026-09-03).

Usage: .venv/bin/python scripts/06_align_3x3_patches.py"""

import ee

import gee_session
import mapbiomas_legend
import s2_utils

N_SPOT_CHECKS = 5


def main():
    gee_session.init()
    aoi = s2_utils.load_aoi()

    s2 = s2_utils.build_s2_composite(aoi, "2019-06-01", "2019-09-30", add_ndvi=False).clip(aoi)
    s2_projection = s2.select("B4").projection()

    mapbiomas = ee.Image(mapbiomas_legend.MAPBIOMAS_ASSET)
    from_codes, to_codes = mapbiomas_legend.remap_expression("classification_2019")
    label = mapbiomas.select("classification_2019").remap(from_codes, to_codes, defaultValue=0).rename("label")

    label_aligned = label.reproject(s2_projection.atScale(30))  # the alignment step itself

    # bosque (1) cell with a non-bosque neighbor = boundary pixel
    kernel = ee.Kernel.square(1, "pixels")
    neighbor_max = label_aligned.reduceNeighborhood(ee.Reducer.max(), kernel)
    neighbor_min = label_aligned.reduceNeighborhood(ee.Reducer.min(), kernel)
    is_edge = neighbor_max.neq(neighbor_min).And(label_aligned.eq(1)).selfMask()

    # plain .sample() misses sparse masks (~1.5% of the AOI here); stratifiedSample() doesn't
    edge_points = is_edge.stratifiedSample(
        numPoints=N_SPOT_CHECKS,
        classBand="label_max",
        region=aoi,
        scale=30,
        seed=42,
        geometries=True,
    )

    points = edge_points.getInfo()["features"]
    print(f"Found {len(points)} bosque/pasto (or bosque/other) boundary points to spot-check.\n")

    for i, feat in enumerate(points):
        lon, lat = feat["geometry"]["coordinates"]
        pt = ee.Geometry.Point([lon, lat])

        label_val = label_aligned.reduceRegion(ee.Reducer.first(), pt, 30).getInfo()["label"]

        patch = s2.select("B4").neighborhoodToArray(ee.Kernel.square(1, "pixels"))
        arr = patch.reduceRegion(ee.Reducer.first(), pt, 10).getInfo()["B4"]

        print(f"Point {i + 1}: ({lon:.5f}, {lat:.5f})")
        print(f"  MapBiomas label (reprojected to S2 grid, 30m): {mapbiomas_legend.CLASS_NAMES[label_val]}")
        print(f"  3x3 S2 B4 patch:\n    {arr[0]}\n    {arr[1]}\n    {arr[2]}")
        print()

    print("If the 3x3 patches above show real variation between rows/cols near a labeled boundary,")
    print("the alignment is working: each patch reflects genuine 10m spatial detail under one 30m label.")


if __name__ == "__main__":
    main()
