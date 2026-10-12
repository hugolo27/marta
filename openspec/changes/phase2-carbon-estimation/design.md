## Context

See `proposal.md` (Why). This design covers how the height-only baseline and the SAR-augmented candidate are built, how the GEDI L4A reference sample is assembled, how both are compared without bias, and how the result becomes a CO2e figure with an uncertainty interval.

It consumes, from Fase 1:
- `scripts/s2_utils.py` (Sentinel-2 L2A from `COPERNICUS/S2_SR_HARMONIZED`, SCL masking, multi-UTM handling).
- The sampling footprint and the three held-out regions (Filadelfia, Bahía Negra, Pozo Colorado).
- The hardened forest/non-forest change map over the case-study AOI (`change_map_2019_2023_fnf.npy`, `temporal-change-detection`).
- The error-adjusted change areas with confidence intervals (`data/study_area/accuracy_assessment/aoi_change_areas.json`, `phase1-accuracy-assessment` task 5.4). Not available yet; only the ΔCO2e step (D8) waits for it.

## Feasibility checks (2026-10-03, read-only)

- **ETH model.** Code is public (MIT) and the weights download works (`trained_models_GLOBAL_GEDI_2019_2020.zip`, 155 MB, 5 models each with a fine-tuned `FT_Lm_SRCB` variant). From `args.json` and `train_input_mean.npy`: 15 input channels = the 12 Sentinel-2 L2A bands in the order B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12 as raw digital numbers (training means ~170-1,000), plus latitude and sin/cos of longitude, standardized with the stored training mean/std. `S2_BANDS` in `s2_utils.py` already has that order. The original code reads `.SAFE` zips and applies no processing-baseline offset correction, so 2022+ scenes read that way would be shifted by +1,000; `S2_SR_HARMONIZED` already removes that shift. Deployment is per scene (cloud-probability mask at 5%, SCL classes 8, 9, 11 and 6 masked), and per-scene predictions are merged by inverse-variance weighted mean. Not yet run on a test tile.
- **Sentinel-1 over the AOI.** `COPERNICUS/S1_GRD`, IW, VV+VH: a single relative orbit (141, descending). 2019: 60 scenes in the year (S1A 29, S1B 31), 20 in June-September. 2023: 29 scenes (S1A only), 8 in June-September.
- **PALSAR-2.** `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` (25 m annual mosaic, HH/HV) has one image over the AOI for each year 2015-2024, including 2019 and 2023. `JAXA/ALOS/PALSAR-2/Level2_2/ScanSAR` has 29 scenes in 2019 and 38 in 2023. The older `JAXA/ALOS/PALSAR/YEARLY/SAR` stops at 2020 and is not used.
- **GEDI L4A after March 2023.** CMR search, `GEDI_L4A_AGB_Density_V3_2508`, granules whose bounding box intersects the AOI: 49 in total. The last before the pause is February 2023. There are none from March 2023 to June 2024, and 10 from July 2024 to July 2025. Footprints actually inside the polygon were not counted (that needs reading the granules, task 2.1). Earth Engine also has `LARSE/GEDI/GEDI04_A_002_MONTHLY` (rasterized, version 2) up to 2025-07; the project keeps the V3 footprint table used by `scripts/02_gedi_feasibility_check.py`.

## Goals / Non-Goals

**Goals:**
- A per-pixel CO2e density estimate for 2019 and 2023, with an uncertainty interval, over the case-study AOI and the held-out regions.
- An honest, pre-registered test of whether SAR improves on the height-only calibration in Chaco dry forest.
- An ablation that tells which open data inputs actually carry the signal.
- Every number traceable to data, parameters and code version (the project's auditability argument).

**Non-Goals:** see `proposal.md` (Non-goals).

## Decisions

### D1. Map periods: 2019 and 2023, same as Fase 1
Carbon density maps are produced for the same two periods the classifier uses, so ΔCO2e lines up with the Fase 1 change categories. The calibration sample (D3) uses footprints from any year with GEDI data, each paired with its own year's imagery.

### D2. Canopy height by inference per scene, not the static 2020 map
Run the ETH model (public code and weights) on individual Sentinel-2 scenes from `S2_SR_HARMONIZED`, exported with the 12 bands as raw digital numbers plus the latitude/longitude channels, and merge per-scene predictions with the inverse-variance weighted mean, as the original deployment does. A median composite would be an input the model was never trained or validated on, so it is not the default. Task 3.2 measures the difference between per-scene aggregation and running on the Fase 1 composite over stable forest, and only if it is negligible may the composite be used.

Predictions whose model-reported standard deviation exceeds a threshold fixed in task 3.3 are masked and reported, not silently kept. The published 2020 map is used only as a sanity check (task 3.4).

Season matters: the Chaco forest is largely deciduous and an optical model may read less canopy in the dry season. Task 3.2 also compares dry-season and wet-season scenes over stable forest and fixes the scene window with that evidence.

### D3. GEDI L4A reference sample over the sampling footprint, not only the AOI
`METODOLOGIA_PIPELINE.md` 3.2 says the calibration is fitted on the AOI's 3,823 footprints, while `FOUNDATION.md` says the GEDI calibration sample is drawn from a footprint wider than the AOI. This design takes the `FOUNDATION.md` position (wider footprint, minus the three held-out regions), because:
- a model fitted on ~20,000 ha of mostly continuous forest will not see the full range of Chaco structure;
- it keeps the held-out regions available as an honest generalization test, the same way Fase 1 used them.

To be confirmed with the tutor (task 1.1) and both docs aligned afterwards.

Footprint filters and pairing:
- `l4a_quality_flag_rel3 == 1` (same flag as the existing feasibility check).
- Same-year pairing: each footprint gets height (D2) and SAR features (D4) from imagery of its own shot year. The calibration is a relation between structure and biomass, not a per-period product, so pooling years is valid as long as each pair is contemporaneous. This also uses the 2024-2025 footprints, since GEDI has no data over the AOI between March 2023 and June 2024.
- Stability within the year: exclude footprints on pixels with Hansen loss in the shot year or the year before, or whose MapBiomas class differs between those two years (for shot years past the last MapBiomas collection year, Hansen only). The Fase 1 change map only covers the AOI and the change-development area, so it cannot be the filter over the whole footprint.
- Geolocation: GEDI footprints are ~25 m in diameter with ~10 m geolocation error, so every predictor is extracted as a mean over a 12.5 m buffer, not a single pixel.

### D4. SAR features
**Sentinel-1** (`COPERNICUS/S1_GRD`, IW mode, VV + VH, sigma0 in dB; already calibrated, thermal-noise corrected and orthorectified in Earth Engine; the Chaco is flat, so radiometric terrain flattening is not needed):
- Dry-season median VV, VH and VH/VV ratio. Dry season preferred because rain and flooding (notably in Alto Paraguay, where the AOI sits) change soil moisture and backscatter.
- Intra-annual standard deviation of VH (captures seasonal dynamics).
- Descending orbit only. Over the AOI it is the only geometry available (relative orbit 141); elsewhere in the footprint the same direction is kept so features are comparable.
- Multi-temporal median also acts as speckle filter; no extra spatial filter unless task 4.3 shows it is needed.
- Sentinel-1B stopped operating in December 2021: over the AOI, June-September has 20 scenes in 2019 and 8 in 2023. The number of acquisitions per pixel and period is recorded and reported, and task 4.3 checks that 2019 features do not shift when subsampled to 2023 density. If 8 dry-season scenes prove too few, the window is widened symmetrically for both periods, not for 2023 alone.

**ALOS-2 PALSAR-2** (L-band, HH + HV): annual mosaic values from `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` and the HV/HH ratio. Both 2019 and 2023 exist; footprints shot in 2025 have no annual mosaic, so they enter the PALSAR-2 ablation rows only if ScanSAR (`Level2_2/ScanSAR`) features are built for them, otherwise they are excluded from those rows and counted.

### D5. Working grid
Predictors come at 10 m (height, S2), ~20 m effective (S1) and 25 m (PALSAR-2). Calibration is done at footprint level (buffer means, D3). Maps are produced on the Sentinel-2 10 m grid for consistency with Fase 1 change pixels, with SAR bilinearly resampled; this is stated as an approximation, since SAR adds no real 10 m detail.

### D6. Models
- **Baseline:** `ln(AGBD) = ln(a) + b * ln(H)`, OLS, with the standard log-bias correction (Baskerville) when back-transforming.
- **Candidate A (interpretable):** multivariate log-linear regression with ln(H) plus SAR features. Coefficients are the explanation, in line with the project's interpretability argument.
- **Candidate B (flexible):** Random Forest regressor on the same features. Feature importances reported.
- **Ablation:** each feature set in `proposal.md` is fitted with Candidate A and B.

### D7. Pre-registered comparison (fixed before looking at results)
- Validation: spatial block cross-validation (~2 km blocks, same approach as Fase 1) over the calibration sample, 5 repetitions with different block assignments; plus evaluation on each held-out region, never used in fitting.
- Metrics: RMSE and bias in Mg/ha (back-transformed), R², and RMSE within the low-biomass stratum (AGBD below the sample median), where the ETH bias is documented.
- A candidate is considered better than the baseline only if its mean RMSE is lower by more than one combined standard deviation of both distributions **and** its low-stratum bias is not worse. Otherwise the baseline stays, and that is reported as a valid finding.
- If Candidate A and B tie, A is preferred for interpretability.

### D8. Carbon conversion, ΔCO2e and uncertainty
- `AGB_total = AGBD * (1 + R)`, `C = AGB_total * 0.47` (IPCC 2006), `CO2e = C * 44/12`.
- R: see Open Questions; the value used and its source table are recorded in the run config.
- **ΔCO2e on assessed areas.** For each change category of the forest/non-forest map (loss, gain): `ΔCO2e = A_adj * d`, where `A_adj` is the error-adjusted area from `aoi_change_areas.json` and `d` is the mean per-hectare density change (`CO2e_2019 - CO2e_2023`) over the mapped pixels of that category. The pixel-sum over mapped pixels is reported next to it as a labeled secondary value, never as the headline figure (spec `map-accuracy-assessment`: "Downstream area figures are error-adjusted").
- `d` is cross-checked against a stock-difference value: mean CO2e density of stable forest minus mean density of stable non-forest, both from the 2019 map. If they differ by more than their combined uncertainty, both are reported and the difference is discussed; mapped change pixels include commission errors, which dilute `d`.
- Monte Carlo (e.g. 1,000 draws): height from its model uncertainty, regression residual error, R and carbon fraction within their published ranges, and `A_adj` from its confidence interval (normal with the reported standard error). Output: mean and 90% interval, for the density maps and for each ΔCO2e.
- The AOI has very little real loss in 2019-2023 (Hansen: 0.1 ha), so a ΔCO2e near zero with an interval that includes zero is an expected, valid outcome, not a failure of the method.
- **Class-pair deltas for Fase 5.** The forest/non-forest map does not support area figures for named transitions, so the table for `phase5-predictive-model` is built from class means instead: mean CO2e density per MapBiomas class over stable footprints of the calibration sample (predicted with the operational calibration), and `delta(A → B) = mean(A) - mean(B)` with its interval. Cultivo does not occur in the AOI, which is why the footprint-wide sample is used. A class with too few footprints is reported as unavailable.

### D9. Independent validation and circularity
The ETH model was trained on GEDI heights (RH98), and GEDI L4A biomass is also derived from GEDI waveform metrics, so height and label are not independent; cross-validation against GEDI alone can look better than reality. Mitigation:
- Report results on held-out regions (spatial independence).
- Compare aggregated estimates against open products not used in fitting: ESA CCI Biomass (annual maps) and the dry-forest emission factors in Paraguay's FREL submitted to the UNFCCC.
- Document the circularity explicitly as a limitation.

### D10. Reproducibility
All parameters (periods, scene windows, filters, thresholds, R, seeds) live in one config file versioned with the code; each run logs data versions, parameters and metrics to MLflow, as Fase 1 already does.

## Risks / Trade-offs

- **[Risk] Uneven Sentinel-1 density between 2019 and 2023** (loss of S1B; 20 vs. 8 dry-season scenes over the AOI). Mitigation: acquisition counts reported; subsampling check (task 4.3); symmetric window widening if needed.
- **[Risk] Per-scene ETH inference is heavier than one composite** (several scenes per year, exported with all 12 bands). Mitigation: inference only over the AOI, the held-out regions and small chips around footprints, not the whole footprint; the scene count per year is capped and recorded.
- **[Risk] Soil moisture and flooding confound SAR.** Mitigation: dry-season features; flag pixels in seasonally flooded zones.
- **[Risk] GEDI/ETH circularity inflates metrics.** Mitigation: D9.
- **[Risk] Few GEDI footprints on stable non-forest classes once filters apply.** Mitigation: report counts per class; if too few, fix non-forest carbon density from IPCC defaults and state it.
- **[Risk] `aoi_change_areas.json` arrives late or the accuracy gate fails.** Mitigation: everything except D8's ΔCO2e runs without it. If the gate fails, ΔCO2e is still computed on the error-adjusted areas and reported together with the failed gate.
- **[Trade-off] More inputs mean more preprocessing and a longer write-up.** Accepted because the ablation is itself a concrete, measurable contribution.

## Open Questions

- **Root-to-shoot ratio R.** `FOUNDATION.md` uses 0.20 to 0.24, which in IPCC 2006 (Vol. 4, Table 4.4) correspond to tropical moist deciduous forest. For tropical/subtropical dry forest the same table lists higher values (0.56 for AGB below 20 t/ha, 0.28 above). Confirm which forest type applies to the Chaco (and whether the 2019 Refinement or Paraguay's FREL gives a better value) before fixing R. This changes the belowground share of the estimate substantially.
- Calibration footprint: AOI only vs. sampling footprint (D3), to confirm with the tutor.
- Whether to also report GEDI L4B (1 km gridded) as a coarse comparison, given it shares the circularity in D9.
