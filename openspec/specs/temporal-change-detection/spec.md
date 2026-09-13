# temporal-change-detection Specification

## Purpose

Produces a per-pixel land-cover change map between two dates over the case-study AOI by running the already-trained, already-selected classifier on each date and diffing the results, turning two static classifications into evidence of what actually changed.

## Requirements

### Requirement: Per-date dense classification over the AOI
The system SHALL run the operational classifier (per the `land-cover-classifier` capability's decision) over every pixel of the case-study AOI for each of the two comparison dates (2019, 2023), producing one classification raster per date.

#### Scenario: Both dates classified
- **WHEN** cloud-free Sentinel-2 composites are available for the AOI for both 2019 and 2023
- **THEN** the system produces a per-pixel class raster (bosque/pasto/cultivo) for each date, covering the full AOI extent

#### Scenario: A pixel cannot be classified for a date
- **WHEN** a pixel has no valid cloud-free observation for one of the two dates (a residual gap after compositing)
- **THEN** the system marks that pixel as unclassified for that date rather than fabricating a prediction from masked/zero input, and excludes it from the change map rather than reporting a spurious transition

### Requirement: Change map from per-date classifications
The system SHALL diff the two per-date classification rasters pixel-by-pixel into a change map distinguishing no-change from each ecologically meaningful transition (bosque→pasto, bosque→cultivo, pasto→cultivo, and the reverse directions).

#### Scenario: Change map produced
- **WHEN** both per-date classification rasters are available for the AOI
- **THEN** the system produces a pixel-level change map labeling each pixel as no-change or a specific named transition, and a visualization of that map

#### Scenario: Aggregate transition statistics reported
- **WHEN** the change map has been produced
- **THEN** the system reports hectares of AOI area per transition type, derived directly from the change map's pixel counts and the known pixel area

### Requirement: Sanity check against independent transition evidence
The system SHALL cross-check a sample of the change map's detected transitions against MapBiomas' own year-over-year classification change in the same locations, as a check against classifier noise (a pixel flipping class between dates without a real land-cover change) rather than treating every detected transition as ground truth.

#### Scenario: Cross-check produced
- **WHEN** the change map reports a transition at a given pixel
- **THEN** the system reports whether MapBiomas' own classification for that pixel shows a corresponding class change between the same two dates, and reports the overall agreement rate rather than only spot-checking a few examples
