## Why

`phase1-accuracy-assessment` answers one question: does the operational CNN meet the VM0007 bar (forest/non-forest overall accuracy ≥ 90%) in the case-study AOI, and what are the error-adjusted change areas. It does not say where the classifier is unreliable, or why. The evidence so far points to specific weak spots:

- Filadelfia, where the CNN loses to Random Forest on narrow windbreak strips (`docs/METODOLOGIA_PIPELINE.md` 5.3). Under the FAO definition windbreaks wider than 20 m and larger than 0.5 ha are forest, so at MapBiomas' 30 m some of that error may sit in the label or the definition rather than in the model.
- Open or sparse woody vegetation (MapBiomas codes 4 and 45), which may fall outside the Paraguayan forest definition the assessment uses.
- Landscapes unlike the training data, where any accuracy measured elsewhere does not transfer.

This change adds diagnostics that locate and quantify those weak spots. It does not modify the classifier, the change-map configuration or the closed operational decision (CNN). Every item carries its own evaluation criterion, as the rest of the project does.

## What Changes

- **Hard cases, labeled separately.** A probability sample over zones where independent maps disagree (MapBiomas, ESA WorldCover, Dynamic World, JRC GFC2020), interpreted on high-resolution imagery and typed as windbreak, degraded forest, shrubland/other wooded land, pasture with scattered trees, or other. CNN and RF accuracy reported per type.
- **Training-label audit.** A sample of training patches where the independent maps disagree with the MapBiomas label, interpreted to estimate the label-noise rate per class. Measured, not corrected: correcting labels means retraining, which is a separate change with a fresh assessment sample.
- **CNN + RF combination and disagreement.** Temperature-scaled probabilities for both models (fitted on the validation split), a weighted-average ensemble scored against the CNN with a pre-registered criterion on the existing test split and held-out regions, and CNN/RF disagreement as a review flag. Accuracy is reported separately where the models agree and where they disagree.
- **Area of applicability** (Meyer and Pebesma, 2021) for the CNN, over the AOI and the held-out regions, with accuracy reported inside and outside it.
- **Accuracy by landscape type**: forest/non-forest accuracy broken down by fragmentation class and ecoregion, using the interpreted reference points from `phase1-accuracy-assessment`.

## Capabilities

### New Capabilities
- `classifier-reliability`: diagnostics that locate where the operational classifier's per-date forest/non-forest output is unreliable (hard-case types, label noise, model disagreement, area of applicability, landscape type), without changing the classifier or its outputs.

### Modified Capabilities
(none. `land-cover-classifier`, `temporal-change-detection` and `map-accuracy-assessment` keep their requirements; this change evaluates their outputs.)

## Non-goals

- Changing the operational classifier, its training data, or the change-map post-processing. If a diagnostic shows a fix is needed, it becomes a separate change that must be re-assessed on a newly drawn reference sample (`map-accuracy-assessment`: "Assessment sample is not reused for tuning").
- Correcting training labels where the model disagrees with them. That is circular and inflates accuracy; the audit samples where independent maps disagree, not where the model does.
- Metrics and change-detection items already covered: change-class user's/producer's accuracy and error-adjusted areas (`phase1-accuracy-assessment`), probabilities instead of hard classes and the 0.5 ha minimum mapping unit (`phase1-change-detection-hardening`).
- Future work, mentioned in the thesis only: semantic segmentation instead of patch classification, seasonal or time-series inputs, foundation-model embeddings, more classes and harmonized legends, active learning, selective or conformal prediction, per-property verification sampling.

## Impact

- **Depends on `phase1-accuracy-assessment`** interpretation (tasks 4.1-4.3 and 6.2) for the items that use its reference points (agreement/disagreement accuracy, accuracy inside/outside the area of applicability, accuracy by landscape). The ensemble comparison and the area of applicability itself only need existing data. Does not block Fase 2.
- **Manual effort:** ~200 hard-case points and ~100 training patches interpreted in Google Earth Pro, plus a 10% blind repeat. Estimated at ~3-4 hours, not measured.
- **New scripts** numbered after `30_assess_heldout_accuracy.py`, logged to MLflow under experiment `phase1-reliability`. Data under `data/study_area/reliability/`.
- **GEE:** WorldCover, Dynamic World and JRC GFC2020 sampled over the AOI, held-out regions and training points; RESOLVE Ecoregions 2017 for the ecoregion split; dense RF predictions over the AOI from the existing composites.
- Updates `docs/METODOLOGIA_PIPELINE.md` (new results subsection) and the thesis results chapter.
