## Why

Fase 1 answers "where did land cover change?" (CNN + Grad-CAM). Its change detection was hardened against Hansen and MapBiomas (`phase1-change-detection-hardening`), and its final test against interpreted reference points (`phase1-accuracy-assessment`) produces the error-adjusted change areas that this change consumes. The carbon market trades in tonnes of CO2e, not hectares, so Fase 2 has to answer "how much carbon does that change represent?" (see `docs/FOUNDATION.md`, point 6, and `docs/METODOLOGIA_PIPELINE.md`, section 3.2).

The currently documented approach is a single-variable calibration: canopy height inferred with the pretrained ETH Global Canopy Height model (Lang et al., 2023), converted to aboveground biomass density with a log-log power law fitted against GEDI L4A (`AGBD = a * H^b`), then to CO2e with IPCC factors. `FOUNDATION.md` already flags the weak point of that chain: the ETH model reports a positive bias in low canopies (roughly 2 m between 5 and 20 m), which is exactly the height range of most Chaco dry forest. Height alone also misses wood density and stem volume, which vary strongly in the Chaco (e.g. quebracho).

Synthetic Aperture Radar (SAR) measures the woody structure (stems and branches) rather than the leaf surface seen by the optical sensor. It is open data, available in Google Earth Engine (already the project's processing platform), insensitive to clouds and much less affected by the seasonal leaf loss of the deciduous Chaco forest. In low-biomass forest like the Chaco the L-band signal stays below its known saturation range, which is where SAR-based biomass estimation works best.

This change keeps the documented approach as the **baseline** and adds a **SAR-augmented candidate**, evaluated with the same pre-registered "baseline vs. candidate" posture already used for Random Forest vs. CNN in Fase 1 and for CA-Markov vs. deep learning in Fase 5.

## What Changes

- **Canopy height by inference** (no retraining): run the ETH model per Sentinel-2 L2A scene for each needed year and aggregate the per-scene predictions with the model's own inverse-variance weighting, as in the original deployment, filtering with the model's uncertainty layer.
- **GEDI L4A reference sample**: quality-filtered footprints over the sampling footprint (the three Región Occidental departments, minus the three held-out regions), each paired with height and SAR features from imagery of its own shot year, and excluding footprints on pixels that changed class within that year.
- **Baseline**: log-log power law `AGBD = a * H^b` fitted against GEDI L4A, as documented today.
- **Candidate**: height plus SAR features, as:
  - Sentinel-1 C-band (VV, VH, VH/VV ratio; dry-season median and intra-annual variability), from `COPERNICUS/S1_GRD`.
  - ALOS-2 PALSAR-2 L-band (HH, HV, HV/HH), from the JAXA collections in Earth Engine (availability for 2019 and 2023 checked 2026-10-03, see design).
  - Model: a multivariate log-linear regression (interpretable by its coefficients) and a Random Forest regressor, both scored against the baseline.
- **Ablation study**: H only; H + S1; H + PALSAR-2; H + S1 + PALSAR-2; SAR only (no H). Answers which open data combination estimates biomass best in Chaco dry forest, and whether the ETH height is needed at all once SAR is present.
- **Pre-registered comparison criterion**, fixed before looking at results (see design.md).
- **Carbon conversion**: `AGB_total = AGBD * (1 + R)`, `C = AGB_total * 0.47`, `CO2e = C * 44/12`, with R re-checked for the correct IPCC forest type (see design.md, open questions).
- **Uncertainty propagation** (Monte Carlo) from height uncertainty, regression residuals, conversion factors and the change-area confidence interval to a CO2e interval, consistent with the "auditable" goal of the project.
- **Outputs**: per-pixel CO2e density maps for 2019 and 2023, observed ΔCO2e per change category in the case-study AOI computed on the error-adjusted areas from `phase1-accuracy-assessment` (never on raw mapped pixel counts), and a table of carbon-density deltas per pair of land cover classes (consumed by Fase 5, `phase5-predictive-model`).
- **Independent validation** against open products not used for calibration (ESA CCI Biomass, Paraguay's FREL emission factors for dry forest), documented as a comparison, not as ground truth.

## Capabilities

### New Capabilities
- `carbon-estimation`: estimates per-pixel aboveground and belowground biomass, carbon and CO2e density, and observed ΔCO2e over assessed change areas, via a height-only baseline evaluated against a SAR-augmented candidate, with propagated uncertainty.

### Modified Capabilities
(none. Fase 1 capabilities are consumed as-is: `temporal-change-detection` provides the forest/non-forest change map, `map-accuracy-assessment` (from `phase1-accuracy-assessment`, not yet archived) provides the error-adjusted change areas, `training-dataset` provides the composite-building code and the held-out regions.)

## Non-goals

- Reopening Fase 1. SAR as an additional classifier input (e.g. to reduce pasto/cultivo confusion) may be proposed later as a separate, optional change.
- Retraining or fine-tuning the ETH canopy height model.
- NISAR or ESA BIOMASS data: both missions started in 2025 and do not cover the 2019/2023 periods. Listed as future work.
- Own field data collection, drones, or non-open datasets (the project uses only open data).
- Carbon pools beyond above and belowground biomass (deadwood, litter, soil), unchanged from `FOUNDATION.md`.
- Additionality or baseline assessment of the REDD+ project.

## Impact

- **Depends on `phase1-accuracy-assessment`** (task 5.4, `aoi_change_areas.json`) for the ΔCO2e step only. Height inference, the GEDI sample, SAR features, the calibration comparison and the density maps do not depend on it and can run first.
- New data sources in the pipeline: Sentinel-1 GRD and ALOS-2 PALSAR-2 (both open, both in Earth Engine), ETH model code (MIT) and weights, ESA CCI Biomass for validation.
- New scripts under `scripts/` following the existing numbering, plus a shared `s1_utils.py` mirroring `s2_utils.py`.
- Updates `docs/METODOLOGIA_PIPELINE.md` (sections 1, 3.2, 6, and a new results section), `docs/FOUNDATION.md` (point 6), and the thesis chapters.
- Enables `phase5-predictive-model` task 7.1 (carbon-density deltas per class pair).
