# Accuracy assessment: reference data and labeling protocol

Change: `openspec/changes/phase1-accuracy-assessment/`. This folder holds the independent reference
data the classifier is scored against: points interpreted by a person on high-resolution imagery,
blind to what the model said. It is archived here (versioned) so anyone can re-check a point, as
VM0007 requires of the case-study project's own monitoring.

## Files

| File | What it is | Open while labeling? |
|---|---|---|
| `aoi_sample.csv` | AOI points to interpret, 2019 and 2023 | **Yes**, this is where labels go |
| `aoi_sample.kml` | same points + a 0.5 ha square each, for Google Earth Pro | **Yes** |
| `heldout_<region>_sample.csv` / `.kml` | held-out points, 2023 only | **Yes** |
| `aoi_sample_design.csv`, `heldout_<region>_sample_design.csv` | sampling stratum and inclusion probability per point | **No**: the stratum is a map label |
| `aoi_sample_strata.json` | stratum sizes and map-class areas | **No** |
| `heldout_<region>_map.csv` | what the CNN predicted at each held-out point | **No** |
| `aoi_repeat.csv`, `aoi_adjudication.csv` | blind repeat of a 20% subset and the resolved disagreements | after the first pass |

Opening a "No" file before labeling is finished breaks the blindness the whole assessment relies
on. If it happens, note it here; don't hide it.

## Imagery coverage (task 1.2, to fill in)

Check in Google Earth Pro (clock icon / time slider) and in Esri World Imagery Wayback whether
there is imagery from the same year for each area. Planet NICFI: the project's service account has
no access and the program's contract with Planet ended in 2025, so it is not relied on (checked
2026-09-24).

| Area | 2019 (source, dates) | 2023 (source, dates) | Notes |
|---|---|---|---|
| AOI (Corazón Verde) | | | |
| Filadelfia | n/a | | 2023 only |
| Bahía Negra | n/a | | 2023 only |
| Pozo Colorado | n/a | | 2023 only |

## Labeling protocol

The AOI sample was redrawn on 2026-10-03 (340 points, six strata) before anything was labeled; the
first draw is in git history only. Strata are deliberately not explained here, so this file can stay
open while labeling.

**Two definitions, one interpretation.** The primary label follows the case-study PD's definition
(Paraguay's CDM definition): forest = a woody patch of **at least 0.5 ha**, with **at least 25% tree
crown cover**, of trees that can reach **5 m**. Paraguay's FREL uses a wider definition for the
Región Occidental (≥ 10% crown, ≥ 1 ha, ≥ 3 m; strips only if ≥ 60 m wide). You don't label twice:
you record the attributes below and the FREL label is computed from them. The primary definition was
fixed before labeling and is not changed after seeing results.

The yellow square in the KML is 0.5 ha (~71 × 71 m) centered on the point, with a 5×5 grid of small
crosses inside it. Each cross stands for 4% of the square.

1. Open the KML in Google Earth Pro. Go to the point (double-click its name).
2. Set the time slider to imagery from the year being labeled (2019 or 2023). When there is a
   choice, prefer leaf-on imagery (wet season, roughly November-April): the Chaco forest drops much
   of its foliage in the dry season and would read as less crown than it has.
3. Record, for that date:
   - `crown_<year>`: count the crosses that sit on tree crown. 0-2 → `lt10`; 3-6 → `10to25`;
     7 or more → `ge25`. If the count is 2-3 or 6-7, also set `near_threshold_<year>` = `yes`.
   - `patch_<year>` (skip if `crown` is `lt10`): size of the whole woody patch the point sits in,
     zooming out as needed: `lt0.5`, `0.5to1` or `ge1` ha (1 ha ≈ 100 × 100 m).
   - `height_<year>` (skip if `crown` is `lt10`): `ge5`, `3to5`, `lt3` or `indeterminate`. Height
     can rarely be judged on imagery (shadows, crown size); `indeterminate` is the honest default and
     counts as meeting the 5 m potential. This is declared as a limitation.
   - `narrow_strip_<year>`: `yes` if the woody patch is a strip narrower than 60 m (windbreaks,
     riparian strips).
   - `label_<year>`: `forest` only if crown is `ge25`, patch is `0.5to1` or `ge1`, and height is
     `ge5` or `indeterminate`; otherwise `nonforest`. The assessment script refuses to run if a label
     contradicts its attributes.
   - `imagery_source_<year>` (`google_earth` / `esri_wayback` / other) and `imagery_date_<year>`.
4. Can't tell (no same-year imagery, clouds, too blurry)? Leave `label_<year>` **empty** and write
   why in `uninterpretable_reason`. Never guess: an empty label is excluded and counted, a guess
   silently biases the result.
5. `notes`: anything uncertain ("edge of a clearing", "burn scar?", "flooded").

Label the 2019 and 2023 of the same point one after the other, in the same view. Don't look up the
model's output, MapBiomas or Hansen for a point while labeling it.

**Give the two dates different labels only when you can see the change itself** (a clearing
appears, regrowth closes in). If the place looks the same in both images, both labels must be the
same, even if you hesitate on which one it is. Why this matters: most of the AOI is stable forest
(~16,400 ha), so a single point wrongly labeled forest→non-forest is read as real deforestation
scaled up by that stratum's size. In a dry run with random labeling noise of ~5-7% per date, the
estimated loss went from 82 ha mapped to roughly 1,800-2,600 ha, entirely from noise.

### Worked examples (to fill in before labeling starts, at least 3 per class)

| Example | Class | Imagery date | Why |
|---|---|---|---|
| | forest (crown ge25, patch ≥ 0.5 ha) | | |
| | nonforest (pasture, crown lt10) | | |
| | nonforest (woody, crown 10to25: FREL forest, not CDM) | | |
| | nonforest (narrow windbreak) | | |

## Consistency check (blind repeat)

After the first pass, `aoi_repeat.csv` gets a random 20% of the points with empty fields
(`27_draw_reference_sample.py repeat`). A second person labels them (preferred: the main interpreter
also built the classifier), or the same person at least 14 days later, in shuffled order, without
looking at the first pass. Disagreements go into `aoi_adjudication.csv` with columns
`point_id,date,label,crown,patch,height,near_threshold,narrow_strip,reason` (only the fields that
change need a value). The final numbers use the adjudicated records.

The FREL wording comes from the 2016 FREL submission, section 2.3 ("Definición de bosque nativo"),
read through a text extraction; check it and its page against the original PDF before citing it
(task 1.4).

## Running the assessment

```bash
.venv/bin/python scripts/28_assess_aoi_accuracy.py         # AOI: per-date gate + error-adjusted areas
.venv/bin/python scripts/30_assess_heldout_accuracy.py assess  # held-out regions
```

## Results
