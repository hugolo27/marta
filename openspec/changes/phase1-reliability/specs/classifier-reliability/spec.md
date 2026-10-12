## Purpose

Locates where the operational classifier's per-date forest/non-forest output is unreliable (hard-case types, training-label noise, model disagreement, area of applicability, landscape type), with quantified uncertainty, without changing the classifier or reusing the assessment sample for tuning.

## ADDED Requirements

### Requirement: Hard-case accuracy over an independent disagreement zone
The system SHALL define a zone where independent land cover maps disagree on forest vs. non-forest, without using the classifier's predictions, SHALL draw a random sample within it that is disjoint from the `map-accuracy-assessment` sample, and SHALL report CNN and Random Forest accuracy per interpreted hard-case type with confidence intervals.

#### Scenario: Hard-case results reported
- **WHEN** the hard-case sample has been interpreted
- **THEN** the system reports, per hard-case type, the number of points, its share of the zone, and CNN and RF accuracy with 95% intervals, labeled as describing the disagreement zone

#### Scenario: Sample overlaps the assessment sample
- **WHEN** a candidate hard-case point lies within the exclusion distance of an assessment point
- **THEN** it is not drawn

### Requirement: Training-label noise is measured, not corrected
The system SHALL estimate the label-noise rate of training patches whose MapBiomas label disagrees with independent maps, by interpretation on high-resolution imagery, and SHALL NOT relabel or retrain as part of this capability.

#### Scenario: Label audit reported
- **WHEN** the audited patches have been interpreted
- **THEN** the system reports the noise rate per class within the disagreement set and the implied lower bound for the training split

### Requirement: Calibrated CNN and RF combination evaluated with a pre-registered criterion
The system SHALL calibrate both models' probabilities on the validation split, SHALL compare a weighted ensemble against the CNN on the test split and held-out regions with a criterion fixed before scoring, and SHALL report the outcome without adopting the ensemble as the operational model.

#### Scenario: Ensemble meets the criterion
- **WHEN** the ensemble's mean macro-F1 exceeds the CNN's by more than one combined standard deviation
- **THEN** the system reports it as a finding that motivates a separate change, and the operational model stays unchanged

#### Scenario: Ensemble does not meet the criterion
- **WHEN** the criterion is not met
- **THEN** the system reports the CNN as sufficient, as a valid finding

### Requirement: Model disagreement as a review flag
The system SHALL flag pixels and reference points where CNN and RF disagree at the forest/non-forest level, SHALL report the flagged fraction per area, and SHALL report accuracy separately for agreeing and disagreeing reference points.

#### Scenario: Agreement split reported
- **WHEN** the reference points of an area have been interpreted
- **THEN** the system reports accuracy with confidence intervals for agreeing and disagreeing points, using an estimator valid for a flag that is not a sampling stratum

### Requirement: Area of applicability
The system SHALL compute an area of applicability for the CNN with a threshold derived from training data before any reference point is consulted, and SHALL report the fraction of each area inside it and accuracy inside and outside it.

#### Scenario: Few points outside the area of applicability
- **WHEN** fewer than 20 interpreted points of an area fall outside the area of applicability
- **THEN** the system reports counts only for that group, not an accuracy estimate

### Requirement: Accuracy by landscape type
The system SHALL report forest/non-forest accuracy by fragmentation class and ecoregion, with bins fixed before results are observed and derived from data independent of the classifier.

#### Scenario: Small landscape cell
- **WHEN** a landscape class in an area has fewer than 20 interpreted points
- **THEN** the system reports its count, not an accuracy estimate

### Requirement: Diagnostics do not tune the classifier
The system SHALL NOT use any result of this capability to change the operational classifier, its thresholds or the change-map post-processing within this capability. Any such change SHALL be a separate change re-assessed on a newly drawn reference sample.

#### Scenario: A diagnostic suggests a fix
- **WHEN** a diagnostic shows a weakness that a model or threshold change could address
- **THEN** the system records the evidence and leaves the operational outputs unchanged
