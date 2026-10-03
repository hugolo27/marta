## Purpose

Measures how well the operational classifier's per-date maps and the derived change map match independently interpreted reference data, using the accuracy bar the case-study project itself must meet (VM0007) and good-practice area estimation for land change, so downstream carbon figures rest on assessed areas rather than raw pixel counts.

## ADDED Requirements

### Requirement: Independent reference sample
The system SHALL draw a stratified random sample of assessment points whose reference labels come from visual interpretation of high-resolution imagery, independent of MapBiomas, ESA WorldCover, Hansen, and the classifier's own predictions. The system SHALL archive every point with its coordinates, sampling stratum, inclusion probability, reference label per date, imagery source and date used, and interpreter notes.

#### Scenario: Sample drawn and archived
- **WHEN** the change map selected by `temporal-change-detection` is available for the AOI
- **THEN** the system produces a sample with a known inclusion probability per point, and stores it with its reference labels in a versioned, re-checkable form

#### Scenario: Interpretation is blind to the model
- **WHEN** a point is presented for reference interpretation
- **THEN** the interpreter sees the high-resolution imagery for each date but not the classifier's predicted class or change label for that point

#### Scenario: Reference imagery unavailable for a point-date
- **WHEN** no high-resolution imagery within the same year exists for a point, or it is cloud-covered
- **THEN** the point-date is recorded as uninterpretable with the reason, excluded from the estimates, and the count of such exclusions per stratum is reported rather than silently dropped or labeled by guess

### Requirement: Reference labels follow the Paraguayan forest definition
The system SHALL label each point-date as forest or non-forest according to Paraguay's CDM forest definition: minimum 25% tree crown cover, minimum 0.5 ha, and potential to reach 5 m height.

#### Scenario: Open or sparse woody vegetation
- **WHEN** a point falls on woody vegetation whose crown cover is judged below 25% or whose patch is smaller than 0.5 ha
- **THEN** the point is labeled non-forest and flagged, so the share of classifier "bosque" predictions that fail the definition can be reported separately

### Requirement: Per-date forest/non-forest accuracy against the VM0007 gate
The system SHALL assess each date's AOI map (2019, 2023), collapsed to forest and non-forest, against the reference labels. It SHALL report the error matrix, overall accuracy, and user's and producer's accuracy per class with 95% confidence intervals. It SHALL report pass or fail against the VM0007 requirement: at least 50 interpreted points per class and overall accuracy of at least 90%.

#### Scenario: Gate passed
- **WHEN** both dates have at least 50 interpreted points per class and overall accuracy of at least 90%
- **THEN** the system reports the classifier as meeting the VM0007 accuracy bar for use in change detection, with the error matrices as evidence

#### Scenario: Gate failed
- **WHEN** either date has fewer than 50 interpreted points in a class or overall accuracy below 90%
- **THEN** the system reports the failure with the error analysis (which class, which confusion, which landscape), does not present the change map as meeting the bar, and marks the classifier as requiring a further change before Fase 2 relies on it

### Requirement: Error-adjusted change area estimation
The system SHALL estimate, from the reference sample, the area of forest loss, forest gain, stable forest and stable non-forest over the AOI using a stratified estimator of area and accuracy. It SHALL report the error-adjusted area with a 95% confidence interval alongside the mapped (pixel-count) area.

#### Scenario: Area estimates produced
- **WHEN** the change-stratified reference sample has been interpreted
- **THEN** the system reports, per change category, the mapped area, the error-adjusted area, its 95% confidence interval, and the user's and producer's accuracy of that category

#### Scenario: Omitted change inside a large stable stratum
- **WHEN** reference points in a stable stratum show real change that the map missed
- **THEN** that omission contributes to the error-adjusted area of the change category, rather than only commission errors inside the mapped change strata being counted

#### Scenario: Mapped change stratum is empty
- **WHEN** the selected change map contains no pixels of a change category
- **THEN** that stratum is not sampled, and the category's error-adjusted area is estimated from omissions found in the stable strata, with its confidence interval

### Requirement: Downstream area figures are error-adjusted
The system SHALL expose the error-adjusted change areas and their confidence intervals as the area figures consumed by carbon estimation. It SHALL NOT hand raw change-map pixel counts downstream as if they were assessed areas.

#### Scenario: Carbon estimation requests change areas
- **WHEN** a downstream capability requests hectares per change category for the AOI
- **THEN** it receives the error-adjusted estimate with its confidence interval, with the mapped pixel-count area available only as a labeled secondary value

### Requirement: Reference-based accuracy in held-out regions
The system SHALL assess 2023 forest/non-forest accuracy against interpreted reference samples in each held-out region used by `land-cover-classifier` (Filadelfia, Bahía Negra, Pozo Colorado), with at least 50 interpreted points per class per region, reporting the same metrics as the AOI assessment.

#### Scenario: Held-out region assessed
- **WHEN** a held-out region's reference sample has been interpreted
- **THEN** the system reports that region's error matrix, overall accuracy and per-class accuracies with confidence intervals next to the AOI's, and states whether that region meets the 90% bar

### Requirement: Reference data consistency is measured
The system SHALL re-interpret a random 10% subset of the reference points blind to the first interpretation, and SHALL report the agreement rate. It SHALL adjudicate disagreements before the final estimates are computed.

#### Scenario: Consistency reported
- **WHEN** the repeat interpretation of the subset is complete
- **THEN** the system reports the agreement rate, lists the disagreeing points with the adjudicated label, and computes final estimates from adjudicated labels only

### Requirement: Assessment sample is not reused for tuning
The system SHALL NOT use the reference sample to tune, retrain, or select models, thresholds, or post-processing. If any such change is made after the assessment, the system SHALL re-assess on a newly drawn reference sample before reporting accuracy for the changed model.

#### Scenario: Classifier changed after assessment
- **WHEN** a model, threshold, or post-processing step is changed in response to this assessment's results
- **THEN** the previously reported accuracy is marked as applying to the previous version only, and a new sample is drawn and interpreted before accuracy is reported for the new version
