## Purpose

Forecasts future land cover change and its projected CO2e for the study area, evaluating a classical CA-Markov baseline against a spatiotemporal deep learning candidate, so the "does the added complexity earn its keep" test already applied to CNN vs. Random Forest also covers the predictive side of the pipeline.

## ADDED Requirements

### Requirement: Historical land cover series
The system SHALL build a multi-year land cover series for the AOI from MapBiomas Chaco to serve as the input both predictive models are trained and evaluated on.

#### Scenario: Sufficient historical depth available
- **WHEN** the AOI's MapBiomas coverage spans enough consecutive years to hold out at least one known year for backtesting
- **THEN** the system builds the series and proceeds to train both the baseline and the candidate

#### Scenario: Insufficient historical depth
- **WHEN** the AOI's MapBiomas coverage does not span enough years to hold out a backtesting year
- **THEN** the system reports that the predictive extension cannot be evaluated for this AOI, rather than training on an unvalidated series

### Requirement: CA-Markov baseline forecast
The system SHALL produce a baseline forecast of future land cover change using a Markov transition matrix, fit on the historical land cover series, combined with a cellular automaton that allocates the predicted change to specific pixels.

#### Scenario: Baseline forecast produced
- **WHEN** the historical land cover series and driver/suitability layers are available
- **THEN** the system outputs both the transition matrix and a pixel-level map of predicted future land cover

### Requirement: Driver and suitability layers
The system SHALL incorporate spatial driver layers — proximity to roads, proximity to already-cleared edges, terrain/slope, and land tenure or protected-area status — into the CA-Markov suitability map used to allocate predicted change.

#### Scenario: Driver layer missing or unsourced
- **WHEN** one or more driver layers cannot be sourced for the AOI
- **THEN** the system documents which layers are missing and how their absence affects the suitability map, rather than silently omitting them

### Requirement: Deep learning candidate evaluated against the baseline
The system SHALL produce a candidate forecast using a spatiotemporal deep learning model (ConvLSTM or 3D-CNN) trained on the same historical land cover series, and SHALL evaluate it against the CA-Markov baseline via backtesting on a held-out known year using Figure of Merit and/or Kappa, rather than assuming the candidate is superior by default.

#### Scenario: Candidate outperforms the baseline
- **WHEN** backtesting shows the deep learning candidate's Figure of Merit/Kappa exceeds the CA-Markov baseline by a documented margin
- **THEN** the system reports the candidate as the preferred predictive model, with the comparison metrics as evidence

#### Scenario: Candidate does not outperform the baseline
- **WHEN** backtesting shows the deep learning candidate does not meaningfully outperform the CA-Markov baseline
- **THEN** the system reports this as a valid finding and keeps CA-Markov as the predictive model, without treating the negative result as a failure of the extension

### Requirement: Projected CO2e from predicted change
The system SHALL translate predicted future land-cover change into a projected CO2e figure by applying the historical carbon-density-per-transition-type deltas — already computed from observed change in the carbon estimation pipeline — to the pixels either predictive model marks as likely to change, without requiring synthetic future satellite imagery or re-run canopy-height inference.

#### Scenario: Carbon deltas available for the predicted transition types
- **WHEN** the predicted change map contains transition types (e.g. bosque→desmonte) for which a historical carbon-density delta was already computed
- **THEN** the system produces a projected CO2e figure for the predicted change

#### Scenario: Carbon delta missing for a predicted transition type
- **WHEN** the predicted change map contains a transition type with no corresponding historical carbon-density delta
- **THEN** the system reports that transition's projected CO2e as unavailable, rather than substituting an unrelated or default value

### Requirement: Cross-region generalization check
The system SHALL support evaluating the trained predictive model against a held-out sub-region within the Paraguayan Chaco distinct from the case-study AOI, to test whether the model's classification and prediction accuracy transfers beyond the single case study.

#### Scenario: Generalization check performed
- **WHEN** a held-out sub-region within the Paraguayan Chaco with adequate MapBiomas/GEDI coverage is designated for the check
- **THEN** the system reports accuracy/agreement metrics for that sub-region alongside the case-study AOI's own metrics, without requiring an interactive tool for arbitrary user-drawn polygons
