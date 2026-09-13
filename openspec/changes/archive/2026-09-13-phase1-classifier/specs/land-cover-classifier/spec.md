## Purpose

Trains and evaluates a Random Forest baseline and a CNN candidate for per-date land cover classification (bosque/pasto/cultivo), establishing whether the CNN's added complexity is justified before it becomes the basis for Grad-CAM, temporal comparison, and carbon estimation.

## ADDED Requirements

### Requirement: Random Forest baseline
The system SHALL train a Random Forest classifier on per-pixel spectral features (12 Sentinel-2 bands plus NDVI) using the dataset's train split, predicting one of the 3 target classes (bosque/pasto/cultivo).

#### Scenario: Baseline trained
- **WHEN** the train split is available with spectral features and labels
- **THEN** the system produces a trained Random Forest model and reports its training-time class distribution

### Requirement: CNN candidate
The system SHALL train a CNN on the 33x33x13 patches from the dataset's train split, predicting the same 3 target classes, using a small custom architecture rather than a large pretrained backbone.

#### Scenario: Candidate trained
- **WHEN** the train split's patches are available
- **THEN** the system produces a trained CNN model and reports training/validation loss and accuracy curves

### Requirement: Baseline vs. candidate evaluation
The system SHALL evaluate both models on the dataset's test split using accuracy, per-class IoU/Dice, and a confusion matrix, and SHALL report whether the CNN meaningfully outperforms the Random Forest baseline rather than assuming it does.

#### Scenario: CNN outperforms the baseline
- **WHEN** the CNN's test-set metrics exceed the Random Forest baseline's by a documented margin
- **THEN** the system reports the CNN as the classifier to carry forward, with the comparison metrics as evidence

#### Scenario: CNN does not outperform the baseline
- **WHEN** the CNN's test-set metrics do not meaningfully exceed the Random Forest baseline's
- **THEN** the system reports this as a valid finding, without treating the result as a failure of the evaluation — which model becomes the operational classifier is a separate decision (see Requirement: Operational classifier selection)

### Requirement: Operational classifier selection
The system SHALL select the operational classifier used by downstream capabilities (Grad-CAM, temporal comparison, carbon estimation) based on the accuracy comparison together with whether per-prediction interpretability is required, not on accuracy alone — because Grad-CAM can only ever attach to a differentiable model with spatial activation maps, never to Random Forest, regardless of future tooling investment.

#### Scenario: Tied or comparable accuracy
- **WHEN** the CNN's test-set metrics are statistically tied with the Random Forest baseline (within the pre-registered margin) or otherwise comparable
- **THEN** the system selects the CNN as the operational classifier, since it uniquely supports per-prediction Grad-CAM evidence at no meaningful accuracy cost, while the Random Forest result is retained as the documented baseline comparison finding, not discarded

#### Scenario: Random Forest meaningfully outperforms across held-out regions generally
- **WHEN** the Random Forest baseline's held-out-region metrics exceed the CNN's by more than the pre-registered margin in most or all evaluated regions
- **THEN** the system selects the Random Forest baseline as the operational classifier, since a real, general accuracy cost outweighs the interpretability benefit, and any Grad-CAM work is scoped as a separate diagnostic tool rather than feeding the production classifier

#### Scenario: A landscape-specific weakness is identified in one region only
- **WHEN** one model loses to the other by more than the pre-registered margin in exactly one held-out region, with the loss traced to a specific, mechanistically-understood cause tied to that region's landscape (not a general property), while winning or tying in the AOI and the other held-out regions
- **THEN** the system MAY still select the stronger-overall model as operational, provided the identified weakness is documented explicitly as a known limitation, is checked against the actual deployment target's landscape profile, and the losing model's result remains available as a cross-check for landscapes matching the weak spot

### Requirement: Cross-region generalization check
The system SHALL evaluate both models on held-out sub-regions spanning distinct landscape topologies, geographically excluded from training, validation, and hyperparameter tuning, and SHALL run each region's comparison across multiple seeds rather than a single run, so a region-level result can be told apart from single-run noise.

#### Scenario: Generalization metrics reported
- **WHEN** a held-out region is evaluated
- **THEN** the system reports mean and standard deviation accuracy/agreement metrics for both models in that region, alongside the case-study AOI's own test-set metrics

#### Scenario: A single held-out region is insufficient to characterize generalization
- **WHEN** only one held-out region has been evaluated
- **THEN** the system SHALL NOT treat that region's result as representative of generalization in general — a landscape-specific weakness must be distinguished from a general one using additional, topologically distinct held-out regions before it informs the operational-classifier decision

### Requirement: ESA WorldCover cross-check
The system SHALL cross-check both models' predictions over each held-out region against ESA WorldCover labels, independent of the MapBiomas-derived training labels.

#### Scenario: Cross-check produced
- **WHEN** a model's predictions over a held-out region are available
- **THEN** the system reports agreement between those predictions and ESA WorldCover, noting explicitly that the "pasto" comparison is a weaker proxy than "bosque" or "cultivo" (per the documented WorldCover legend limitation)
