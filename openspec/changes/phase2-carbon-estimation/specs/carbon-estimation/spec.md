## Purpose

Estimates per-pixel biomass, carbon and CO2e density for the study periods, and the observed ΔCO2e over the error-adjusted change areas assessed in Fase 1, comparing a height-only calibration baseline against a SAR-augmented candidate under a pre-registered criterion, with propagated uncertainty, so the carbon figure is as auditable as the classification that feeds it.

## ADDED Requirements

### Requirement: Canopy height by inference per period
The system SHALL infer canopy height with the pretrained ETH Global Canopy Height model on Sentinel-2 imagery of each study period, in the input format the model was trained on, and SHALL mask predictions whose model-reported uncertainty exceeds a documented threshold.

#### Scenario: Height map produced for a period
- **WHEN** cloud-masked Sentinel-2 scenes exist for the period
- **THEN** the system outputs a canopy height map and its uncertainty layer on the Sentinel-2 grid, and reports the fraction of pixels masked by the uncertainty threshold

#### Scenario: Season or input aggregation affects height
- **WHEN** dry-season and wet-season imagery, or per-scene aggregation and a median composite, give materially different heights over stable forest
- **THEN** the system records the difference and the chosen window and aggregation with their justification, rather than picking them silently

### Requirement: Filtered GEDI L4A reference sample
The system SHALL build a reference sample of GEDI L4A footprints that pass the quality flag, are paired with predictors from imagery of their own shot year, and fall on pixels with no land cover change around the shot date.

#### Scenario: Unstable footprint excluded
- **WHEN** a footprint lies on a pixel with forest loss or a land cover class change in its shot year or the year before
- **THEN** the footprint is excluded and counted in the filtering report

#### Scenario: Held-out regions kept out of calibration
- **WHEN** the calibration sample is assembled
- **THEN** no footprint from the Filadelfia, Bahía Negra or Pozo Colorado held-out regions is included

### Requirement: SAR feature extraction
The system SHALL extract Sentinel-1 features (and ALOS-2 PALSAR-2 features where available for the period) at each reference footprint and over the mapped area, and SHALL record the number of Sentinel-1 acquisitions per period.

#### Scenario: PALSAR-2 missing for a period
- **WHEN** no PALSAR-2 data is available in the processing platform for one of the study periods
- **THEN** the system documents the gap and excludes PALSAR-2 from that period's candidate, rather than substituting data from a different year

### Requirement: Baseline vs. candidate evaluation with a pre-registered criterion
The system SHALL fit the height-only power-law baseline and the SAR-augmented candidates on the same sample, evaluate them with spatial block cross-validation and on the held-out regions, and SHALL decide using a criterion fixed before results are observed.

#### Scenario: Candidate outperforms the baseline
- **WHEN** the candidate's mean RMSE is lower than the baseline's by more than one combined standard deviation and its bias in the low-biomass stratum is not worse
- **THEN** the system reports the candidate as the operational calibration, with the comparison metrics as evidence

#### Scenario: Candidate does not outperform the baseline
- **WHEN** the criterion is not met
- **THEN** the system keeps the baseline and reports the result as a valid finding, not as a failure

### Requirement: Ablation study
The system SHALL report performance for each input combination (height only, height with Sentinel-1, height with PALSAR-2, height with both, SAR only) under the same evaluation protocol.

#### Scenario: Ablation table produced
- **WHEN** all feature sets have been evaluated
- **THEN** the system outputs one table with the metrics of every combination and model type

### Requirement: CO2e conversion with propagated uncertainty
The system SHALL convert biomass density to total biomass, carbon and CO2e using documented IPCC factors, and SHALL propagate height, regression and conversion-factor uncertainty to a per-pixel interval.

#### Scenario: Density map with interval
- **WHEN** the operational calibration is applied to a period
- **THEN** the system outputs mean CO2e density and a 90% interval, and records the factor values and their sources in the run configuration

### Requirement: Observed ΔCO2e on error-adjusted areas
The system SHALL compute ΔCO2e for each change category of the AOI's forest/non-forest change map by combining the error-adjusted area of that category from `map-accuracy-assessment` with the mean per-hectare density change, and SHALL propagate the area confidence interval into the ΔCO2e interval. It SHALL NOT report a pixel-count sum over mapped change pixels as the ΔCO2e figure.

#### Scenario: AOI ΔCO2e computed
- **WHEN** both period density maps and the error-adjusted change areas exist
- **THEN** the system reports ΔCO2e per change category with its interval, and the pixel-sum over mapped change pixels only as a labeled secondary value

#### Scenario: Error-adjusted areas not yet available
- **WHEN** the error-adjusted change areas have not been produced
- **THEN** the system does not report an AOI ΔCO2e, rather than falling back to mapped areas

### Requirement: Carbon-density deltas per class pair
The system SHALL export, for downstream predictive modeling, the mean CO2e density per land cover class from stable reference footprints and the delta for each class pair, with intervals.

#### Scenario: Class without enough footprints
- **WHEN** a class has too few stable footprints for a stable mean density
- **THEN** its deltas are reported as unavailable rather than estimated from an unrelated class

### Requirement: Independent comparison and documented circularity
The system SHALL compare its aggregated estimates against at least one open product not used in calibration, and SHALL document that height and biomass labels both derive from GEDI.

#### Scenario: Comparison against an external product
- **WHEN** the AOI and held-out region estimates are available
- **THEN** the system reports them next to the corresponding external estimates (e.g. ESA CCI Biomass, FREL dry-forest factors), with the differences discussed rather than hidden
