## MODIFIED Requirements

### Requirement: Resolution-matched MapBiomas labels
The system SHALL align MapBiomas Chaco labels (30m native resolution) to Sentinel-2 imagery at 10m by keeping Sentinel-2 on its native UTM 10m grid and resampling MapBiomas by nearest neighbour onto a 30m grid whose cells are exact 3x3 blocks of that 10m grid, and SHALL store with each image tile the label map of the same ground, one label per 30m cell.

#### Scenario: Label-aligned patch produced
- **WHEN** a sampled point's whole tile lies within the sampling footprint and outside every held-out region
- **THEN** the system produces a Sentinel-2 tile whose side is a multiple of 3 pixels, with all channels, and the matching MapBiomas label map whose side is one third of it, with 0 for classes outside bosque, pasto and cultivo

#### Scenario: Tile reaches into a held-out region
- **WHEN** any part of a point's tile falls inside a held-out region
- **THEN** the point is not used
