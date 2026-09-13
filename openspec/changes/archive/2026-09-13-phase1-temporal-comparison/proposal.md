## Why

`phase1-classifier` (archived) produces per-date land cover predictions (bosque/pasto/cultivo) from a trained CNN, but nothing yet diffs two dates into a change map. MARTA's core thesis — auditable evidence for carbon-credit verification — needs to answer "did this pixel change between 2019 and 2023, and to what," not just "what is this pixel today." This is also a stated prerequisite for two already-scoped pieces of work: Grad-CAM needs a real detected change to explain rather than a static single-date classification, and Fase 2's carbon estimation needs to know which pixels transitioned and how, to apply a carbon-density delta per transition type.

## What Changes

- Run the operational classifier (CNN, per `phase1-classifier`'s closed decision, `land-cover-classifier` spec) over both the 2019 and 2023 Sentinel-2 composites for the case-study AOI (Corazón Verde del Chaco), producing a dense per-pixel classification raster for each date.
- Diff the two classification rasters pixel-by-pixel into a change map: no-change vs. one of the ecologically meaningful transitions (bosque→pasto, bosque→cultivo, pasto→cultivo, and the reverse directions).
- Report aggregate change statistics over the AOI: hectares per transition type, and a visual change map.
- Cross-check a sample of detected transitions against MapBiomas' own year-over-year transition where available, as a sanity check that the diff reflects real change rather than classifier noise flipping back and forth between adjacent dates.

## Capabilities

### New Capabilities
- `temporal-change-detection`: produces a per-pixel land-cover change map between two dates over the case-study AOI, by running the already-trained classifier on each date and diffing the results, with aggregate transition statistics.

### Modified Capabilities
(none — this consumes `land-cover-classifier`'s trained model as-is, without changing its requirements)

## Impact

- New script(s) under `scripts/` for dense per-date inference over the AOI (distinct from `phase1-classifier`'s held-out evaluation scripts, which score sampled points, not a full raster) and for diffing two classified rasters into a change map.
- Consumes the CNN trained and selected in `phase1-classifier` (`scripts/10_train_cnn.py`'s architecture, `land-cover-classifier` spec's operational-classifier decision) — no retraining.
- Produces the change map and transition statistics that Fase 2 (carbon estimation) and the future Grad-CAM change will both build on.
- Scoped to the case-study AOI only (Corazón Verde del Chaco), not the full training footprint — dense wall-to-wall inference over 24M ha is out of scope and unnecessary; the AOI is the actual audit target (Fase 4).
