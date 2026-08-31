## Context

See `proposal.md` - Why. This design covers the predictive extension's technical approach: how the baseline and candidate are built, how driver layers factor in, and how predicted change is bridged to a CO2e figure without a historical biomass time series (the core data gap identified in the proposal). It assumes the Fase 1 (classification) and Fase 2 (carbon) capabilities exist and produce, at minimum: a multi-year MapBiomas-derived land cover series for the AOI, and a table of carbon-density deltas per observed transition type (e.g. bosque→desmonte).

## Goals / Non-Goals

**Goals:**
- Forecast future land cover change for the case-study AOI, with an honest baseline-vs-candidate evaluation (mirroring CNN vs. Random Forest).
- Produce a projected CO2e figure for that forecast without needing a historical canopy-height/biomass series.
- Keep the predictive layer interpretable enough not to undercut the thesis's central auditability argument — CA-Markov's transition matrix and suitability weights double as the baseline's own explanation.
- Design data collection (training/calibration samples) wide enough to support a generalization check to a second Chaco sub-region, without building interactive tooling to do it.

**Non-Goals:**
- No interactive tool for arbitrary user-drawn polygons or date ranges (`docs/FOUNDATION.md`, Out of scope) — the generalization check is a one-time evaluation exercise, not a product feature.
- No attempt to reconstruct a historical canopy-height/biomass time series in this change. If the ETH model's code/weights turn out to be re-runnable on other years' Sentinel-2 (open question below), that's a future improvement, not a dependency of this design.
- No fusion of MapBiomas with the predictive model's own land-cover output — the historical series driving CA-Markov/the DL candidate stays MapBiomas-based, the same ground truth already used for training the classifier, to avoid compounding the classifier's own error into the forecast.

## Decisions

**CA-Markov as baseline, spatiotemporal deep learning as candidate — not the other way around, and not only one.** CA-Markov is the established method in land-change-modeling literature and is interpretable by construction, matching the thesis's core auditability argument; a spatiotemporal deep net is less mature to interpret (no established Grad-CAM equivalent) and risks undercutting that argument if used alone. Running both, evaluated against each other, mirrors the CNN-vs-Random-Forest posture already central to the thesis's methodology and produces a reportable finding either way (see spec: "Candidate does not outperform the baseline" is a valid, not a failing, outcome).

**Carbon bridge via historical transition-type deltas, not a regenerated biomass series.** Re-deriving canopy height and calibrating it against GEDI for a future/synthetic date isn't possible (there's no future imagery) and isn't needed: the observed-change side of the pipeline (Fase 2) already computes, per transition type, the average carbon-density delta between the "before" and "after" class. Applying that same delta to predicted-change pixels is simpler, avoids inventing data, and keeps the projection auditable back to the same historical calibration used everywhere else in the pipeline.

**Driver layers sourced at Chaco scale, not AOI-only.** Roads, cleared-edge distance, terrain, and tenure/protected-status layers are sourced for a footprint wider than the single case-study AOI (e.g. from OpenStreetMap, SRTM, and Paraguay's own land-tenure/protected-area registries where available at Chaco scale), so the same driver data can support both the AOI's CA-Markov suitability map and the held-out sub-region used for the generalization check, instead of building two separate driver datasets.

**Training/calibration sample wider than the AOI, to enable the generalization check.** The classifier's training sample and the GEDI calibration sample (Fase 1/Fase 2, not built in this change, but a dependency of this one's generalization requirement) should be drawn from a footprint spanning more of the Paraguayan Chaco, not just the ~20,589 ha case-study AOI — both MapBiomas and GEDI already have Chaco-wide coverage, so this doesn't require a new data source, only a broader sampling decision when those upstream changes are implemented. This design flags the dependency; it doesn't implement the sampling itself.

## Risks / Trade-offs

- **[Risk] Sparse/short historical MapBiomas-Sentinel2 overlap limits how far back the "historical series" can meaningfully go for training.** → Mitigation: MapBiomas's own multi-decade depth (1980s/90s onward) is used for the land-cover series itself, decoupling the predictive extension's training depth from Sentinel-2's shorter usable archive (~2017+), which only constrains the classification/carbon side, not this one.
- **[Risk] Driver layers (roads, tenure, protected status) may be incomplete or low-quality for the Paraguayan Chaco specifically.** → Mitigation: the spec's "Driver layer missing or unsourced" scenario requires documenting gaps explicitly rather than silently omitting a layer, keeping the suitability map's limitations auditable.
- **[Risk] Backtesting on a single held-out year, given the AOI's short usable history, may not be a robust test of either model.** → Mitigation: report Figure of Merit/Kappa with their known sensitivity to short validation windows noted as a limitation in the evaluation write-up, rather than treating a single backtest as conclusive.
- **[Trade-off] Choosing CA-Markov as the "safe" baseline sacrifices some of the novelty a purely deep-learning predictive layer might have offered.** Accepted deliberately: the thesis's differentiator is auditable evaluation methodology, not maximal model sophistication (see `docs/PIPELINE.md`, "Why CA-Markov + deep learning, not just one").

## Open Questions

- Is the predictive extension a required core component of the TFM or an optional one? Raised by the tutor in conversation, not resolved yet — doesn't change this design's approach, but does affect how much of it needs to be finished for the October 2026 prototype deadline.
- Are Lang et al.'s (ETH Global Canopy Height) model code/weights public and re-runnable on Sentinel-2 composites from years other than 2020? Would allow reconstructing a real canopy-height series instead of relying solely on the transition-delta bridge — worth investigating as a future improvement, not blocking this design.
- Has GEDI L4A's mission coverage for the AOI extended past the March 2023 cutoff found in the `phase1-define-study-area` feasibility check (the mission had a pause and later resumed)? Worth re-running that check; would only strengthen the historical carbon-delta inputs this design depends on, not change the approach.
