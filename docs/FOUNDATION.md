# Project foundation

*Languages: **English** | [Español](FOUNDATION.es.md)*

## The problem

Generating a Monitoring Report for a REDD+ project in the Paraguayan Chaco today relies on some mix of manual GIS judgment, semi-automatic classification tools, and aggregate satellite monitoring platforms that already run at scale (Global Forest Watch/Global Nature Watch, MapBiomas itself). None of these give per-prediction evidence: biomass/carbon is calculated with inconsistent methods, and the auditor (VVB) reviews the resulting report as a black box, with no traceable evidence of why a specific area was classified as deforestation — whether that classification came from a person or an algorithm — or how the CO2 tonnage figure was reached.

This creates two concrete problems:

1. **Cost and time:** weeks and thousands of dollars just for this stage, before the auditor even gets involved.
2. **Lack of traceability:** there's no systematic way to audit *why* a system (human or automated) concluded there was or wasn't deforestation, nor to check whether the hectares and tons claimed by a project match what's observable by satellite. Independent evaluations of first-generation REDD+ projects document substantial over-crediting, but locate most of it in how the baseline was built (reference areas and ex ante modelling) rather than in how forest cover was measured (Swinfield et al., 2026).

## The research question

> Is it possible to build, over Sentinel-2 imagery and open satellite products, a pipeline that classifies land cover with interpretable evidence for each prediction, and translates detected change into an estimate of associated CO2 tons — such that both the classification and the carbon figure are auditable rather than a black box?

The system works at the land-cover level over 10m pixels (area/hectares), not at the individual-tree level. REDD+ and the Chaco are the case study used to validate this — chosen because REDD+ has a documented, credit-type-specific credibility problem (see Justification below), not because the underlying approach is assumed to work only for REDD+ or only in this region.

**What this project actually tests, rather than assumes:**

- Whether a CNN meaningfully outperforms a simpler Random Forest baseline on this classification task — a negative result here is a valid finding, not a failure of the project.
- Whether Grad-CAM heatmaps hold up as coherent, useful audit evidence on this specific data. Interpretability methods are typically validated on different conditions than the Chaco's dry, dispersed vegetation, so this isn't assumed to transfer cleanly.
- Whether a satellite-calibrated carbon estimate (pretrained canopy height + GEDI) produces a defensible number for a real registered project, given known biases in the underlying models for low-canopy vegetation.
- Whether a spatiotemporal deep learning model meaningfully outperforms a classical CA-Markov baseline at predicting future land cover change — the same "does the added complexity earn its keep" test applied to the predictive extension (see point 10 below), mirroring the CNN vs. Random Forest comparison.

## General objective

Evaluate a candidate satellite verification pipeline for the carbon credit market in the Paraguayan Chaco: land cover classification with a CNN, tested against a simpler baseline, with a candidate interpretability layer intended to make change detection auditable, combined with a biomass/carbon/CO2 estimate calibrated on open satellite products — as a prototype to assess the technical feasibility of automating and making auditable the monitoring report (MRV) generation stage.

## Approach under evaluation

The components below make up the approach being tested, not a finished system presented as validated. Each has an explicit evaluation step, because its suitability for this specific data — Chaco vegetation, one credit type, one case study — isn't established yet.

1. **Dataset:** Sentinel-2 imagery + MapBiomas Chaco as ground truth, over a bounded study area. Case study: Corazón Verde del Chaco (VCS 2611), a real registered REDD+ project — chosen because it lets the audit approach be validated against real, publicly claimed figures, not because the method is REDD+-specific. Approximate boundary (see `openspec/specs/study-area/`), confirmed by the tutor, GEDI feasibility check passed.
2. **Classification candidate:** a CNN adapted to Sentinel-2's 13 spectral bands (not just RGB), with spectral indices (NDVI and similar) as additional channels — evaluated against the baseline below, not assumed superior by default.
3. **Baseline:** Random Forest on spectral features, run specifically to test whether the CNN's added complexity is justified.
4. **Temporal comparison:** classify two or more points in time and produce a change map (hectares that moved from forest to another class) — the change-detection mechanism, independent of which classifier from points 2–3 performs better.
5. **Interpretability candidate:** Grad-CAM, producing a heatmap per prediction intended to show which region of the image supports each classification. Selected over other XAI methods based on prior literature (lighter computational cost, comparable interpretability; Kakogeorgiou & Karantzalos, 2021) — but its actual coherence on this data is evaluated, not assumed (see objective 7).
6. **Carbon estimation:** for the detected hectares of change, a candidate pipeline to estimate associated tons of CO2:
   - **Canopy height by inference** (no retraining), running the pretrained ETH Zürich Global Canopy Height model (10m, 2020 baseline year) and filtering estimates using the model's own uncertainty layer — its paper reports an overestimation bias in low canopies (≈2 m between 5 and 20 m, and some overestimation below 5 m), a range common in Chaco vegetation, although it also reports a low mean bias (<1 m) for tropical dry broadleaf forest — a biome-level average validated against GEDI rather than field measurements, so results in the Chaco need scrutiny rather than being taken at face value.
   - **Height → biomass calibration** with a log-log power regression (`AGBD = a · height^b`) fit against GEDI L4A footprints in the study region — contingent on an early feasibility check of GEDI footprint density/quality in the Chaco.
   - **Biomass → carbon → CO2e conversion** with standard IPCC factors (see formula below), including a belowground biomass factor (root-to-shoot) so as not to report aboveground carbon only.
7. **Evaluation:** quantitative (accuracy, IoU/Dice, confusion matrix, CNN vs. baseline comparison) and qualitative (whether Grad-CAM heatmaps actually align with known change, height-biomass fit quality via cross-validation) — this is where points 2 and 5 get an actual answer, not just a stated intention.
8. **Functional prototype of the full flow:** satellite image → classification → temporal comparison → heatmap → associated CO2 estimate, presentable at the symposium regardless of which specific model choices hold up.
9. **Audit demo (case study):** run the full pipeline over Corazón Verde del Chaco and compare satellite-observed hectares/CO2 against the observed figures in the project's public monitoring reports. This is an independent verification of the *observed* side of the report (deforestation inside the project area and carbon stock), with per-prediction evidence. It does not assess additionality or the baseline, where independent evaluations locate most of the over-crediting (Swinfield et al., 2026), so on its own it cannot establish whether this project's credits were over-issued. It is a case study of one project — not a general claim about the REDD+ market as a whole.
10. **Predictive extension (new relative to the tutor's originally documented 6-phase methodology):** beyond validating past change (points 3-4-6-9, all retrospective), forecast future land cover change and its associated projected CO2e for the study area, using the same "baseline vs. candidate" evaluation posture as points 2-3:
    - **Baseline:** CA-Markov — a Markov transition matrix (historical class-change frequency, from a multi-year MapBiomas series) combined with a cellular automaton that allocates that change to specific pixels using neighborhood rules and a suitability map (driver layers such as roads, distance to already-cleared edges, terrain, land tenure). Interpretable by construction — the transition matrix and suitability weights are themselves the explanation, no separate interpretability layer needed.
    - **Candidate:** a spatiotemporal deep learning model (ConvLSTM or 3D-CNN) over the stacked multi-year maps, evaluated against the CA-Markov baseline via backtesting (train on years 1..N-1, predict a known year N, score with Figure of Merit/Kappa) — not assumed superior by default, same posture as point 2 vs. point 3.
    - The projected CO2e figure reuses the historical carbon-density-per-transition-type numbers already computed for observed change (points 4-6), applied to the pixels either model predicts will change — it does not require synthetic future imagery or re-running canopy-height inference.
    - This extension was proposed by the tutor in conversation and isn't part of his originally documented methodology (`research_docs/METODOLOGIA_TUTOR.md`, which is entirely retrospective/stock-based).

### Validation (if data becomes available)

Optional contrast against published local allometric equations for Paraguay, or field measurements (possible collaboration with A Todo Pulmón Paraguay / Colosos de la Tierra), instead of relying on GEDI alone.

### Carbon estimation formula

```
AGBD (Mg/ha)      = a · H^b                 — log-log regression, H = canopy height (m), calibrated against GEDI L4A
AGB_total (Mg/ha) = AGBD × (1 + R)           — R = IPCC root-to-shoot ratio (~0.20–0.24 depending on biomass class/ecological zone)
Carbon (Mg C/ha)  = AGB_total × 0.47         — default carbon fraction (IPCC 2006 GL Vol.4)
CO2e (Mg CO2/ha)  = Carbon × 3.67            — CO2:C molecular weight ratio (44/12)

ΔCO2e (Mg CO2) = Σ over changed pixels [ CO2e_density_before − CO2e_density_after ] × area_ha
```

`ΔCO2e` is the figure that would actually matter to the carbon market (tons avoided/emitted) if the pipeline holds up under evaluation — it's what connects classification (point 4) to carbon estimation (point 6).

## What interpretability would solve, if it holds up (and what it wouldn't anyway)

Grad-CAM, even if its heatmaps prove coherent on this data, wouldn't detect fraud directly. What it would do is turn a classification claim ("this is deforestation") into something checkable with traceable visual evidence, lowering the cost of auditing and surfacing systematic model errors — e.g. a cloud misread as deforestation. What it wouldn't do, even working as intended: verify that the training ground truth is itself correct, prevent intentional manipulation of input imagery, or replace field validation.

## Scope

**Included:** CNN classification over a bounded area of the Chaco evaluated against a Random Forest baseline, Grad-CAM evaluated qualitatively as an audit mechanism, a GEDI-calibrated carbon/CO2 estimate, a predictive extension (CA-Markov baseline vs. spatiotemporal deep learning candidate, see point 10 above), an audit demo against one real registered project, a functional/demonstrable prototype, a document and defense following the standard graduate program structure.

**Out of scope:** replacing the VVB auditor or producing a legally valid report before Verra, processing the entire Chaco or building a national real-time monitoring system, building the full SaaS product (automatic ingestion, dashboard, third-party API, arbitrary user-drawn polygons anywhere in the region), assessing a project's additionality or baseline (e.g. against matched control areas), left as future work, original field work for in-situ validation, carbon pools beyond above/belowground biomass (deadwood, litter, and soil carbon are excluded and documented as a limitation).

The cut to REDD+ and to one case-study project is a scope decision made to keep the TFM achievable in the available time — not a claim that the classification and carbon-estimation approach only works for REDD+. Whether it generalizes to other credit types or regions is explicitly untested and left as future work.

**On generalization within the Chaco specifically:** the case-study demo (point 9) is fixed to one AOI, but that's a scope decision about the *demo*, not a hard technical ceiling on the *model*. The classifier's training sample and the GEDI calibration sample are deliberately drawn from a footprint wider than the single case-study AOI (MapBiomas and GEDI both have Chaco-wide coverage, not just over Corazón Verde del Chaco), so the trained pipeline is a candidate for generalizing to other areas within the Paraguayan Chaco — tested, not assumed, via a held-out sub-region accuracy check during evaluation (point 7), not by building the interactive multi-polygon tool that's explicitly out of scope above. Generalizing beyond the Paraguayan Chaco (other Chaco countries, other biomes) is untested and out of scope.

---

This document is a public summary of the framing. Full detail (state of the art, legal framework, tutor methodology, decision log) is kept in private research notes outside this repository.
