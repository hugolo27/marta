## 1. Scope confirmation

- [ ] 1.1 Confirm with the tutor: SAR-augmented candidate in scope, calibration over the sampling footprint instead of AOI only (design D3), and the forest type used to pick R (design, Open Questions). Record in `research_docs/BITACORA.md`
- [ ] 1.2 Write the pre-registered comparison criterion (design D7) into `docs/METODOLOGIA_PIPELINE.md` before any model is fitted, verified by a commit that precedes the first results commit

## 2. GEDI L4A reference sample

- [ ] 2.1 Extend `scripts/02_gedi_feasibility_check.py` to count quality footprints inside the AOI per year, including 2024-2025, and record the result. Granule-level check done 2026-10-03 (design, Feasibility checks): no AOI granules from March 2023 to June 2024, 10 from July 2024 to July 2025
- [ ] 2.2 Download and filter footprints over the sampling footprint minus the three held-out regions (quality flag), storing them as a versioned parquet table with shot date, AGBD, AGBD standard error and coordinates
- [ ] 2.3 Apply the within-year stability filter (design D3) using Hansen loss year and MapBiomas per-year classes, verified by a filtering report with counts removed per reason
- [ ] 2.4 Report footprint counts per MapBiomas class and per shot year, verified that each class used in the class-pair deltas has enough footprints, or document the fallback (design, Risks)

## 3. Canopy height by inference

- [ ] 3.1 Obtain the ETH model code and weights, export one 2020 Sentinel-2 scene from `S2_SR_HARMONIZED` in the model's input format (12 bands as raw DN in B01-B12 order without B10, latitude and sin/cos longitude channels, training mean/std standardization; design, Feasibility checks), and verify the prediction reproduces the published 2020 map on that tile within its reported uncertainty
- [ ] 3.2 Over stable forest pixels, compare (a) dry-season vs. wet-season scenes and (b) per-scene inverse-variance aggregation vs. inference on the Fase 1 median composite, and fix the scene window and aggregation with the result (spec: "Season or input aggregation affects height")
- [ ] 3.3 Run inference for 2019 and 2023 over the AOI and the held-out regions, and for each footprint's shot year at the footprint locations; fix and document the uncertainty threshold, and report the masked fraction
- [ ] 3.4 Sanity check: compare the inferred 2019/2023 heights against the published 2020 map over stable forest, verified by a difference histogram in the write-up

## 4. SAR features

- [ ] 4.1 Add `scripts/s1_utils.py` mirroring `s2_utils.py`: Sentinel-1 GRD filtering (IW, VV+VH, descending orbit), dry-season window, median, VH/VV ratio, intra-annual VH std, acquisition count band
- [ ] 4.2 Build Sentinel-1 feature composites for 2019 and 2023 and for each footprint shot year, verified by rendering them over the AOI and one held-out region
- [ ] 4.3 Check the effect of lower 2023 acquisition density: subsample 2019 to 2023 density and compare features, verified by a short numeric report
- [ ] 4.4 Build PALSAR-2 HH, HV and HV/HH features from `JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH` for 2019, 2023 and each footprint shot year up to 2024 (availability confirmed 2026-10-03); decide whether 2025 footprints get ScanSAR features or are excluded from the PALSAR-2 rows, and record the counts (spec: "PALSAR-2 missing for a period")
- [ ] 4.5 Flag seasonally flooded pixels (e.g. from MapBiomas water/wetland classes) so they can be excluded or reported separately

## 5. Feature table

- [ ] 5.1 Extract all predictors (height, height uncertainty, S1, PALSAR-2, S2 bands and NDVI) as 12.5 m buffer means at every retained footprint, verified by no missing values beyond those explained by masks
- [ ] 5.2 Assign spatial blocks (~2 km) for cross-validation, reusing the Fase 1 approach, and verify no leakage between folds with a minimum-distance check

## 6. Baseline

- [ ] 6.1 Fit `ln(AGBD) = ln(a) + b ln(H)` with log-bias correction; report a, b, R², RMSE and bias under the design D7 protocol
- [ ] 6.2 Plot predicted vs. GEDI AGBD with the low-biomass stratum highlighted

## 7. Candidates and ablation

- [ ] 7.1 Fit Candidate A (multivariate log-linear) for every feature set in the ablation, reporting coefficients
- [ ] 7.2 Fit Candidate B (Random Forest) for every feature set, reporting feature importances
- [ ] 7.3 Produce the ablation table (spec: "Ablation table produced")

## 8. Decision

- [ ] 8.1 Apply the pre-registered criterion across cross-validation and each held-out region, and record the decision (spec: candidate outperforms vs. does not outperform), accepting either outcome as valid
- [ ] 8.2 Log all runs (data versions, parameters, metrics) to MLflow

## 9. Carbon conversion and uncertainty

- [ ] 9.1 Fix R with its IPCC table and forest type (after 1.1), and record it with the carbon fraction in the run config
- [ ] 9.2 Implement the Monte Carlo propagation (design D8), including the change-area confidence interval, verified by checking that interval width shrinks when input uncertainty is set to zero
- [ ] 9.3 Produce CO2e density maps (mean and 90% interval) for 2019 and 2023 over the AOI and held-out regions

## 10. Observed ΔCO2e

- [ ] 10.1 After `phase1-accuracy-assessment` task 5.4, compute ΔCO2e per change category from `aoi_change_areas.json` and the per-hectare density change (design D8), with intervals, plus the mapped pixel-sum as a labeled secondary value and the stock-difference cross-check
- [ ] 10.2 Export the per-class mean density and class-pair delta table (design D8) for `phase5-predictive-model` task 7.1

## 11. Independent comparison

- [ ] 11.1 Compare aggregated AOI and held-out estimates against ESA CCI Biomass for the nearest available years
- [ ] 11.2 Compare mean forest CO2e density against the dry-forest factors in Paraguay's FREL
- [ ] 11.3 Write the circularity limitation (design D9) explicitly

## 12. Documentation

- [ ] 12.1 Update `docs/METODOLOGIA_PIPELINE.md` (sources table, section 3.2, model justification, new results section) and `docs/FOUNDATION.md` point 6, aligning the calibration footprint wording
- [ ] 12.2 Add the Fase 2 results chapter to the thesis and update the roadmap table
- [ ] 12.3 Archive this change and sync the `carbon-estimation` spec into `openspec/specs/`
