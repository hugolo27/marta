## 1. Boundary research

- [x] 1.1 Search for a public, precise boundary (shapefile/KML/GeoJSON) for Corazón Verde del Chaco (VCS 2611) — check Verra Registry project documents, Quadriz/Ostrya public materials, MADES catastro. Result: none found publicly (Verra Registry is a JS app, not fetchable); real KML likely exists there but isn't reachable without a login/browser session
- [x] 1.2 If no precise public boundary is found, hand-digitize an approximate polygon from published maps/coordinates and label it clearly as approximate (not the verified legal boundary) in the rationale doc. Done: bounding box read off Figure 2.2 of the official PD (58°27'-58°22'W, 22°30'-22°17'S)
- [x] 1.3 Sanity-check the resulting polygon's area (ha) against the publicly claimed area. Bounding box computes to ~20,688 ha vs. the PD's stated Initial Project Area of 20,515.0 ha (within 0.8%)

## 2. AOI artifact

- [x] 2.1 Save the boundary as `data/study_area/aoi.geojson` (EPSG:4326, single Polygon/MultiPolygon)
- [x] 2.2 Add a `.gitignore` exception so `data/study_area/` is tracked despite the broader `data/` ignore rule

## 3. GEDI L4A feasibility check

- [ ] 3.1 Stand up minimal one-off tooling to query GEDI L4A granules/footprints intersecting the AOI for a representative date range (e.g. NASA GEDI subsetter or `earthaccess`)
- [ ] 3.2 Record footprint count, date range queried, and a qualitative read on data quality/density
- [ ] 3.3 Decide go/no-go: if footprint density is too sparse for a regional calibration, widen the AOI or fall back to the alternate candidate (Chaco Vivo, VCS 3671) and redo tasks 1-3

## 4. Documentation

- [x] 4.1 Write the rationale doc (source, size, why chosen over alternatives, GEDI feasibility result) that the `study-area` spec requires — `data/study_area/README.md` (GEDI result still pending, will be appended after task 3)
- [x] 4.2 Record the study area decision in `docs/FOUNDATION.md` and `research_docs/ALCANCE_Y_PLANTEAMIENTO_TFM.md` (objetivo 9)

## 5. Tutor sign-off

- [ ] 5.1 Confirm the chosen area with the tutor, or capture their preferred alternative, before treating the AOI as final
