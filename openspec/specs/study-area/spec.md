# study-area Specification

## Purpose

Defines the single geographic area of interest (AOI) that every other capability — dataset build, classification, canopy height inference, GEDI calibration — consumes as its spatial boundary.

## Requirements

### Requirement: Versioned AOI artifact
The project SHALL store a single study area boundary as a versioned GeoJSON file in the repository, usable directly as input to Earth Engine and GEDI data queries.

#### Scenario: AOI file is valid and unambiguous
- **WHEN** any downstream capability reads the study area
- **THEN** it finds exactly one GeoJSON file containing a single Polygon or MultiPolygon geometry in EPSG:4326, with no ambiguity about which boundary is authoritative

### Requirement: Documented selection rationale
The study area selection SHALL be documented with its source, approximate size in hectares, and why it was chosen over alternatives.

#### Scenario: Rationale is traceable
- **WHEN** the tutor or a committee member reviews the study area choice
- **THEN** they can find a written rationale explaining the source of the boundary (e.g. a real registered project's public documentation, or a hand-defined alternative), its approximate area, and why it fits the project's needs (e.g. enabling a later audit comparison against publicly claimed figures)

### Requirement: GEDI L4A feasibility check before finalizing
The study area SHALL NOT be considered final until GEDI L4A footprint availability within its boundary and a representative date range has been checked and documented.

#### Scenario: Feasibility check blocks a data-sparse area
- **WHEN** a candidate AOI has too few or too poor-quality GEDI L4A footprints to support the height-to-biomass calibration planned in the carbon estimation capability
- **THEN** the AOI is rejected or adjusted (e.g. widened, or a different candidate chosen) before downstream capabilities begin, and the check's result (footprint count, date range queried) is documented alongside the rationale

#### Scenario: Feasibility check passes
- **WHEN** a candidate AOI has sufficient GEDI L4A footprint density and quality for a regional calibration
- **THEN** the AOI is finalized and the footprint count/date range is recorded as part of the rationale documentation
