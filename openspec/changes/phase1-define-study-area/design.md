## Context

See proposal.md for motivation. This is the first change in the repo — no existing code, data pipeline, or GEE/GEDI access has been set up yet, so this design also has to decide the minimal tooling needed to run a GEDI footprint feasibility check.

## Goals / Non-Goals

**Goals:**
- Decide the study area boundary and record it as a reusable artifact.
- Verify GEDI L4A footprint availability over that boundary before treating it as final, so the carbon-estimation capability doesn't discover infeasibility later.

**Non-Goals:**
- Building any part of the dataset, classification, or carbon pipelines themselves.
- Setting up the full project's Python environment/dependencies beyond what's needed to query GEDI footprint counts (that belongs to whichever capability first needs a real Earth Engine/GEDI pipeline).

## Decisions

**Primary candidate: Corazón Verde del Chaco (VCS 2611) boundary, not a synthetic/hypothetical area.**
Alternatives considered: a hand-drawn hypothetical polygon (simpler, no dependency on finding the real boundary) or Chaco Vivo (VCS 3671, larger project). Using a real, registered project lets the capstone audit demo (comparing satellite-observed hectares/CO2 against the project's publicly claimed figures) work with actual claimed numbers instead of invented ones — the whole point of the "sobreventa" framing in the research question. Chaco Vivo is larger (187,916 ha vs. 32,000 ha), which increases processing cost without adding methodological value for a bounded TFM; Corazón Verde del Chaco's smaller committed area (32,000 ha of a 300,000 ha target) is likely more tractable.

**Storage: `data/study_area/aoi.geojson`, EPSG:4326.**
GeoJSON is the natural interchange format for Earth Engine (`ee.Geometry`/`ee.FeatureCollection`) and for GEDI subsetting tools, and is small enough to version in git even though `data/` is otherwise gitignored — this one file is a boundary definition, not imagery or model output.

**Feasibility check: query GEDI L4A footprint count/date range over the candidate AOI directly, before writing any project pipeline code.**
This can be done with a short one-off script (e.g. using NASA's GEDI subsetter or the `earthaccess`/`h5py` route against GEDI L4A granules, or via Earth Engine if a suitable community GEDI asset is available) — whichever is fastest to stand up, since this is a go/no-go check, not reusable pipeline infrastructure. The tasks.md for this change should not over-invest in productionizing this script.

## Risks / Trade-offs

- **[Risk]** The official Corazón Verde del Chaco boundary may not be publicly available at usable precision (only marketing-level maps, no downloadable shapefile/KML). → **Mitigation:** if no precise public boundary is found, hand-digitize an approximate polygon from published maps/coordinates and label it explicitly as an approximation in the rationale doc, not as the verified legal boundary.
- **[Risk]** GEDI footprint density over the chosen AOI may be too sparse for a reliable regional calibration, given the Chaco's dry, short, dispersed vegetation (a concern the tutor's own methodology doc raises). → **Mitigation:** this is exactly why the feasibility check is part of this change rather than assumed; if it fails, widen the AOI or fall back to Chaco Vivo before any pipeline code is written.
- **[Trade-off]** Choosing a real project over a synthetic area adds a dependency on finding/trusting a real boundary, but is required for the capstone audit demo already committed to in `docs/FOUNDATION.md`.

## Open Questions

- Final confirmation with the tutor: does the tutor agree with Corazón Verde del Chaco as the study area, or is there a different area in mind? (The tutor's methodology doc says "real o hipotética" — either is acceptable, so this is a preference check, not a blocking unknown.)
