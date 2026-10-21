## MODIFIED Requirements

### Requirement: Cloud-free Sentinel-2 composites
The system SHALL produce cloud-free Sentinel-2 L2A composites (the 12 L2A bands, since B10 is only in L1C, plus NDVI) over the AOI and the wider sampling footprint, for at least two time periods sufficient for both classifier training and temporal change comparison, and for each period SHALL produce both a dry-season (June-September) and a wet-season (January-April) composite of the same year.

#### Scenario: Composite produced for a target period
- **WHEN** a target period and geographic footprint are given
- **THEN** the system returns a dry-season and a wet-season composite, each with no more than a documented maximum residual cloud fraction, or reports which season could not be built for that period

### Requirement: Dataset output format and splits
The system SHALL define and produce the dataset in a documented patch/tile format with train/val/test splits, including one or more designated held-out sub-regions within the wider Chaco sampling footprint, spanning distinct landscape topologies, reserved for a later cross-region generalization check. It SHALL assign splits by spatial blocks whose side is derived from the measured spatial autocorrelation of the labels and the imagery, and SHALL assign splits consistently across every time period a location appears in, not independently per period.

#### Scenario: Dataset assembled
- **WHEN** the composites and aligned labels are ready
- **THEN** the system outputs patches in the documented format, partitioned into train/val/test, with every held-out sub-region excluded from all three

#### Scenario: Block size set
- **WHEN** the split blocks are defined
- **THEN** their side is at least the largest practical range of the fitted semivariograms of the MapBiomas class and NDVI, and the measurement and the derived side are recorded, and every point in a block goes to the same split whatever its class

#### Scenario: A location appears in more than one time period
- **WHEN** the same geographic location is sampled in more than one time period
- **THEN** the system assigns that location's split once, consistently across every period it appears in, so no period-vs-period pair can leak the same location across a train/test boundary
