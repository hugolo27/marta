## Context

See proposal.md for motivation. Relevant current state:

- This change runs after `phase1-change-detection-hardening`, which produces the forest/non-forest change map with a pre-registered post-processing configuration (`change_map_2019_2023_fnf.npy`) and already reports agreement with Hansen and MapBiomas. The sample here is stratified on that map.
- The held-out regions have no dense maps. `holdout_eval.py` classifies sampled points by pulling each point's patch, a mechanism that can classify arbitrary reference points too.
- Imagery access checked 2026-09-24:
  - Planet NICFI basemaps exist in GEE (4.77 m, Dec 2015-Aug 2026), but the project's service account has no access.
  - The NICFI contract with Planet expired in early 2025, and Norway cancelled the next-phase procurement in September 2025, so new sign-ups are unlikely.
- An earlier hyperparameter sweep scored on the test split. It was never used for a decision, and `phase1-hyperparameter-selection` (archived 2026-10-13) replaced it with selection on the validation split. The reference sample must not repeat that pattern.

## Goals / Non-Goals

**Goals:**
- One interpreted sample per area that serves both the per-date gate and the change-area estimate, sized to the VM0007 minimum plus a margin rather than to the largest defensible number.
- Estimators verified against published worked examples before being applied to project data.
- Every number traceable to archived points a third party can re-interpret.

**Non-Goals:**
- No change to the classifier or the change-map configuration here. The reference labels can evaluate a later model too (Stehman's estimator works for any map, given the stored strata), but only if the decision to change the model did not use this assessment's results (spec: "Assessment sample is not reused for tuning").
- No three-class reference labels. Forest/non-forest is what VM0007 gates and what carbon needs; an optional note field captures the class when it is obvious, but it is not assessed.
- No 2019 assessment in the held-out regions. Generalization is a per-date question, and 2023 answers it; the AOI carries both dates because the change estimate needs them.
- No field work (out of scope in `docs/FOUNDATION.md`). VM0007 accepts high-resolution imagery.

## Decisions

**AOI: one sample over six strata; every estimate via Stehman (2014).** Redrawn on 2026-10-03, before any point was interpreted. The first draw (four strata = the map's change classes, 275 points) was reviewed and found to leave omission poorly covered: in a near-intact AOI the large stable-forest stratum decides the loss-area interval, and the map's own change is probably mostly false, so a buffer around it alone mostly surrounds noise. Strata, in order of precedence:
- `loss`, `gain`: the hardened map's change classes.
- `discarded_change`: change in the unfiltered forest/non-forest map that the confidence + persistence filter removed. This is where the filter could have erased real clearing.
- `buffer`: 60 m around the final change, plus Hansen 2020-2023 or MapBiomas 2019→2023 loss dilated 30 m (690 px, too few to be a stratum of their own; the patch is also reviewed by hand as a qualitative check, outside the estimator). Rule fixed before drawing: 60 m, provided the buffer stays under 10% of the AOI; it covers 0.29% (90 m would be 0.60%).
- `stable_forest`, `stable_nonforest`: the rest.
- Strata are not the map's classes, so per-date and change estimates both use Stehman's estimator with each point's map class stored in the design file.
- Sampling frame: classified pixels whose centre lies inside the AOI polygon. 13,431 classified edge pixels (0.65%) have their centre just outside and are excluded from the frame.

**Allocation: 50 loss, 40 gain, 40 discarded change, 30 buffer, 120 stable forest, 60 stable non-forest (340 points).**
- 50 for loss, VM0007's minimum per class and within Olofsson's 50-100 guidance; 30-40 in the other rare strata for budget (SE of a user's accuracy near 50% with 40 points is about 8 points).
- Stable forest gets the most points because missed loss there dominates the loss-area interval. If no loss is found among n points of a stratum of area A, the 95% upper bound is about 3A/n (rule of three): with 120 points in ~16,400 ha, ~410 ha. Loss below a few hundred hectares cannot be resolved with this budget; that is a limit of the sample, not of the model, and is reported as such.
- The ≥ 50 rule is checked both by map class and by reference class, since the PD's wording does not say which one it means.
- An empty stratum is not sampled and its points go to stable forest.
- If the loss-area confidence interval is still wider than ±50% of the estimate, a top-up sample is drawn with the same design and recomputed inclusion probabilities, not an ad-hoc addition.

**Assessment unit: the 10 m map pixel, labeled in the context of the forest definition.** The interpreter labels the pixel forest only if it sits inside a woody patch that meets the definition. This keeps the unit identical to the map while applying the definition's minimum area.

**Two forest definitions: the PD's as primary, Paraguay's FREL as secondary, fixed before interpretation.**
- Primary: the CDM definition the case-study PD uses (≥ 25% crown, ≥ 0.5 ha, ≥ 5 m potential). The VM0007 gate is a conformity test against the project, whose figures use this definition.
- Secondary: the FREL definition for the Región Occidental (FREL 2016, section 2.3: ≥ 10% crown, ≥ 1 ha, ≥ 3 m; protective strips count only if ≥ 60 m wide and ≥ 1 ha; wording and page to be checked against the original before citing). The difference between the two is a result in itself: area that is forest for national accounting but not for the project. MapBiomas' legend is probably closer to the FREL, so part of the classifier's error against the CDM definition may be definitional, and the two measurements separate it.
- Per point and date the interpreter records the primary label plus the attributes that separate the definitions: crown class (< 10%, 10 to < 25%, ≥ 25%), woody patch size (< 0.5 ha, 0.5 to < 1 ha, ≥ 1 ha), height (≥ 5 m, 3-5 m, < 3 m, or indeterminate), whether the patch is a strip under 60 m wide, and a near-threshold flag. The FREL label is derived from them (`scripts/reference_labels.py`), never interpreted twice, and the primary label is checked for consistency with its own attributes.
- Crown is counted on a 5×5 grid of crosses drawn inside the 0.5 ha square (each 4%), not guessed.
- Height cannot be seen on imagery. "Indeterminate" is allowed, counted as meeting the CDM's 5 m potential, and the FREL result is reported both with and without counting it as meeting 3 m. Declared as a limitation.
- Woody vegetation failing the primary definition is reported as the share of the classifier's "bosque" points on it (MapBiomas codes 4 and 45 included).

**Reference imagery: Google Earth Pro historical imagery as primary, Esri World Imagery Wayback as secondary, NICFI only if access is granted.**
- Google Earth Pro's time slider gives sub-meter to few-meter imagery at irregular dates, and is free.
- The imagery date used is recorded per point-date. Imagery from the same year is required. Leaf-on (wet season) imagery is preferred when there is a choice, because the deciduous Chaco forest shows less crown in the dry season and crown cover is now a recorded attribute.
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

**Interpreter consistency: blind repeat on a 20% random subset.** The main interpreter is the author, who also built the classifier, so a second interpreter is strongly preferred for the repeat (e.g. the forestry engineer contact). Otherwise the same interpreter repeats it at least 14 days later, in shuffled order, without access to the first labels, and the thesis states that the reference was interpreted by the author. Disagreements are adjudicated with a recorded reason, and the final estimates use adjudicated labels only.

**Estimators live in one unnumbered module and are verified on published examples.**
- `scripts/accuracy_stats.py` implements Olofsson (2014) and Stehman (2014), verified by reproducing each paper's worked numerical example.
- Pipeline steps are numbered after the hardening change's scripts.
- Results are logged to MLflow under experiment `phase1-accuracy-assessment`.
- Points, labels, KML and results JSON go to `data/study_area/accuracy_assessment/`, which is versioned (not covered by the existing `.gitignore` rules).

**Gate and headline numbers.**
- The PD defines overall accuracy as correct samples over total samples (checked in the PD, monitoring section). On this sample, which deliberately oversamples change strata, the raw count is not an estimate of the map's accuracy, so the gate uses the area-weighted (Stehman) overall accuracy and the raw count is reported next to it.
- In a near-intact AOI overall accuracy will be high almost regardless of the change map. The user's and producer's accuracy of loss is reported as the headline result, not as a secondary number.
- When a stratum shows no reference loss, its SE contribution is zero and the interval would look falsely narrow. The rule-of-three bound per such stratum is added to the CI upper limit and reported as the loss upper bound, phrased as "loss not distinguishable from zero, upper bound X" when the estimate's interval includes zero.
- Near-threshold point-dates are kept, and accuracy is also reported without them as a sensitivity check.

**Gate outcome is recorded, not acted on here.**
- A pass clears the CNN for Fase 2 under the VM0007 bar.
- A fail records the error analysis and scopes a classifier-level change, for example relabeling training data where MapBiomas disagrees with the Paraguayan definition, or a dedicated forest/non-forest decision threshold.
- Either way, Fase 2 consumes the error-adjusted areas.

## Risks / Trade-offs

- **[Risk] Google Earth Pro has no same-year imagery over parts of the AOI for 2019** → Fall back to Esri Wayback versions for that point. If both lack it, mark the point uninterpretable and report exclusions per stratum. If exclusions push a class below 50 points, draw replacement points in that stratum with the same design.
- **[Risk] Imagery dates differ from the composite season** → Forest/non-forest (the gated split) depends on woody structure, which is far less seasonal than the pasture/crop split. The date is recorded, so any seasonal pattern in disagreements is visible.
- **[Risk] The interpreter is not a trained photo-interpreter, and is the model's author** → A written protocol with example points per class comes before labeling, crown is counted on a grid, uncertain calls go into notes or the near-threshold flag, and the 20% repeat (second interpreter preferred) quantifies the effect.
- **[Trade-off] Smaller sample (340 AOI points) than the original plan (~500)** → It still meets the VM0007 minimum with margin. The cost is wider confidence intervals, and a loss bound of a few hundred hectares, which are reported rather than hidden.
- **[Risk] The result is a fail** → A valid, reportable finding. It is what the gate exists to catch before the carbon figure inherits it.
