## Context

`phase1-classifier` (archived) trains RF and CNN fresh inside every script that needs them — no script persists a trained model to disk, since each prior use case (the 5-seed comparison, each held-out region check) only ever needed a model for the duration of one run. This change is the first one that needs the *same* trained model applied twice, to two different dates, and diffed — introducing a real correctness requirement that didn't exist before: retraining independently per date would mean any difference between the two dates' classifications partly reflects training-run variance (already measured at std ≈ 0.01-0.02 macro-F1 across seeds, `phase1-classifier` tasks 4.1), not real land-cover change, contaminating the change map with model noise.

`scripts/13_visualize_classification_map.py` already does dense per-pixel CNN inference over a tile using row-chunked sliding windows (built and code-reviewed in `phase1-classifier`), and `scripts/06_align_3x3_patches.py` already demonstrates the exact 3x3/33x33 alignment on the single-UTM-zone AOI. This change reuses both rather than rebuilding dense inference from scratch.

## Goals / Non-Goals

**Goals:**
- Produce one change map over the case-study AOI, from one trained CNN applied consistently to both dates.
- Reuse existing dense-inference and AOI-composite-building code rather than duplicating it.
- Report transition statistics with an independent sanity check (MapBiomas), not just trust the diff.

**Non-Goals:**
- No retraining or re-evaluating the classifier itself — `phase1-classifier`'s operational-classifier decision is settled and out of scope here.
- No dense inference over the full 3-department training footprint — only the AOI (Corazón Verde del Chaco), which is the actual Fase 4 audit target. A 24M-ha dense raster is unnecessary for this change and would be a very different (and much more expensive) undertaking.
- No carbon/CO2e conversion — that is Fase 2, consuming this change's output, not part of it.

## Decisions

**Train the CNN once, persist the checkpoint, reuse it for both dates.** A fixed seed (42, matching the seed already used as the default/reference throughout `phase1-classifier`) trains one `SmallCNN` instance via `scripts/10_train_cnn.py`'s existing `train()` function; its weights are saved to a checkpoint file (`.pt`, already covered by `.gitignore`) instead of being discarded at the end of the script, and both dates' dense inference load that same checkpoint. This is a new pattern for this codebase — every prior script trained transiently — but is required here specifically because this is the first capability that classifies more than one date with what must be the same decision boundary.

**Dense inference reuses `13_visualize_classification_map.py`'s row-chunked sliding-window approach, run once per date.** Same reasoning as that script's own design: materializing all sliding windows for a tile at once is memory-prohibitive; row-chunked processing already solved this and passed code review. Not reinvented here.

**Composite building uses `reproject=True` (the default), not `False`.** Unlike `phase1-classifier`'s 3-department training footprint (which spans UTM 20S/21S, requiring `reproject=False`), the case-study AOI sits entirely within a single UTM zone — the same condition `06_align_3x3_patches.py` already relies on. Using the multi-zone-safe default here would be needless caution; using the single-zone-appropriate `clip=True` (to bound the composite to the AOI polygon, avoiding any risk of pulling pixels from outside it) is still applied, matching the round-6 finding from `phase1-classifier` about unclipped composites.

**Change map encodes named transitions, not a binary changed/unchanged flag.** A binary flag would lose exactly the information Fase 2 needs (carbon estimation depends on which transition happened, since bosque→cultivo and bosque→pasto carry different carbon-density deltas). Every pixel gets one of: no-change, or one of the 6 ordered pairwise transitions among {bosque, pasto, cultivo}.

**A pixel unclassifiable in either date is excluded from the change map, not imputed.** Matches `phase1-classifier`'s established norm (never classify a masked/fabricated pixel, round 1-2 findings) — a residual cloud gap in one date means that pixel's transition status is genuinely unknown, not a default "no change."

**The MapBiomas cross-check is a sanity check on the diff, not a validation of the classifier itself.** `phase1-classifier` already validated the classifier's accuracy; this check exists to catch a different failure mode — a classifier that's individually accurate on each date but flips between two visually-similar classes (bosque/pasto confusion, already the dominant error pattern per `phase1-classifier` tasks 2.2/3.3) inconsistently between dates, producing spurious "transitions" that are actually just noise. Comparing against MapBiomas' own year-over-year class change at the same pixels catches this without re-litigating per-date accuracy.

## Risks / Trade-offs

- **[Risk] The single trained CNN checkpoint might itself sit on an unlucky seed, given the already-measured std ≈ 0.01-0.02 across seeds.** → Mitigation: seed 42 is already the reference seed used throughout `phase1-classifier`'s per-task single-run numbers (tasks 2.2/3.3) and the first of its 5-seed comparisons — using it here keeps this change's output comparable to those already-reported numbers, rather than introducing a new, unvalidated seed choice.
- **[Risk] Persisting a model checkpoint is a new artifact type for this repo (no prior script does this) — could be forgotten in `.gitignore` or accidentally treated as reproducible-from-scratch.** → Mitigation: `.gitignore` already covers `*.pt`/`*.pth`/`*.ckpt` (added early in the project, unused until now) and the checkpoint's provenance (seed, architecture, training data) is fully reproducible by rerunning `10_train_cnn.py` with the documented seed if the file is ever lost — not a hidden, unrecoverable dependency.
- **[Trade-off] Restricting dense inference to the AOI instead of the full training footprint means this change cannot validate its own change-detection approach on the held-out regions (Filadelfia, Bahia Negra, Pozo Colorado).** Accepted: those regions' role was generalization testing for the classifier itself, already closed; re-litigating that here would be scope creep, not new information.
