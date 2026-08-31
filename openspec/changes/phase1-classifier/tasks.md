## 1. Data loading

- [ ] 1.1 Load the dataset manifest and verify real training volume is present (not the 90-patch proof sample), verified by checking per-class/per-split counts against the expected ~1,200 total
- [ ] 1.2 Build a per-pixel feature table (13 channels: 12 bands + NDVI, taken from each patch's center pixel) for the Random Forest, verified by checking row count matches patch count and no NaNs are present
- [ ] 1.3 Build a patch tensor loader for the CNN (33x33x13 arrays + labels, batched), verified by loading one batch and checking shape/dtype

## 2. Random Forest baseline

- [ ] 2.1 Train the Random Forest on the per-pixel feature table (train split), verified by confirming it fits without error and reports feature importances
- [ ] 2.2 Evaluate on the test split: accuracy, per-class IoU/Dice, confusion matrix, verified by producing all three outputs

## 3. CNN candidate

- [ ] 3.1 Define the CNN architecture (small, custom, documented layer-by-layer), verified by confirming the model builds and a forward pass on one batch produces the expected output shape (3 classes)
- [ ] 3.2 Train on the patch tensors (train split, validate on val split), verified by confirming loss decreases and training completes without error
- [ ] 3.3 Evaluate on the test split with the same metrics as the Random Forest baseline, verified by producing all three outputs in the same format for direct comparison

## 4. Baseline vs. candidate comparison

- [ ] 4.1 Run both models across multiple seeds (design.md: decide the outperformance margin before looking at results), verified by producing a distribution of test-set metrics per model, not a single run each
- [ ] 4.2 Determine and document which model is selected as the classifier going forward, verified by a written comparison (spec: candidate outperforms vs. does not outperform) with the metrics as evidence, either outcome accepted as valid

## 5. Cross-region generalization and WorldCover cross-check

- [ ] 5.1 Run the selected classifier over the Filadelfia held-out sub-region, verified by producing predictions covering that region
- [ ] 5.2 Compute accuracy/agreement metrics for the held-out sub-region and report them alongside the case-study AOI's test-set metrics, verified by a side-by-side comparison table
- [ ] 5.3 Cross-check the held-out region's predictions against ESA WorldCover, verified by producing per-class agreement, with an explicit note that the "pasto" comparison is a weaker proxy than "bosque"/"cultivo"

## 6. Write-up

- [ ] 6.1 Document the final model choice, evaluation metrics, and generalization results in the TFM document sections covering results, cross-referencing `docs/METODOLOGIA_PIPELINE.md` section 5
