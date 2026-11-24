## MODIFIED Requirements

### Requirement: CNN candidate
The system SHALL train a U-Net for semantic segmentation on the train split's Sentinel-2 tiles (dry and wet composites, 26 channels), predicting one of the 3 target classes per pixel, with its 10 m class probabilities averaged over each 3x3 block so that training and evaluation happen at the 30 m resolution of the MapBiomas labels, and SHALL record for each run the epoch with the best validation macro Dice and the stop epoch.

#### Scenario: Candidate trained
- **WHEN** the train split's tiles and label maps are available
- **THEN** the system produces a trained U-Net and reports training/validation loss and macro Dice curves, the best epoch and the stop epoch

#### Scenario: Pixel outside the target classes
- **WHEN** a label pixel belongs to a MapBiomas class other than bosque, pasto or cultivo
- **THEN** it contributes to neither the loss nor any metric

#### Scenario: Training reaches the epoch cap
- **WHEN** a run reaches the maximum number of epochs without early stopping
- **THEN** the run is flagged as truncated and is not used for any decision until re-run with a higher cap

### Requirement: Cross-region generalization check
The system SHALL evaluate both models on held-out sub-regions spanning distinct landscape topologies, geographically excluded from training, validation, and hyperparameter tuning, by classifying each region wall to wall at 30 m and scoring per-class and macro Dice against MapBiomas on every labeled cell, and SHALL run each region's comparison across the 5 seeds of the test rather than a single run, so a region-level result can be told apart from single-run noise.

#### Scenario: Generalization metrics reported
- **WHEN** a held-out region is evaluated
- **THEN** the system reports mean and sample standard deviation of macro Dice and per-class Dice for both models in that region, the better-than result under the test's rule, and the test-split metrics alongside

#### Scenario: A seed retrained for the check
- **WHEN** a seed's checkpoint was not kept by the test and the model is retrained with the same configuration, seed, commit and device
- **THEN** the retrained model is used as a new run of that configuration, and its gap to the test run of the same seed is measured and reported, since GPU training is not bit-for-bit deterministic

#### Scenario: A single held-out region is insufficient to characterize generalization
- **WHEN** only one held-out region has been evaluated
- **THEN** the system SHALL NOT treat that region's result as representative of generalization in general; a landscape-specific weakness must be distinguished from a general one using additional, topologically distinct held-out regions before it informs the operational-classifier decision

### Requirement: ESA WorldCover cross-check
The system SHALL cross-check both models' predictions over each held-out region against ESA WorldCover labels on the same 30 m cells, independent of the MapBiomas-derived training labels.

#### Scenario: Cross-check produced
- **WHEN** a model's predictions over a held-out region are available
- **THEN** the system reports agreement between those predictions and ESA WorldCover, noting explicitly that the "pasto" comparison is a weaker proxy than "bosque" or "cultivo" (per the documented WorldCover legend limitation)

## ADDED Requirements

### Requirement: Pilot study before selection
The system SHALL set the early-stopping patience, the validation and test split sizes and the number of training tiles from a pilot study that uses only training and validation data, by a rule written and hashed before the pilot runs, and SHALL discard the pilot's models.

#### Scenario: Pilot completed
- **WHEN** the pilot runs finish
- **THEN** the patience, the split sizes and the learning-curve result are recorded with the measurements that set them, and the selection's pre-registration uses those values

#### Scenario: Test reserve
- **WHEN** the pilot starts
- **THEN** the blocks reserved for test have already been set aside and no pilot step reads them

### Requirement: Spatial buffer between splits
The system SHALL leave out of training and validation any tile that comes within the largest practical range of the semivariograms of a tile it must be kept apart from, measured edge to edge between footprints: pool tiles near a test tile, and training tiles near a validation tile.

#### Scenario: Training tile near validation
- **WHEN** a training tile's footprint lies within that range of a validation tile's footprint
- **THEN** the tile is used by no step and is counted as left out by the buffer

### Requirement: Segmentation evaluation at label resolution
The system SHALL compare the U-Net with the Random Forest baseline by per-class Dice and macro Dice on the same 30 m pixels, with the Random Forest classifying each 30 m pixel from the mean of its 3x3 block of Sentinel-2 channels.

#### Scenario: Comparison on validation
- **WHEN** both models' selected configurations are scored on validation
- **THEN** the U-Net is reported as better only if its mean macro Dice exceeds the Random Forest's by more than their pooled sample standard deviation over 5 seeds
