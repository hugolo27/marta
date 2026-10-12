"""Picks the change-development area for phase1-change-detection-hardening (task 1.2): the box of
roughly AOI size with the most Hansen forest loss 2020-2023 inside the sampling footprint. The AOI
is a protected REDD+ area with ~0 real loss in that period (Hansen: 0.1 ha), so scoring change-map
post-processing on the AOI alone can only ever reward removing change -- this box is where a
configuration has to show it still keeps real clearing.
Criterion fixed in data/study_area/change_hardening/README.md before scoring: 0.13 deg boxes east
of -60 deg (UTM 21S, same zone as the AOI, so 18_classify_aoi_temporal.py's tiling applies
unchanged), fully inside the footprint, not touching the AOI or any held-out region.
Usage: .venv/bin/python scripts/25_select_change_dev_area.py"""

import importlib
import json
from pathlib import Path

import ee
import numpy as np

import gee_session
import s2_utils

assemble = importlib.import_module("08_assemble_dataset")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "data" / "study_area" / "change_hardening" / "dev_area.geojson"

HANSEN_ASSET = "UMD/hansen/global_forest_change_2025_v1_13"
BOX_DEG = 0.13
MIN_LON = -60.0
LOSS_YEARS = (20, 23)
TREECOVER_MIN = 25


def hansen_loss_ha():
    h = ee.Image(HANSEN_ASSET)
    loss = (h.select("lossyear").gte(LOSS_YEARS[0])
            .And(h.select("lossyear").lte(LOSS_YEARS[1]))
            .And(h.select("treecover2000").gte(TREECOVER_MIN)))
    return ee.Image.pixelArea().divide(10_000).updateMask(loss).rename("loss_ha")


def candidate_boxes(footprint):
    minx, miny, maxx, maxy = np.array(footprint.bounds(1).coordinates().getInfo()[0]).T[[0, 1, 0, 1]].tolist()
    minx, maxx = max(min(minx), MIN_LON), max(maxx)
    miny, maxy = min(miny), max(maxy)
    excluded = [s2_utils.load_aoi()] + [assemble.heldout_rectangle(n) for n in assemble.HELDOUT_REGIONS]

    feats = []
    for lon in np.arange(minx, maxx - BOX_DEG, BOX_DEG):
        for lat in np.arange(miny, maxy - BOX_DEG, BOX_DEG):
            rect = ee.Geometry.Rectangle([float(lon), float(lat), float(lon + BOX_DEG), float(lat + BOX_DEG)])
            feats.append(ee.Feature(rect, {"lon0": float(lon), "lat0": float(lat)}))
    boxes = ee.FeatureCollection(feats)

    def flag(f):
        g = f.geometry()
        touches = ee.List([g.intersects(e, ee.ErrorMargin(1)) for e in excluded]).contains(True)
        return f.set({"inside": footprint.contains(g, ee.ErrorMargin(1)), "touches_excluded": touches})

    return boxes.map(flag).filter(ee.Filter.eq("inside", True)).filter(ee.Filter.eq("touches_excluded", False))


def main():
    gee_session.init()
    footprint = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "Paraguay"),
            ee.Filter.inList("ADM1_NAME", assemble.CHACO_DEPARTMENTS),
        )
    ).geometry().dissolve()

    boxes = candidate_boxes(footprint)
    scored = hansen_loss_ha().reduceRegions(collection=boxes, reducer=ee.Reducer.sum(), scale=30, tileScale=4)
    rows = scored.select(["lon0", "lat0", "sum"], retainGeometry=False).getInfo()["features"]
    rows = sorted(((r["properties"].get("sum") or 0.0, r["properties"]["lon0"], r["properties"]["lat0"]) for r in rows), reverse=True)
    print(f"{len(rows)} candidate boxes scored")
    for loss, lon0, lat0 in rows[:5]:
        print(f"  lon0={lon0:.3f} lat0={lat0:.3f}: {loss:,.1f} ha Hansen loss 2020-2023")

    loss, lon0, lat0 = rows[0]
    rect = ee.Geometry.Rectangle([lon0, lat0, lon0 + BOX_DEG, lat0 + BOX_DEG])
    area_ha = rect.area(1).divide(10_000).getInfo()
    OUT_PATH.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "name": "change_dev_area", "hansen_loss_2020_2023_ha": round(loss, 1),
                "area_ha": round(area_ha, 1), "candidates_scored": len(rows), "hansen_asset": HANSEN_ASSET,
            },
            "geometry": rect.getInfo(),
        }],
    }, indent=2))
    print(f"selected: lon0={lon0:.3f} lat0={lat0:.3f}, {area_ha:,.0f} ha, {loss:,.1f} ha loss")
    print(f"saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
