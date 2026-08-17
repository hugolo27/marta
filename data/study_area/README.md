# Study area

Satisfies the `study-area` capability spec at `openspec/changes/phase1-define-study-area/specs/study-area/spec.md`.

## Source and selection

Candidate: **Corazón Verde del Chaco** (VCS 2611), a real, registered REDD+ project — chosen over a synthetic/hypothetical polygon because it enables the Phase 4 audit demo (comparing satellite-observed hectares/CO2 against the project's own publicly claimed figures).

No downloadable KML or shapefile for the project boundary was found publicly (2026-08-13). The project's own Project Description (PD) states boundary KML files exist "in the Project's database" — Verra's Registry, which is a JS-rendered application not reachable via a simple fetch. Verra Registry project page: https://registry.verra.org/app/projectDetail/VCS/2611

## How the AOI in `aoi.geojson` was built

Hand-digitized as a bounding box read directly off **Figure 2.2** ("Map of the Corazón Verde del Chaco Project's Initial Project Area") in the official Project Description PDF (Quadriz, 2023-02-28), which has a lat/long graticule overlaid on the property boundary. This is an approximation, not the legal boundary — labeled as such in the GeoJSON's `properties`.

Bounding box read: **58°27'W – 58°22'W, 22°30'S – 22°17'S**.

## Sanity check

The PD states the Initial Project Area is **20,515.0 ha**. The bounding box above computes to **~20,688 ha** (within 0.8%) — close enough to treat the reading as a reasonable stand-in, given it's explicitly a bounding box (a rectangle) around a property whose actual shape is irregular (grid-pattern in the north, river-following boundary in the south, per the PD's Figure 2.2).

## Known limitations

- This is a **bounding box**, not the actual property outline — it will include some area outside the real property and could clip small edges.
- Precision of the graticule reading is on the order of a few arc-minutes (~a few km).
- If a precise boundary later becomes available (e.g. through direct contact with Quadriz/Verra), this file should be replaced and this README updated — the rest of the pipeline should not be sensitive to which one is used, since Sentinel-2/GEDI feasibility work operates at a similar or coarser spatial precision.

## Status

- [x] Boundary approximated and documented (tasks 1.1–1.3, 4.1)
- [ ] GEDI L4A feasibility check (task 3) — pending, blocks calling this AOI final
- [ ] Tutor sign-off (task 5)
