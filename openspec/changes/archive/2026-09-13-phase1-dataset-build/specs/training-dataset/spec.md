## Purpose

Produces the Sentinel-2 + MapBiomas Chaco dataset — imagery composites, resolution-matched labels, and a held-out accuracy cross-check — that the classifier, baseline, and temporal comparison all consume as their single source of training and evaluation data.

## ADDED Requirements

### Requirement: Cloud-free Sentinel-2 composites
The system SHALL produce cloud-free Sentinel-2 L2A composites (13 bands plus spectral indices) over the AOI and the wider sampling footprint, for at least two time periods sufficient for both classifier training and temporal change comparison.

#### Scenario: Composite produced for a target period
- **WHEN** a target period and geographic footprint are given
- **THEN** the system returns a composite with no more than a documented maximum residual cloud fraction, or reports that no acceptable composite could be built for that period

### Requirement: Resolution-matched MapBiomas labels
The system SHALL align MapBiomas Chaco labels (30m native resolution) to Sentinel-2 imagery (10m native resolution) by keeping Sentinel-2 at native resolution and grouping it into 3x3-pixel blocks per MapBiomas pixel, rather than downsampling Sentinel-2 to 30m.

#### Scenario: Label-aligned patch produced
- **WHEN** a MapBiomas-labeled pixel falls within the sampling footprint
- **THEN** the system produces a 33x33 Sentinel-2 pixel patch (all bands/indices), centered on that pixel's 3x3-pixel block, tagged with that pixel's single MapBiomas class — the 3x3 block sets label alignment, the wider 33x33 window gives the CNN real spatial context

### Requirement: Independent accuracy cross-check via ESA WorldCover
The system SHALL extract ESA WorldCover (10m) labels for a held-out evaluation area, kept separate from the MapBiomas-derived training labels, to serve as an accuracy cross-check independent of the training ground truth.

#### Scenario: Held-out area evaluated
- **WHEN** the classifier (built in a later change) is evaluated
- **THEN** its predictions over the held-out area can be scored against ESA WorldCover labels that were never used in training

### Requirement: Cloud coverage assessment and SAR gap decision
The system SHALL assess real cloud coverage over the sampling footprint for the chosen periods and record whether Sentinel-1 SAR is needed to fill optical gaps, rather than assuming the answer upfront.

#### Scenario: Cloud coverage acceptable
- **WHEN** the assessed cloud coverage for the chosen periods stays under the documented threshold
- **THEN** the system proceeds without Sentinel-1 SAR and records that decision with its supporting cloud-coverage figures

#### Scenario: Cloud coverage leaves real gaps
- **WHEN** the assessed cloud coverage leaves gaps that cloud-free compositing cannot fill for a needed period
- **THEN** the system flags the gap and records that Sentinel-1 SAR (or an alternative period) is needed, rather than silently shipping a degraded composite

### Requirement: Dataset output format and splits
The system SHALL define and produce the dataset in a documented patch/tile format with train/val/test splits, including one or more designated held-out sub-regions within the wider Chaco sampling footprint — spanning distinct landscape topologies, not just one — reserved for a later cross-region generalization check, and SHALL assign splits consistently across every time period a location appears in, not independently per period.

#### Scenario: Dataset assembled
- **WHEN** the composites and aligned labels are ready
- **THEN** the system outputs patches in the documented format, partitioned into train/val/test, with every held-out sub-region excluded from all three

#### Scenario: A location appears in more than one time period
- **WHEN** the same geographic location is sampled in more than one time period (e.g. its land cover changed between periods, or its MapBiomas classification happened to draw it in both)
- **THEN** the system assigns that location's split once, consistently across every period it appears in, so no period-vs-period pair can leak the same location across a train/test boundary
