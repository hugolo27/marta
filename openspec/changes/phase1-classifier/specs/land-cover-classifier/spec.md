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

#### Scenario: Random Forest meaningfully outperforms
- **WHEN** the Random Forest baseline's test-set metrics exceed the CNN's by more than the pre-registered margin
- **THEN** the system selects the Random Forest baseline as the operational classifier, since a real accuracy cost outweighs the interpretability benefit, and any Grad-CAM work is scoped as a separate diagnostic tool rather than feeding the production classifier

### Requirement: Cross-region generalization check
The system SHALL evaluate the operational classifier on the Filadelfia held-out sub-region, which was never used in training, validation, or hyperparameter tuning.

#### Scenario: Generalization metrics reported
- **WHEN** the operational classifier is run over the held-out sub-region
- **THEN** the system reports accuracy/agreement metrics for that region alongside the case-study AOI's own test-set metrics

### Requirement: ESA WorldCover cross-check
The system SHALL cross-check the operational classifier's predictions over the held-out sub-region against ESA WorldCover labels, independent of the MapBiomas-derived training labels.

#### Scenario: Cross-check produced
- **WHEN** the operational classifier's predictions over the held-out sub-region are available
- **THEN** the system reports agreement between those predictions and ESA WorldCover, noting explicitly that the "pasto" comparison is a weaker proxy than "bosque" or "cultivo" (per the documented WorldCover legend limitation)
