## Context

See proposal.md for motivation. Relevant current state:

- This change runs after `phase1-change-detection-hardening`, which produces the forest/non-forest change map with a pre-registered post-processing configuration (`change_map_2019_2023_fnf.npy`) and already reports agreement with Hansen and MapBiomas. The sample here is stratified on that map.
- The held-out regions have no dense maps. `holdout_eval.py` classifies sampled points by pulling each point's patch, a mechanism that can classify arbitrary reference points too.
- Imagery access checked 2026-09-24:
  - Planet NICFI basemaps exist in GEE (4.77 m, Dec 2015-Aug 2026), but the project's service account has no access.
  - The NICFI contract with Planet expired in early 2025, and Norway cancelled the next-phase procurement in September 2025, so new sign-ups are unlikely.
- The hyperparameter sweep scored on the test split, a known contamination issue (BITACORA 2026-09-19). The reference sample must not repeat that pattern.

## Goals / Non-Goals

**Goals:**
- One interpreted sample per area that serves both the per-date gate and the change-area estimate, sized to the VM0007 minimum plus a margin rather than to the largest defensible number.
- Estimators verified against published worked examples before being applied to project data.
- Every number traceable to archived points a third party can re-interpret.

**Non-Goals:**
- No change to the classifier or the change-map configuration. Changes require a fresh sample (spec: "Assessment sample is not reused for tuning").
- No three-class reference labels. Forest/non-forest is what VM0007 gates and what carbon needs; an optional note field captures the class when it is obvious, but it is not assessed.
- No 2019 assessment in the held-out regions. Generalization is a per-date question, and 2023 answers it; the AOI carries both dates because the change estimate needs them.
- No field work (out of scope in `docs/FOUNDATION.md`). VM0007 accepts high-resolution imagery.

## Decisions

**AOI: one sample stratified by change class; per-date accuracy via Stehman (2014).**
- Strata: forest loss, forest gain, stable forest, stable non-forest, from the hardened map.
- Each point is interpreted for 2019 and 2023 in the same view. The two labels give both the change error matrix (Olofsson et al., 2014) and each date's forest/non-forest error matrix.
- Per-date map classes are not the sampling strata, so per-date accuracy uses Stehman's estimator for strata that differ from map classes.

**Allocation: 50 per change stratum, 100 stable forest, 75 stable non-forest (~275 points).**
- 50 is VM0007's minimum per class and within Olofsson's 50-100 guidance for rare strata.
- Stable forest gets the most points because missed loss inside a large stable stratum dominates the loss-area confidence interval.
- The ≥ 50 rule is checked both by map class and by reference class, since the PD's wording does not say which one it means.
- If a change stratum is empty after hardening, it is not sampled and its area comes from omissions in the stable strata (spec scenario). Its points go to stable forest.
- If the loss-area confidence interval is still wider than ±50% of the estimate, a top-up sample in stable forest is drawn with the same design and recomputed inclusion probabilities, not an ad-hoc addition.

**Assessment unit: the 10 m map pixel, labeled in the context of the forest definition.** The interpreter labels the pixel forest only if it sits inside a woody patch of at least 0.5 ha (~70×70 m) with at least 25% crown cover. This keeps the unit identical to the map while applying the definition's minimum area. Open or sparse woody vegetation that fails the definition is flagged; this measures how much of the classifier's "bosque" (MapBiomas codes 4 and 45 included) sits outside the Paraguayan definition.

**Reference imagery: Google Earth Pro historical imagery as primary, Esri World Imagery Wayback as secondary, NICFI only if access is granted.**
- Google Earth Pro's time slider gives sub-meter to few-meter imagery at irregular dates, and is free.
- The imagery date used is recorded per point-date. Imagery from the same year is required, preferably within or near the June-September composite window.
- Sentinel-2 is not a valid reference: it is the classifier's own input, and not high-resolution under VM0007's wording.

**Interpretation workflow: KML for Google Earth Pro plus a CSV.**
- The sampling script writes a KML with each point's ID and a 0.5 ha square around it, and a CSV with fixed columns: point id, forest/non-forest per date, imagery date per date, flags, notes.
- The model's labels are kept in a separate join file that is not opened during interpretation.
- Alternatives rejected:
  - A GEE Code Editor viewer: it cannot show Google Earth's historical imagery, which is now the primary source.
  - Python image chips: thumbnail access under the service account has been unreliable, and a chip loses the ability to pan for context.

**Held-out regions: stratify by an independent proxy, classify points by patch.**
- Each region gets 50 points per stratum, stratified by ESA WorldCover 2021 tree cover vs. other (independent of both MapBiomas and the model). Points are interpreted for 2023 only.
- Each point is then classified by pulling its patch through the existing `holdout_eval.py` mechanism, with `reproject=False` for the multi-zone composites.
- Stehman's estimator applies again, since the strata are not the map classes. This avoids building dense maps over regions up to 8× the AOI.

**Interpreter consistency: blind repeat on a 10% random subset.** It is done by a second interpreter if available (e.g. the forestry engineer contact, who can also take part of the main load). Otherwise the same interpreter repeats it at least 14 days later, in shuffled order, without access to the first labels. Disagreements are adjudicated with a recorded reason, and the final estimates use adjudicated labels only.

**Estimators live in one unnumbered module and are verified on published examples.**
- `scripts/accuracy_stats.py` implements Olofsson (2014) and Stehman (2014), verified by reproducing each paper's worked numerical example.
- Pipeline steps are numbered after the hardening change's scripts.
- Results are logged to MLflow under experiment `phase1-accuracy-assessment`.
- Points, labels, KML and results JSON go to `data/study_area/accuracy_assessment/`, which is versioned (not covered by the existing `.gitignore` rules).

**Gate outcome is recorded, not acted on here.**
- A pass clears the CNN for Fase 2 under the VM0007 bar.
- A fail records the error analysis and scopes a classifier-level change, for example relabeling training data where MapBiomas disagrees with the Paraguayan definition, or a dedicated forest/non-forest decision threshold.
- Either way, Fase 2 consumes the error-adjusted areas.

## Risks / Trade-offs

- **[Risk] Google Earth Pro has no same-year imagery over parts of the AOI for 2019** → Fall back to Esri Wayback versions for that point. If both lack it, mark the point uninterpretable and report exclusions per stratum. If exclusions push a class below 50 points, draw replacement points in that stratum with the same design.
- **[Risk] Imagery dates differ from the composite season** → Forest/non-forest (the gated split) depends on woody structure, which is far less seasonal than the pasture/crop split. The date is recorded, so any seasonal pattern in disagreements is visible.
- **[Risk] The interpreter is not a trained photo-interpreter** → A written protocol with example points per class comes before labeling. Uncertain calls go into notes, and the consistency check quantifies the effect.
- **[Trade-off] Smaller sample (~275 AOI points) than the original plan (~500)** → It still meets the VM0007 minimum with margin. The cost is wider confidence intervals, which are reported rather than hidden, and the top-up rule covers the case where the loss interval is too wide to be useful.
- **[Risk] The result is a fail** → A valid, reportable finding. It is what the gate exists to catch before the carbon figure inherits it.
