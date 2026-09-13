## Why

Every downstream capability in the project — the Sentinel-2/MapBiomas dataset, the CNN classifier, the canopy height inference, the GEDI L4A calibration — needs a concrete geographic boundary to operate on. Nothing else can be built or tested without one. This is also the first concrete step the tutor recommended in the proposed methodology.

## What Changes

- Select and document the project's study area (AOI) within the Paraguayan Chaco.
- Evaluate Corazón Verde del Chaco (VCS 2611) as the primary candidate: it's a real, registered REDD+ project with public claimed boundaries and hectare/CO2 figures, which makes it directly usable later for the audit ("sobreventa") demo. Document a fallback candidate in case its official boundary isn't obtainable at usable precision.
- Produce a versioned AOI artifact (GeoJSON) stored in the repo, plus a short rationale document covering: why this area, its approximate size, and known early risks (e.g. GEDI L4A footprint density/quality over the area, which gates the carbon-estimation pipeline and should be checked as part of this change, not assumed).
- No model code, data pipeline, or training happens in this change — it only establishes the spatial boundary everything else consumes.

## Capabilities

### New Capabilities
- `study-area`: the project's defined geographic area of interest — its source, boundary artifact, rationale, and the constraints downstream capabilities must respect (e.g. area size, coordinate reference system, known data-availability risks within the boundary).

### Modified Capabilities
(none — first capability in the project)

## Impact

- New `data/study_area/` directory holding the AOI as GeoJSON (small, versionable — not raster/imagery, so not excluded by `.gitignore`'s `data/` rule; this is the one exception and should be carved out explicitly in the gitignore if needed).
- No existing code or specs affected — this is the first change in the repo.
- Gates every future capability that touches geospatial data (dataset build, canopy height inference, GEDI calibration, classification).
