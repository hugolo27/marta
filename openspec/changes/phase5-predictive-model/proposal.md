## Why

Every capability in the project so far is retrospective: it classifies and quantifies change that already happened (Fase 1: detection, Fase 2: carbon for observed change). The tutor separately suggested, in conversation, that the project also produce a forward-looking view — given the change already observed in the AOI's historical record, predict how the terrain is likely to behave next, and what CO2e that implies. This isn't part of his originally documented 6-phase methodology (`research_docs/METODOLOGIA_TUTOR.md`, entirely stock-based/retrospective), so it's tracked here as an explicit, separately-scoped addition rather than folded into an existing phase.

## What Changes

- Add a predictive extension to the pipeline: given the AOI's historical multi-year land cover series, forecast future land cover change and the CO2e it implies, evaluated with the same "baseline vs. candidate" posture already used for CNN vs. Random Forest.
- **Baseline — CA-Markov**: a Markov transition matrix (historical class-change frequency from a multi-year MapBiomas Chaco series) combined with a cellular automaton that allocates predicted change to specific pixels via neighborhood rules and a suitability map built from driver layers (proximity to roads, proximity to already-cleared edges, terrain, land tenure/protected status).
- **Candidate — spatiotemporal deep learning**: ConvLSTM or 3D-CNN over the stacked multi-year maps, evaluated against the CA-Markov baseline via backtesting (train on years 1..N-1, predict a known year N, score with Figure of Merit/Kappa) — not assumed superior by default.
- **Carbon bridge**: no synthetic future satellite imagery and no re-run of canopy-height inference for future years. The projected CO2e reuses the carbon-density-per-transition-type deltas already computed for observed change in Fase 2, applied to the pixels either predictive model marks as likely to change.
- **New driver layers to source** (none currently identified in the pipeline): roads/infrastructure, distance to already-cleared edges, terrain/slope, land tenure or protected-area status.
- Document, rather than resolve in this change, the data gap this depends on: there is no deep historical biomass/carbon series — GEDI L4A only covers the AOI from ~April 2019 to March 2023 per the feasibility check done in `phase1-define-study-area` (3,823 quality footprints), and ETH Global Canopy Height is a static 2020 product, not a series. Whether Lang et al.'s model code/weights are public and re-runnable on other years' Sentinel-2 to produce a canopy-height series is an open technical question, not required to make this extension viable (the transition-delta bridge above sidesteps it), but worth investigating as a future improvement.
- Design the training/calibration sample (classifier and GEDI calibration) to span a footprint wider than the single case-study AOI where feasible, so a generalization check across a held-out sub-region of the Paraguayan Chaco is possible during evaluation — not a general-purpose interactive tool (still out of scope, see `docs/FOUNDATION.md`).

## Capabilities

### New Capabilities
- `predictive-change-model`: forecasts future land cover change and projected CO2e for the study area, via a CA-Markov baseline evaluated against a spatiotemporal deep learning candidate, bridging to carbon through historical transition-type deltas rather than synthetic future imagery.

### Modified Capabilities
(none — this change does not alter the requirements of `study-area` or any other existing spec)

## Impact

- New driver/covariate data sourcing (roads, cleared-edge distance, terrain, tenure) not previously part of the pipeline — none identified yet, this change's design/tasks need to source them.
- Depends conceptually on: the AOI (`study-area`, already resolved), a multi-year MapBiomas land cover series for the AOI, and the historical carbon-density-per-transition-type figures produced by the Fase 1 classification pipeline and the Fase 2 carbon pipeline — neither of which exists as an OpenSpec change yet. This proposal does not block on those changes existing, but implementation (`/opsx:apply`) does depend on their outputs being available.
- Updates `docs/FOUNDATION.md` and `docs/METODOLOGIA_PIPELINE.md` to reflect the predictive extension.
- No code, training, or data pipeline work happens in this change — planning artifacts only.
