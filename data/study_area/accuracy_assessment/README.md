# Accuracy assessment — reference data and labeling protocol

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
| `heldout_<region>_map.csv` | what the CNN predicted at each held-out point | **No** |
| `aoi_repeat.csv`, `aoi_adjudication.csv` | blind repeat of a 10% subset and the resolved disagreements | after the first pass |

Opening a "No" file before labeling is finished breaks the blindness the whole assessment relies
on. If it happens, note it here; don't hide it.

## Imagery coverage (task 1.2 — to fill in)

Check in Google Earth Pro (clock icon / time slider) and in Esri World Imagery Wayback whether
there is imagery from the same year for each area. Planet NICFI: the project's service account has
no access and the program's contract with Planet ended in 2025, so it is not relied on (checked
2026-09-24).

| Area | 2019 (source, dates) | 2023 (source, dates) | Notes |
|---|---|---|---|
| AOI (Corazón Verde) | | | |
| Filadelfia | — | | 2023 only |
| Bahía Negra | — | | 2023 only |
| Pozo Colorado | — | | 2023 only |

## Labeling protocol

**The question per point and date: is this pixel forest under Paraguay's definition?**
Forest = a woody patch of **at least 0.5 ha**, with **at least 25% tree crown cover**, of trees that
can reach **5 m**. The yellow square in the KML is 0.5 ha (~71 × 71 m) centered on the point.

1. Open the KML in Google Earth Pro. Go to the point (double-click its name).
2. Set the time slider to imagery from the year being labeled (2019 or 2023). Prefer the dry season
   (June-September, the same window as the Sentinel-2 composites) when there is a choice.
3. Look at the point and its square, zooming out if needed for context:
   - `forest`: the point sits inside a woody patch that meets all three thresholds. The patch may
     extend beyond the square; it just has to be ≥ 0.5 ha in total.
   - `nonforest`: pasture, crop, bare soil, water, or woody vegetation below 25% cover or in a patch
     smaller than 0.5 ha.
4. Fill in the CSV row: `label_<year>` (`forest` / `nonforest`), `imagery_source_<year>`
   (`google_earth` / `esri_wayback` / other), `imagery_date_<year>` (as shown by the source).
5. `flag_sparse_woody`: `yes` when the point is on open or scattered woody vegetation (palm
   savanna, open woodland) that you judged below 25% cover, or a woody patch under 0.5 ha. This is
   how the share of the classifier's "bosque" that falls outside the Paraguayan definition gets
   measured.
6. Can't tell (no same-year imagery, clouds, too blurry)? Leave `label_<year>` **empty** and write
   why in `uninterpretable_reason`. Never guess: an empty label is excluded and counted, a guess
   silently biases the result.
7. `notes`: anything uncertain ("edge of a clearing", "burn scar?", "flooded").

Label the 2019 and 2023 of the same point one after the other, in the same view. Don't look up the
model's output, MapBiomas or Hansen for a point while labeling it.

**Give the two dates different labels only when you can see the change itself** (a clearing
appears, regrowth closes in). If the place looks the same in both images, both labels must be the
same, even if you hesitate on which one it is. Why this matters: most points sit in the large
stable-forest stratum (~17,500 ha), so a single point wrongly labeled forest→non-forest is read as
real deforestation scaled up by that stratum's size. In a dry run with random labeling noise of
~7% per date, the estimated loss went from 82 ha mapped to ~2,570 ha, entirely from noise.

### Worked examples (to fill in before labeling starts, at least 3 per class)

| Example | Class | Imagery date | Why |
|---|---|---|---|
| | forest | | |
| | nonforest (pasture) | | |
| | nonforest (sparse woody, flagged) | | |

## Consistency check (blind repeat)

After the first pass, `aoi_repeat.csv` gets a random 10% of the points with empty labels. A second
person labels them (preferred), or the same person at least 14 days later, without looking at the
first pass. Disagreements go into `aoi_adjudication.csv` with columns
`point_id,date,first_label,repeat_label,adjudicated_label,reason`. The final numbers use the
adjudicated labels.

## Running the assessment

```bash
.venv/bin/python scripts/28_assess_aoi_accuracy.py         # AOI: per-date gate + error-adjusted areas
.venv/bin/python scripts/30_assess_heldout_accuracy.py assess  # held-out regions
```

## Results
