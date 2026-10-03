## Context

See proposal.md for motivation. Relevant current state:

- `scripts/18_classify_aoi_temporal.py` stores only the argmax class per pixel for 2019 and 2023 (Sentinel-2 composites over June-September). It uses the reference checkpoint (`data/study_area/cnn_checkpoint.pt`, seed 42).
- `scripts/19_temporal_change_map.py` diffs the two class rasters into 6 named transitions plus no-change. Only 4 transitions occur, all of them with little or no support from MapBiomas.
- The AOI is a protected REDD+ area with almost no real loss in the period: Hansen shows 0.1 ha for 2020-2023 and ~118 ha across 2001-2019. Evaluating on the AOI alone can only measure false loss (commission). It cannot measure whether real loss is still detected.

## Goals / Non-Goals

**Goals:**
- A change map whose forest loss is defensible against independent references before any manual interpretation is spent.
- A configuration choice that is pre-registered and reproducible, not tuned by eye.

**Non-Goals:**
- No retraining, relabeling or architecture change of the classifier. If post-processing cannot fix the map, that becomes a separate change with its own evidence.
- No use of the interpreted reference sample (`phase1-accuracy-assessment`). It stays the untouched final test.
- No change to per-date accuracy claims made by `land-cover-classifier`.

## Decisions

**Forest/non-forest collapse before diffing.** Loss and gain are defined as forest→non-forest and non-forest→forest. The pasto/cultivo split is the classifier's weakest (IoU 0.59/0.65) and does not matter for carbon at this stage, since both are non-forest for the Paraguayan definition and for VM0007's forest/non-forest monitoring. Named transitions stay as a secondary, not-for-area output, so nothing already reported is silently erased.

**Candidate post-processing, combined as a small grid:**
- *Minimum mapping unit*: none or 0.5 ha (50 pixels, 8-connectivity). 0.5 ha is the Paraguayan definition's minimum area, so this is a definitional choice rather than a tuned threshold.
- *Temporal persistence*: none, or loss requires forest in 2019 and non-forest in both 2022 and 2023 (gain symmetric), using dense classifications for 2020-2022 with the same checkpoint and season window. A class that flips and flips back across years is noise, not land-cover change.
- *Confidence*: none, or softmax probability ≥ 0.7 or ≥ 0.9 on the relevant class at both endpoint dates, otherwise the pixel stays stable. This requires storing probabilities, not only argmax.

That makes 2 × 2 × 3 = 12 configurations. It is small enough to report in full, which avoids a search large enough to overfit the development references.

**Change-development area: a box of AOI-like size with documented 2020-2023 loss.** It is chosen inside the training footprint by Hansen loss density, and excludes the AOI and the three held-out regions (Filadelfia, Bahía Negra, Pozo Colorado stay reserved for generalization). Using a training-footprint area is acceptable here: the classifier was trained on per-date labels at sampled points, while this area evaluates a change-map post-processing choice. The chosen box and its selection criterion are recorded before scoring.

**Development references and their roles.** Hansen loss (`lossyear` 20-23, `treecover2000` ≥ 25%) marks loss confirmed by an independent Landsat product. MapBiomas marks bosque in 2019 and non-bosque in 2023 in its own maps. "Confirmed loss" is the pixels where both agree; "confirmed stable forest" is forest in both MapBiomas years with no Hansen loss. Neither reference is treated as truth, and agreement with both is the development signal. MapBiomas and Hansen are 30 m, so they are compared at 30 m by majority-aggregating the 10 m map.

**Pre-registered selection rule** (written into tasks.md before scoring):
1. Reject any configuration that keeps less than 50% of confirmed loss in the change-development area.
2. Among the remaining ones, pick the configuration with the smallest false-loss area in the AOI (map loss outside confirmed loss).
3. If two configurations are within 10% of each other on step 2, pick the simpler one (fewer active post-processing steps).

This favors removing commission error in the protected area without buying it by blinding the map to real clearing.

**Per-date rasters regenerated, same checkpoint.** 2019 and 2023 are re-run to add probabilities. The argmax of the new run must equal the stored rasters pixel-for-pixel, which verifies nothing else changed.

## Risks / Trade-offs

- **[Risk] No configuration keeps ≥ 50% of confirmed loss while cutting AOI false loss substantially** → Report that as the result. The next step is a classifier-level change (relabeling against the Paraguayan definition, a dedicated forest/non-forest decision), not loosening the rule after seeing the scores.
- **[Risk] Hansen and MapBiomas share Landsat origins, so their agreement is not fully independent** → Acknowledged. They are development references only; the final claim rests on the interpreted sample in `phase1-accuracy-assessment`.
- **[Trade-off] Persistence needs 3 extra annual classifications (GEE time and ~27 MB rasters each)** → Accepted. The rasters are regenerable and gitignored like the existing ones.
- **[Risk] A 0.5 ha minimum mapping unit drops small real clearings** → The Paraguayan definition does not count sub-0.5 ha patches as forest anyway, so they are not forest loss under the definition the project is measured against.
