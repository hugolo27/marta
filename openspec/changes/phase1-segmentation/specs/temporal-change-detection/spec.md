## MODIFIED Requirements

### Requirement: Per-date dense classification over the AOI
The system SHALL run the operational classifier (per the `land-cover-classifier` capability's decision) over the whole case-study AOI for each comparison date (2019, 2023, and 2022 when the persistence filter is a candidate), on Sentinel-2's native UTM 10 m grid with edges at multiples of 30 m, producing one classification raster per date at the 30 m resolution of the labels, with each cell's probabilities averaged over the overlapping windows that cover it.

#### Scenario: Both dates classified
- **WHEN** cloud-free Sentinel-2 composites are available for the AOI for both 2019 and 2023
- **THEN** the system produces a 30 m class raster (bosque/pasto/cultivo) and its class probabilities for each date, covering the full AOI extent, with the checkpoint's hash recorded next to it

#### Scenario: A pixel cannot be classified for a date
- **WHEN** a 30 m cell contains a 10 m pixel with no valid cloud-free observation in either composite for one of the dates (a residual gap after compositing)
- **THEN** the system marks that cell as unclassified for that date rather than fabricating a prediction from masked/zero input, and excludes it from the change map rather than reporting a spurious transition

#### Scenario: Tiled result independent of tiling
- **WHEN** the area is classified in several blocks
- **THEN** the result equals classifying it in one block, verified on synthetic input against the model's direct whole-tile prediction

### Requirement: Change map from per-date classifications
The system SHALL derive the primary change map from each date's classification collapsed to forest (bosque) and non-forest (pasto, cultivo), labeling each valid 30 m cell as stable forest, stable non-forest, forest loss, or forest gain, after the post-processing selected under "Development evaluation against independent loss references", and SHALL keep a secondary named-transition map, not post-processed and not for area reporting.

#### Scenario: Change map produced
- **WHEN** both per-date classification rasters are available for the AOI
- **THEN** the system produces the forest/non-forest change map with the selected post-processing applied, the secondary named-transition map, and a visualization of each

#### Scenario: Aggregate transition statistics reported
- **WHEN** the change map has been produced
- **THEN** the system reports hectares of AOI area per change category from cell counts and the known cell area, labeled as mapped area (not an accuracy-assessed estimate)

#### Scenario: Change below the minimum mapping unit
- **WHEN** the selected configuration includes a minimum mapping unit and a connected patch of forest loss or gain is smaller than 0.5 ha, that is, fewer than 6 cells of 30 m
- **THEN** that patch is relabeled to the corresponding stable class rather than reported as change

### Requirement: Development evaluation against independent loss references
The system SHALL evaluate candidate change-map configurations against Hansen Global Forest Change loss and MapBiomas year-over-year transitions on the map's own 30 m cells, and SHALL select one in a separate change-development area with documented forest loss, by retention of confirmed loss and false loss on confirmed stable forest, with a rule hashed before scoring. It SHALL NOT use the interpreted reference sample of `map-accuracy-assessment`.

#### Scenario: Candidates scored
- **WHEN** the candidate configurations have been run over the AOI and the change-development area
- **THEN** the system reports, per configuration, forest-loss area, retention of confirmed loss, false loss on confirmed stable forest, and agreement with each independent reference in both directions, over both areas

#### Scenario: A configuration suppresses real change
- **WHEN** a configuration reduces false loss but also removes most loss confirmed by both references in the change-development area
- **THEN** the selection rule rejects it, so a configuration that suppresses all change cannot be selected by default

#### Scenario: AOI kept out of the choice
- **WHEN** the selection rule is applied
- **THEN** no AOI metric enters it, and the selected configuration is applied to the AOI only afterwards

#### Scenario: Selection recorded
- **WHEN** the selection rule has been applied
- **THEN** the system records the selected configuration, the full table of scored candidates, and the rule as written before scoring with its hash
