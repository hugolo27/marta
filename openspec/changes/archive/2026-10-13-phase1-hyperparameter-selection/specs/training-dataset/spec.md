## MODIFIED Requirements

### Requirement: Cloud-free Sentinel-2 composites
The system SHALL produce cloud-free Sentinel-2 L2A composites (the 12 L2A bands, since B10 is only in L1C, plus NDVI) over the AOI and the wider sampling footprint, for at least two time periods sufficient for both classifier training and temporal change comparison.

#### Scenario: Composite produced for a target period
- **WHEN** a target period and geographic footprint are given
- **THEN** the system returns a composite with no more than a documented maximum residual cloud fraction, or reports that no acceptable composite could be built for that period
