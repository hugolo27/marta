## MODIFIED Requirements

### Requirement: Grad-CAM for a single prediction
The system SHALL produce a Seg-Grad-CAM activation heatmap for a prediction of the operational U-Net over a region of one input window (26 channels), using the persisted operational checkpoint: the score explained is the class logit summed over the region's pixels, and the heatmap identifies which spatial regions of the window contributed most to that class there.

#### Scenario: Heatmap produced for a patch
- **WHEN** an input window, a region of its output and a class are available
- **THEN** the system produces an activation map over the window's spatial extent, attributed to that class over that region

#### Scenario: Heatmap depends on the class
- **WHEN** two different classes are explained over the same region of the same window
- **THEN** the two heatmaps differ, verified rather than assumed

### Requirement: Heatmap sharpened via Guided Grad-CAM
The system SHALL sharpen the raw Seg-Grad-CAM heatmap using guided backpropagation before rendering it, combining its class-discriminative localization with guided backpropagation's pixel-level gradient detail at 10 m, rather than presenting the raw heatmap, native to the target layer's resolution, upsampled with no further refinement.

#### Scenario: Sharpened heatmap produced
- **WHEN** a raw heatmap and a guided-backpropagation saliency map are both available for the same window, region and class
- **THEN** the system combines them elementwise into a single sharpened heatmap, used for rendering instead of the raw upsampled heatmap alone

### Requirement: Heatmap rendered over true color
The system SHALL render the sharpened heatmap overlaid on the window's true-color image, with the explained region outlined, not as a bare heatmap, matching the project's existing true-color visualization convention.

#### Scenario: Overlay rendered
- **WHEN** a sharpened heatmap has been produced for a window
- **THEN** the system renders it as a semi-transparent overlay on that window's true-color (B4/B3/B2) rendering, with the region's outline

### Requirement: Explanation of a detected temporal transition
The system SHALL produce heatmaps for both dates at a forest-loss patch of the temporal change map, explaining the whole connected patch with the class recorded for each date, on a window of the classification's own grid, so the evidence behind both halves of a claimed transition is visible, not only the diff result.

#### Scenario: Transition pixel explained
- **WHEN** a cell is labeled forest loss in the 2019/2023 change map
- **THEN** the system produces one heatmap for 2019 and one for 2023 over the cell's loss patch, side by side

#### Scenario: Window matches the map
- **WHEN** a window is pulled to explain a cell
- **THEN** re-predicting every window that covers the cell gives back, within the stored precision, the probabilities recorded in that date's raster

### Requirement: Scoped to the CNN only
The system SHALL only ever produce Grad-CAM evidence for the operational convolutional network (the U-Net), and SHALL NOT attempt to produce it for the Random Forest baseline, since Random Forest has no gradients or spatial activation maps for Grad-CAM to attach to.

#### Scenario: Grad-CAM requested for a non-CNN model
- **WHEN** Grad-CAM evidence is requested for a model other than the operational U-Net
- **THEN** the system refuses rather than fabricating an approximation, and reports that it applies to the U-Net only
