## MODIFIED Requirements

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

## ADDED Requirements

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
