## MODIFIED Requirements

### Requirement: CNN candidate
The system SHALL train a CNN on patches from the dataset's train split (12 Sentinel-2 L2A bands plus NDVI; B10 is not part of L2A), predicting the same 3 target classes, using a small custom architecture rather than a large pretrained backbone, with an input size of either the 3x3 block aligned to one MapBiomas pixel or a 33x33 window centered on that block, and SHALL record for each training run the input size, the epoch with the lowest validation loss and the epoch at which training stopped.

#### Scenario: Candidate trained
- **WHEN** the train split's patches are available
- **THEN** the system produces a trained CNN model and reports its input size, training/validation loss and accuracy curves, the best epoch and the stop epoch

#### Scenario: Training reaches the epoch cap
- **WHEN** a run reaches the maximum number of epochs without early stopping
- **THEN** the run is flagged as truncated and is not used for any decision until re-run with a higher cap

## ADDED Requirements

### Requirement: Input size selection on the validation split
The system SHALL choose the operational CNN's input size between 3x3 and 33x33 on the validation split only, after selecting each size's hyperparameters on the validation split, using a rule pre-registered before any 3x3 configuration is scored. The 3x3 input SHALL be the default, replaced by 33x33 only if the 33x33 CNN's mean validation macro-F1 exceeds the 3x3 CNN's by more than their pooled sample standard deviation.

#### Scenario: 33x33 beats 3x3 beyond noise
- **WHEN** the selected 33x33 CNN's mean validation macro-F1 exceeds the selected 3x3 CNN's by more than their pooled sample standard deviation
- **THEN** the 33x33 CNN stays the operational classifier

#### Scenario: 33x33 does not beat 3x3 beyond noise
- **WHEN** the difference is within the pooled sample standard deviation, or favours 3x3
- **THEN** the 3x3 CNN becomes the operational classifier and every downstream product that depends on it is regenerated

#### Scenario: Pre-registered rule changed after scoring started
- **WHEN** the pre-registered text no longer matches the hash logged before scoring
- **THEN** the selection refuses to run
