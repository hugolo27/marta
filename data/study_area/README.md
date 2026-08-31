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

## Independent cross-check against the official PD text

Re-verified 2026-08-20 by pulling the actual PD text (`Corazon-Verde-del-Chaco-Project-PD-2023.02.28-1.pdf`, same version cited above), not just the Figure 2.2 graticule reading:

- **Department:** the initial project instance sits in **Presidente Hayes Department**, not Alto Paraguay. "Puerto Casado" is the nearest reference point because the closest town, La Victoria, is administratively part of the Puerto Casado district — but that district itself is in Alto Paraguay Department, just near the Presidente Hayes border. Worth being precise about this distinction when writing up the study area for the TFM document.
- **Distance cross-check:** the PD states the initial project instance is "160 km east of Filadelfia and 330 km north northeast of Asunción." Computing 160 km east of Filadelfia (~22°21'S, 60°02'W) at this latitude lands at ~58.48°W — within ~0.1° (a few km) of our digitized bounding box (58°22'–58°27'W). This is an independent confirmation (distance from two named towns, not the map graticule we already used), and it agrees.
- **Area breakdown:** the 20,515.0 ha "Initial Project Area" is the forested, REDD+-eligible portion of a larger 31,858.6 ha property (~64%) — the rest is excluded as riparian buffer, a 25% mandatory green reserve on the forested area, or non-forest. Our AOI approximates the 20,515.0 ha eligible area, not the full property, which is the correct comparison for the carbon/CO2e audit demo.

## GEDI L4A feasibility check (task 3)

Checked with `scripts/gedi_feasibility_check.py` (2026-08-20): 39 GEDI L4A (V3) granules intersect
the AOI's bounding box across the full mission span (2019-04 to 2023-03). Of the shots that
actually fall inside the AOI polygon (not just the granule's bbox), **40,257 footprints**, of
which **3,823 pass `l4a_quality_flag_rel3`** — roughly 18.6 quality-passing footprints per 100 ha
over the 20,589 ha AOI.

**Result: GO.** That's a healthy density for the log-log height→biomass calibration in
`docs/FOUNDATION.md` — no need to widen the AOI or fall back to Chaco Vivo. The low overall quality
pass rate (~9.5%) lines up with the known GEDI bias in low, dry, dispersed canopy — expected for
the Chaco, not a red flag specific to this AOI.

## Known limitations

- This is a **bounding box**, not the actual property outline — it will include some area outside the real property and could clip small edges.
- Precision of the graticule reading is on the order of a few arc-minutes (~a few km).
- If a precise boundary later becomes available (e.g. through direct contact with Quadriz/Verra), this file should be replaced and this README updated — the rest of the pipeline should not be sensitive to which one is used, since Sentinel-2/GEDI feasibility work operates at a similar or coarser spatial precision.

## Status

- [x] Boundary approximated and documented (tasks 1.1–1.3, 4.1)
- [x] GEDI L4A feasibility check (task 3) — GO, see above
- [ ] Tutor sign-off (task 5) — last thing blocking this AOI being final
