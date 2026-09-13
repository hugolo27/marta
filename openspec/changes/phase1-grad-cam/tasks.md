## 1. Grad-CAM core

- [ ] 1.1 Implement Grad-CAM (forward/backward hooks on `SmallCNN`'s last conv block, weighted-activation-sum + ReLU) as a standalone function taking a loaded CNN + a single 33x33x13 patch tensor, returning an 8x8 raw CAM plus its bilinear upsample to 33x33, verified by checking the CAM is non-negative everywhere and non-degenerate (not uniformly zero) on a known bosque patch
- [ ] 1.2 Verify the CAM is attributed to the *predicted* class specifically, not a fixed class, by confirming the CAM changes when computed against a different target class on the same patch
- [ ] 1.3 Refuse Grad-CAM for anything other than the operational CNN (e.g. if passed a Random Forest model or its predictions), per the `grad-cam-interpretability` spec's CNN-only requirement, verified by confirming a clear refusal rather than a silent wrong result
- [ ] 1.4 Implement guided backpropagation (a modified `ReLU` backward hook zeroing negative gradients as well as negative activations) and combine it elementwise with the upsampled Grad-CAM map to produce a sharpened, still class-specific heatmap (Guided Grad-CAM), verified by confirming the sharpened map has finer spatial detail than the raw upsampled Grad-CAM while still concentrating within the same general region

## 2. True-color overlay rendering

- [ ] 2.1 Render the sharpened (Guided Grad-CAM) heatmap as a semi-transparent colormap overlay on the patch's true-color (B4/B3/B2, `/3000` clipped) rendering, reusing `13_visualize_classification_map.py`'s normalization convention, verified by visual inspection that the overlay aligns pixel-for-pixel with the true-color base
- [ ] 2.2 Produce this overlay for at least one example patch per class (bosque/pasto/cultivo) from the existing dataset, verified by visual inspection that each heatmap concentrates on plausible spatial evidence for its class (not spread uniformly or concentrated on an obviously irrelevant corner)

## 3. Explaining a detected temporal transition

- [ ] 3.1 Given a specific AOI pixel (row, col) flagged as a transition in `temporal-change-detection`'s change map, pull that pixel's 33x33 window fresh from Sentinel-2 for both 2019 and 2023 (reusing `s2_utils.build_s2_composite` + `sampleRectangle`, same convention as `18_classify_aoi_temporal.py`), verified by confirming the CNN's prediction on each pulled patch matches the class already recorded in that date's saved classification raster at that pixel
- [ ] 3.2 Produce and render Grad-CAM overlays for both dates' patches at that pixel, side by side, verified by visual inspection against the true-color composites (same hand-picked pixels already used in `19_temporal_change_map.py`'s task 3.3 visual check, so the two checks corroborate each other)

## 4. Write-up

- [ ] 4.1 Document the CAM resolution limitation (8x8 native, upsampled) explicitly wherever Grad-CAM outputs are presented, so it reads as a disclosed property, not a hidden imprecision
