## Why

Every downstream capability in Fase 1 — the CNN classifier, the Random Forest baseline, Grad-CAM, and the temporal comparison — needs a dataset of Sentinel-2 imagery paired with MapBiomas Chaco labels over the AOI to train and evaluate on. Nothing there can start without it, and it's the first unblocked piece of implementation work now that `phase1-define-study-area` has a validated AOI (technically GO — GEDI feasibility passed, area sanity-checked against the official PD — with only the tutor's formal sign-off still pending, tracked separately and not a blocker for building this).

## What Changes

- Build a training/evaluation dataset by pulling Sentinel-2 L2A imagery and MapBiomas Chaco land cover labels over the AOI via Google Earth Engine (credentials already configured — service account, `.env` variables verified working).
- Compose cloud-free Sentinel-2 composites (13 bands + spectral indices) for at least two time periods, sufficient for both classifier training and the later temporal change comparison.
- Extract MapBiomas Chaco labels (4 target classes: bosque/pasto/desmonte/cultivo) spatially aligned to the same Sentinel-2 pixels/patches.
- Extract ESA WorldCover (10m) over a held-out evaluation area, kept separate from training labels, as an independent accuracy cross-check — not blended into training data, to avoid train/eval circularity.
- Deliberately sample the training footprint wider than the single case-study AOI (both MapBiomas and GEDI have Chaco-wide coverage), so a later generalization check against a held-out Chaco sub-region is possible without a second data-collection effort.
- Assess real cloud coverage over the AOI/sampling footprint for the chosen periods, and decide during this change (not assume upfront) whether Sentinel-1 SAR is needed to fill gaps.
- Define the dataset's output format: patch/tile size, train/val/test split, and how the generalization held-out sub-region is chosen.

## Capabilities

### New Capabilities
- `training-dataset`: the Sentinel-2 + MapBiomas Chaco dataset (imagery composites, aligned labels, held-out WorldCover cross-check, patch format and splits) that the classifier, baseline, and temporal comparison all consume.

### Modified Capabilities
(none)

## Impact

- New Google Earth Engine-based data pipeline code (not yet written — this change is planning only).
- Consumes the AOI artifact from `phase1-define-study-area` (`data/study_area/aoi.geojson`) as its geographic boundary.
- Depends on the AOI being treated as stable. Its tutor sign-off (`phase1-define-study-area` task 5.1) is now confirmed — the AOI is final.
- Produces the direct input the not-yet-created CNN/Random Forest/Grad-CAM change and the not-yet-created carbon-estimation change (canopy height + GEDI calibration) will both need.
- No model training happens in this change — it only produces the dataset those changes will consume.
