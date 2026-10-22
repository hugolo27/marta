## MODIFIED Requirements

### Requirement: CNN candidate
The system SHALL train a U-Net for semantic segmentation on Sentinel-2 tiles from the dataset's train split (dry and wet composites, 26 channels), predicting one of the 3 target classes per pixel, SHALL average its 10 m class probabilities over each 3x3 block so that training and evaluation happen at the 30 m resolution of the MapBiomas labels, SHALL ignore pixels whose label is outside the 3 target classes, and SHALL record for each training run the epoch with the best validation macro Dice and the epoch at which training stopped.

#### Scenario: Candidate trained
- **WHEN** the train split's tiles and label maps are available
- **THEN** the system produces a trained U-Net and reports training/validation loss and macro Dice curves, the best epoch and the stop epoch

#### Scenario: Pixel outside the target classes
- **WHEN** a label pixel belongs to a MapBiomas class other than bosque, pasto or cultivo
- **THEN** it contributes to neither the loss nor any metric

#### Scenario: Training reaches the epoch cap
- **WHEN** a run reaches the maximum number of epochs without early stopping
- **THEN** the run is flagged as truncated and is not used for any decision until re-run with a higher cap

## ADDED Requirements

### Requirement: Pilot study before selection
The system SHALL set the early-stopping patience, the validation and test split sizes and the number of training tiles from a pilot study that uses only training and validation data, by a rule written and hashed before the pilot runs, and SHALL discard the pilot's models.

#### Scenario: Pilot completed
- **WHEN** the pilot runs finish
- **THEN** the patience, the split sizes and the learning-curve result are recorded with the measurements that set them, and the selection's pre-registration uses those values

#### Scenario: Test reserve
- **WHEN** the pilot starts
- **THEN** the blocks reserved for test have already been set aside and no pilot step reads them

### Requirement: Segmentation evaluation at label resolution
The system SHALL compare the U-Net with the Random Forest baseline by per-class Dice and macro Dice on the same 30 m pixels, with the Random Forest classifying each 30 m pixel from the mean of its 3x3 block of Sentinel-2 channels.

#### Scenario: Comparison on validation
- **WHEN** both models' selected configurations are scored on validation
- **THEN** the U-Net is reported as better only if its mean macro Dice exceeds the Random Forest's by more than their pooled sample standard deviation over 5 seeds
