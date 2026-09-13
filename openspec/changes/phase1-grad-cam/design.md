## Context

`SmallCNN` (`scripts/10_train_cnn.py`) is 3 conv blocks (32→64→128 filters, the first two followed by `MaxPool2d(2)`) feeding `AdaptiveAvgPool2d(1)` then a `Linear` classifier. On a 33x33 input, the last conv block's feature map is 128 channels at 8x8 spatial resolution — that's the natural Grad-CAM target layer (last conv output before global pooling), same as the architecture Grad-CAM was originally designed for.

Two prior changes already built what this one consumes: `phase1-classifier` trained and selected the CNN as operational classifier (`land-cover-classifier` spec) and `phase1-temporal-comparison` persisted a reusable checkpoint (`scripts/10_train_cnn.py`'s `save_checkpoint`/`load_checkpoint`) plus dense per-date classification rasters and a named-transition change map over the case-study AOI (`scripts/18_classify_aoi_temporal.py`, `19_temporal_change_map.py`).

## Goals / Non-Goals

**Goals:**
- Grad-CAM for any single 33x33x13 patch + predicted class, using the persisted checkpoint (no retraining).
- A true-color overlay renderer, reused for both standalone patches and transition pixels.
- Explain both halves (2019 prediction, 2023 prediction) of a change-map transition pixel, by pulling that pixel's own 33x33 window for each date directly from Sentinel-2 rather than requiring `18_classify_aoi_temporal.py` to have saved every patch it ever classified (it never did — it discards patches after producing the class raster).

**Non-Goals:**
- No Grad-CAM for Random Forest — structurally impossible (no gradients, no spatial activation map), not a missing feature to add later.
- No new metric for "heatmap quality" or automated evaluation of whether the heatmap is "correct" — Grad-CAM here is auditor-facing evidence, not a component being benchmarked. Qualitative inspection (does the heatmap land on the part of the patch that plausibly drove the class) is the acceptance bar, same spirit as `phase1-classifier`'s and `phase1-temporal-comparison`'s visual sanity checks.
- No re-litigating the operational-classifier decision (`land-cover-classifier`, closed) or the change map's transition semantics (`temporal-change-detection`, closed) — this only adds an explanation layer on top of both.

## Decisions

**Hook the last conv block's output (128 channels, 8x8 spatial) as the Grad-CAM target layer.** It's the last spatial feature map before `AdaptiveAvgPool2d(1)` collapses everything — exactly the layer Grad-CAM targets by convention (deepest layer that still has spatial structure). Consequence, stated up front rather than discovered later: the raw CAM is only 8x8, upsampled (bilinear) to 33x33 for the overlay — coarse by construction, given how aggressively this small architecture pools. This is disclosed as a property of the heatmap's resolution, not hidden.

**Standalone-patch Grad-CAM reads existing dataset patches directly; transition-pixel Grad-CAM re-pulls from Sentinel-2 per pixel.** The dataset's `.npy` patches (`dataset_loader.py`) already exist for the first case — no new data path needed. For a flagged transition pixel, `18_classify_aoi_temporal.py` never persisted per-pixel patches (only the final class raster, by design — persisting a patch per pixel over 3.36M pixels would be enormous), so explaining a specific transition pixel means pulling that one pixel's 33x33 window fresh from GEE for both 2019 and 2023 (same `s2_utils.build_s2_composite` + `sampleRectangle` pattern already used throughout the AOI scripts) — cheap for a handful of hand-picked pixels, not something meant to run over every transition pixel at scale.

**Reuse the true-color rendering convention (`grid[..., [3,2,1]] / 3000`, clipped to [0,1]) from `13_visualize_classification_map.py` for the overlay base**, rather than inventing a new normalization. The heatmap itself uses a standard diverging/hot colormap at partial alpha over that same true-color image.

**Grad-CAM computed via manual forward/backward hooks on `SmallCNN`, not a library dependency.** The architecture is 3 conv blocks — implementing the standard Grad-CAM formula (global-average-pooled gradients as channel weights, ReLU on the weighted activation sum) directly is a few lines and avoids pulling in a new dependency (e.g. `pytorch-grad-cam`) for something this small, matching the project's existing preference for homegrown code over new dependencies for simple, well-understood algorithms (`SmallCNN` itself over a pretrained backbone, same rationale).

**Sharpen with Guided Grad-CAM rather than shipping the raw 8x8-upsampled heatmap.** Guided backpropagation runs a backward pass through the network with a modified ReLU (zeroing negative gradients as well as negative activations), producing a pixel-level saliency map at the input's own 33x33 resolution — but on its own it isn't class-discriminative (it highlights salient input detail regardless of which class is being explained). Elementwise-multiplying it with the (upsampled) Grad-CAM map keeps only the fine detail inside the region Grad-CAM already identified as relevant to the predicted class — this is exactly the "Guided Grad-CAM" combination from the original paper (Selvaraju et al. 2017), not a novel technique. Implemented as a second, small hook (overriding `ReLU`'s backward pass) alongside the existing forward/backward hooks — no new dependency, no retraining, same homegrown-over-library rationale as the base Grad-CAM decision above.

## Risks / Trade-offs

- **[Risk] An 8x8-native heatmap upsampled to 33x33 is inherently blocky/coarse — it will not pinpoint sub-pixel-cluster detail within a patch.** Accepted: this is a property of the architecture's spatial resolution at the target layer, not a Grad-CAM implementation bug, and is disclosed as such rather than presented as fine-grained.
- **[Risk] Re-pulling Sentinel-2 for individual transition pixels means Grad-CAM explanations for the change map are only ever produced for hand-picked pixels, not the whole AOI.** Accepted and intentional (per design's Non-Goals) — Grad-CAM here is auditor-facing spot-check evidence for specific claims, not a wall-to-wall artifact; the change map's own aggregate statistics (`temporal-change-detection`) already cover the wall-to-wall view.
- **[Trade-off] Manual hook-based Grad-CAM instead of a library** means less battle-tested edge-case handling (e.g. multi-target-layer CAM variants) than a dedicated library would offer, in exchange for a small, auditable implementation consistent with the project's existing "small, homegrown, understood end-to-end" preference for its own CNN.
- **[Risk] Guided backpropagation alone is known to be weakly class-discriminative — it can highlight the same edges regardless of predicted class.** Mitigation: it is never rendered alone, only multiplied with Grad-CAM's class-specific localization, which is the entire point of the "guided" combination rather than guided backprop by itself.
