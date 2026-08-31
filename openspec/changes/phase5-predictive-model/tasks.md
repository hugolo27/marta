## 1. Scope confirmation

- [ ] 1.1 Confirm with Parra whether the predictive extension is required core or optional, and record the answer in `research_docs/BITACORA_FASES.md` and this change's `design.md` (Open Questions)
- [ ] 1.2 Re-run the GEDI L4A feasibility check for the AOI (reuse/extend the script from `phase1-define-study-area`) to see if mission coverage now extends past the March 2023 cutoff found previously, and record the result

## 2. Historical land cover series

- [ ] 2.1 Build a multi-year MapBiomas Chaco land cover series for the AOI, verified by confirming at least one year can be held out for backtesting (spec: "Sufficient historical depth available")
- [ ] 2.2 Document the series' year range and any gaps in `docs/PIPELINE.md`

## 3. Driver and suitability layers

- [ ] 3.1 Source a roads/infrastructure layer covering the AOI and the planned generalization sub-region (e.g. OpenStreetMap), verified by a rendered proximity-to-road raster over the AOI
- [ ] 3.2 Source a terrain/slope layer (e.g. SRTM-derived), verified the same way
- [ ] 3.3 Source a land tenure / protected-area status layer for the same footprint, verified the same way, or document that no usable source exists (spec: "Driver layer missing or unsourced")
- [ ] 3.4 Derive a distance-to-already-cleared-edge layer from the historical land cover series built in section 2, verified by inspecting output on a known deforestation front in the AOI

## 4. CA-Markov baseline

- [ ] 4.1 Fit the Markov transition matrix on the historical land cover series, verified by inspecting transition probabilities against known historical trends in the AOI
- [ ] 4.2 Build the suitability map from the driver layers (section 3), verified by visual inspection against known deforestation fronts
- [ ] 4.3 Implement the cellular automaton allocation step and produce a predicted future land cover map, verified end-to-end by running it on the AOI (spec: "Baseline forecast produced")

## 5. Deep learning candidate

- [ ] 5.1 Assemble the training tensor (stacked multi-year maps + driver layers as channels) for the AOI, verified by checking tensor shape/coverage matches the historical series
- [ ] 5.2 Train a ConvLSTM or 3D-CNN candidate on the assembled tensor, verified by confirming training converges and produces a predicted future land cover map

## 6. Baseline vs. candidate evaluation

- [ ] 6.1 Backtest both models against the held-out known year using Figure of Merit and Kappa, verified by producing both metrics for both models
- [ ] 6.2 Document the comparison result (spec: candidate outperforms vs. does not outperform) and select the model to carry forward, recording either outcome as valid

## 7. Projected CO2e bridge

- [ ] 7.1 Pull the historical carbon-density-per-transition-type deltas from the Fase 2 carbon pipeline output, verified by confirming coverage for the transition types present in the predicted change map
- [ ] 7.2 Apply the deltas to the selected model's predicted-change pixels to produce a projected CO2e figure, verified by producing a total and per-transition-type breakdown for the AOI
- [ ] 7.3 Handle predicted transition types with no corresponding historical delta by reporting them as unavailable rather than substituting a value (spec: "Carbon delta missing for a predicted transition type"), verified by a test case using a synthetic transition type absent from the historical deltas

## 8. Cross-region generalization check

- [ ] 8.1 Designate a held-out sub-region within the Paraguayan Chaco, distinct from the case-study AOI, with adequate MapBiomas/GEDI coverage, verified by running the same feasibility check used for the case-study AOI
- [ ] 8.2 Run the selected predictive model and the classifier on that sub-region and report accuracy/agreement metrics alongside the AOI's own metrics, verified by a side-by-side metrics table

## 9. Write-up

- [ ] 9.1 Document the predictive extension's methodology, results, and open limitations in the TFM document sections covering results/conclusions, cross-referencing `docs/FOUNDATION.md` point 10
