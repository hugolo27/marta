## MODIFIED Requirements

### Requirement: CNN candidate
The system SHALL train a CNN on the 33x33x13 patches from the dataset's train split (12 Sentinel-2 L2A bands plus NDVI; B10 is not part of L2A), predicting the same 3 target classes, using a small custom architecture rather than a large pretrained backbone, and SHALL record for each training run the epoch with the lowest validation loss and the epoch at which training stopped.

#### Scenario: Candidate trained
- **WHEN** the train split's patches are available
- **THEN** the system produces a trained CNN model and reports training/validation loss and accuracy curves, the best epoch and the stop epoch

#### Scenario: Training reaches the epoch cap
- **WHEN** a run reaches the maximum number of epochs without early stopping
- **THEN** the run is flagged as truncated and is not used for any decision until re-run with a higher cap

### Requirement: Baseline vs. candidate evaluation
The system SHALL evaluate both models on the dataset's test split using accuracy, per-class IoU/Dice, and a confusion matrix, and SHALL report whether the CNN meaningfully outperforms the Random Forest baseline rather than assuming it does. Spread across seeds SHALL be reported as the sample standard deviation (`ddof=1`).

#### Scenario: CNN outperforms the baseline
- **WHEN** the CNN's test-set metrics exceed the Random Forest baseline's by a documented margin
- **THEN** the system reports the CNN as the classifier to carry forward, with the comparison metrics as evidence

#### Scenario: CNN does not outperform the baseline
- **WHEN** the CNN's test-set metrics do not meaningfully exceed the Random Forest baseline's
- **THEN** the system reports this as a valid finding, without treating the result as a failure of the evaluation; which model becomes the operational classifier is a separate decision (see Requirement: Operational classifier selection)

## ADDED Requirements

### Requirement: Hyperparameter selection on the validation split
The system SHALL choose the hyperparameters of both the Random Forest baseline and the CNN candidate on the validation split only, over a grid fixed in advance, with the same number of seeds per configuration as the baseline vs. candidate evaluation, using a selection rule pre-registered before any configuration is scored. The test split SHALL be evaluated only once, with the selected configurations.

#### Scenario: Selection run
- **WHEN** the grids and the selection rule have been pre-registered
- **THEN** the system scores every configuration on the validation split and reports, per model, the mean and sample standard deviation of macro-F1 per configuration and the selected configuration

#### Scenario: Pre-registered rule changed after scoring started
- **WHEN** the pre-registered text no longer matches the hash logged before scoring
- **THEN** the selection refuses to run

#### Scenario: Best configuration within noise of the current one
- **WHEN** the best configuration's mean validation macro-F1 does not exceed the current configuration's by more than their pooled sample standard deviation
- **THEN** the current configuration is kept

#### Scenario: Test split used for selection
- **WHEN** a script scores a hyperparameter configuration for the purpose of choosing one
- **THEN** it evaluates on the validation split, never on the test split, the held-out regions or the interpreted reference sample
