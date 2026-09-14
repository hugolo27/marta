## Purpose

Produces a Grad-CAM activation heatmap for a single CNN prediction, so an auditor can see which part of a patch drove a classification instead of trusting a bare class label.

## ADDED Requirements

### Requirement: Grad-CAM for a single prediction
The system SHALL produce a Grad-CAM activation heatmap for any single CNN prediction on a 33x33x13 patch, using the persisted operational CNN checkpoint, identifying which spatial regions of the patch contributed most to the predicted class.

#### Scenario: Heatmap produced for a patch
- **WHEN** a 33x33x13 patch and the CNN's predicted class for it are available
- **THEN** the system produces a per-pixel activation map over the patch's spatial extent, attributed to that predicted class

### Requirement: Heatmap sharpened via Guided Grad-CAM
The system SHALL sharpen the raw Grad-CAM heatmap using guided backpropagation before rendering it, combining Grad-CAM's class-discriminative localization with guided backpropagation's pixel-level gradient detail, rather than presenting the raw 8x8-native heatmap upsampled with no further refinement.

#### Scenario: Sharpened heatmap produced
- **WHEN** a raw Grad-CAM heatmap and a guided-backpropagation saliency map are both available for the same patch and predicted class
- **THEN** the system combines them elementwise into a single sharpened heatmap, used for rendering instead of the raw upsampled Grad-CAM alone

### Requirement: Heatmap rendered over true color
The system SHALL render the sharpened Grad-CAM heatmap overlaid on the patch's true-color image, not as a bare heatmap, matching the project's existing true-color visualization convention.

#### Scenario: Overlay rendered
- **WHEN** a sharpened Grad-CAM heatmap has been produced for a patch
- **THEN** the system renders it as a semi-transparent overlay on that patch's true-color (B4/B3/B2) rendering

### Requirement: Explanation of a detected temporal transition
The system SHALL produce Grad-CAM heatmaps for both dates' predictions at a pixel flagged as a transition in the temporal change map, so the evidence behind both halves of a claimed transition is visible, not only the diff result.

#### Scenario: Transition pixel explained
- **WHEN** a pixel is labeled as a specific transition in the 2019/2023 change map
- **THEN** the system produces one Grad-CAM heatmap for the 2019 prediction and one for the 2023 prediction at that pixel's patch, so both can be inspected side by side

### Requirement: Scoped to the CNN only
The system SHALL only ever produce Grad-CAM evidence for the CNN, and SHALL NOT attempt to produce it for the Random Forest baseline, since Random Forest has no gradients or spatial activation maps for Grad-CAM to attach to.

#### Scenario: Grad-CAM requested for a non-CNN model
- **WHEN** Grad-CAM evidence is requested for a prediction made by a model other than the operational CNN
- **THEN** the system refuses rather than fabricating an approximation, and reports that Grad-CAM is CNN-only by construction
