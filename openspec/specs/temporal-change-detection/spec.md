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
The system SHALL derive the primary change map from each date's classification collapsed to forest (bosque) and non-forest (pasto, cultivo), labeling each valid pixel as stable forest, stable non-forest, forest loss, or forest gain, after applying the post-processing configuration selected under "Development evaluation against independent loss references". The system SHALL also keep a secondary map of named transitions among {bosque, pasto, cultivo}, labeled as not post-processed and not for area reporting.

#### Scenario: Change map produced
- **WHEN** both per-date classification rasters are available for the AOI
- **THEN** the system produces the forest/non-forest change map with the selected post-processing applied, the secondary named-transition map, and a visualization of each

#### Scenario: Aggregate transition statistics reported
- **WHEN** the change map has been produced
- **THEN** the system reports hectares of AOI area per change category from pixel counts and the known pixel area, labeled as mapped area (not an accuracy-assessed estimate)

#### Scenario: Change below the minimum mapping unit
- **WHEN** the selected configuration includes a minimum mapping unit and a connected patch of forest loss or gain is smaller than it
- **THEN** that patch is relabeled to the corresponding stable class rather than reported as change

### Requirement: Sanity check against independent transition evidence
The system SHALL cross-check a sample of the change map's detected transitions against MapBiomas' own year-over-year classification change in the same locations, as a check against classifier noise (a pixel flipping class between dates without a real land-cover change) rather than treating every detected transition as ground truth.

#### Scenario: Cross-check produced
- **WHEN** the change map reports a transition at a given pixel
- **THEN** the system reports whether MapBiomas' own classification for that pixel shows a corresponding class change between the same two dates, and reports the overall agreement rate rather than only spot-checking a few examples

### Requirement: Development evaluation against independent loss references
The system SHALL evaluate candidate change-map configurations against independent loss references (Hansen Global Forest Change loss and MapBiomas year-over-year transitions) over the case-study AOI and over a separate change-development area with documented forest loss in the same period, and SHALL select the configuration with a rule fixed before any candidate is scored. The system SHALL NOT use points from the manually interpreted reference sample of `map-accuracy-assessment` in this evaluation.

#### Scenario: Candidates scored
- **WHEN** the candidate configurations have been run over the AOI and the change-development area
- **THEN** the system reports, per configuration, forest-loss area and its agreement with each independent reference in both directions, over both areas

#### Scenario: A configuration suppresses real change
- **WHEN** a configuration reduces false loss in the AOI but also removes most loss confirmed by both references in the change-development area
- **THEN** the selection rule rejects it, so a configuration that suppresses all change cannot be selected by default

#### Scenario: Selection recorded
- **WHEN** the selection rule has been applied
- **THEN** the system records the selected configuration, the full table of scored candidates, and the rule as written before scoring
