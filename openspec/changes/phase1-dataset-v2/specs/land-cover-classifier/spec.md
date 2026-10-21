## ADDED Requirements

### Requirement: Variant selection on the validation split
The system SHALL use a 3x3 input for the operational CNN and choose its season (dry or dry+wet), and the Random Forest's season, on the validation split only, by a rule pre-registered before any variant is scored, keeping the simplest variant unless another beats it beyond seed noise.

#### Scenario: A more complex variant beats the default beyond noise
- **WHEN** the best variant's mean validation macro-F1 exceeds the default's by more than their pooled sample standard deviation
- **THEN** the best variant becomes operational and every downstream product that depends on it is regenerated

#### Scenario: No variant beats the default beyond noise
- **WHEN** no variant exceeds the default (3x3 dry for the CNN, dry for the Random Forest) by more than their pooled sample standard deviation
- **THEN** the default stays operational

#### Scenario: Selected hyperparameter on the edge of the grid
- **WHEN** a selected value lies on the edge of its grid axis
- **THEN** that axis is extended by one step and the selection is redone once before the variant comparison

### Requirement: CNN input normalization
The system SHALL standardize every CNN input channel with the mean and standard deviation of that channel over the training split only, and SHALL store those statistics with the model weights so every caller applies the same scaling.

#### Scenario: A saved model is used outside training
- **WHEN** a saved CNN classifies held-out regions, the AOI, or is explained with Grad-CAM
- **THEN** it scales raw inputs with the training-split statistics stored in the checkpoint, without the caller computing them
