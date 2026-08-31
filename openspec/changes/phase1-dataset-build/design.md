## Context

See `proposal.md` - Why. This design covers how the Sentinel-2 + MapBiomas dataset gets built over the AOI (and a wider Chaco sampling footprint) via Google Earth Engine, and specifically how Sentinel-2's 10m native resolution gets reconciled with MapBiomas's 30m native resolution (Landsat-derived) — a resolution mismatch that has to be resolved before any patch/label pair can be produced.

## Goals / Non-Goals

**Goals:**
- Produce label-aligned Sentinel-2 patches over the AOI and a wider Chaco footprint without discarding Sentinel-2's native spatial detail.
- Keep the held-out generalization sub-region and the ESA WorldCover accuracy cross-check fully separate from training data, decided during dataset construction rather than left implicit.
- Make the cloud-coverage/SAR decision an explicit, evidence-based step rather than an upfront assumption.

**Non-Goals:**
- No model training or architecture decisions (CNN, Random Forest) — those belong to the next change, which consumes this dataset's output.
- No canopy-height/GEDI work — that's a separate carbon-estimation change.
- No attempt to produce label supervision finer than MapBiomas's native 30m — the resolution-matching decision below preserves spatial detail as model input, it does not invent finer ground truth than exists.

## Decisions

**3x3 Sentinel-2 patch per MapBiomas pixel, not resampling Sentinel-2 down to 30m.** MapBiomas is Landsat-derived at 30m; Sentinel-2 is 10m — an exact 3:1 ratio per axis, so each MapBiomas pixel maps cleanly to a 3x3 block of Sentinel-2 pixels.

- *Alternative considered: resample/aggregate Sentinel-2 down to a single 30m value per MapBiomas pixel (e.g. average the 3x3 block), producing a direct 1:1 pixel-to-label match.* Simpler pipeline, but throws away exactly the spatial detail that motivated choosing Sentinel-2 over Landsat in the first place — the dataset's final output resolution would be no better than Landsat's, undercutting the 10m-vs-30m precision argument already used to justify the source choice (`docs/PIPELINE.md`, "Why these sources").
- *Chosen: keep each Sentinel-2 pixel in the 3x3 block at native resolution, tagging the whole block with the single MapBiomas label it falls under.* The classifier (next change) then trains on 3x3xC-band patches rather than single-pixel vectors, letting it use intra-block texture and edges as signal even though the label itself is still only as fine as MapBiomas allows. This does not create finer supervision than MapBiomas provides — it's still one label per 30m block — but it stops discarding information that's useful to a texture-sensitive model like a CNN, and keeps the door open to later inference at finer effective granularity if that's ever validated (out of scope here).
- This choice is consistent with why ESA WorldCover is used as a *separate*, held-out 10m cross-check rather than blended into training (`training-dataset` spec, "Independent accuracy cross-check"): 30m-anchored supervision is a known limitation of MapBiomas, not something this patch scheme claims to fix, and WorldCover is what actually tests whether finer-than-30m accuracy is happening.

**Refinement found during task 6.1 (patch/tile format): CNN input patch is 33x33 pixels, not literally 3x3.** The 3x3 block above is the *label-alignment* unit (which S2 pixels correspond to one MapBiomas cell), not necessarily the CNN's input size. A literal 3x3xC input (9 pixels) barely allows one meaningful convolution and would undercut the CNN-vs-RF test this thesis runs — a CNN needs real spatial context to have a chance of outperforming a per-pixel/small-window classifier, otherwise the comparison isn't fair. Each training example is now: a 33x33-pixel Sentinel-2 window (roughly 330m x 330m, centered on the 3x3 label block) as input, single MapBiomas-derived class as the label for the center block. 33 chosen so the center 3x3 block sits at the exact middle of the window (a common patch size in Sentinel-2 CNN classification literature). This does not change the resolution-matching decision above — it only changes how much surrounding context the network sees per label.

**Wider Chaco sampling footprint, not AOI-only.** Both MapBiomas and GEDI already have Chaco-wide coverage, so composites and labels are built over a footprint larger than the ~20,589 ha case-study AOI, with a designated held-out sub-region reserved for the generalization check already planned in `phase5-predictive-model`'s design. This is a sampling decision at dataset-build time, not a new data source or new infrastructure.

**Cloud-coverage assessment before deciding on Sentinel-1 SAR.** Rather than assuming the Chaco's wet season leaves unacceptable optical gaps (a possibility flagged but not decided in `docs/PIPELINE.md`), this change measures actual cloud coverage over the chosen periods first and only adds SAR if the measured gaps warrant it.

**3 per-date CNN classes (bosque/pasto/cultivo), "desmonte" derived via temporal comparison, not trained directly.** Discovered during implementation: MapBiomas Chaco Collection 5's real legend (chaco.mapbiomas.org/en/legend-codes/, distinct from the standard Brazil/Amazon MapBiomas legend) has no "recently cleared" class — it classifies land cover state per year, not clearing events. `docs/PIPELINE.md` had imprecisely described the CNN as training on "4 classes: bosque/pasto/desmonte/cultivo," implying desmonte was a per-date CNN output.

- *Alternative considered: treat MapBiomas's non-vegetated/bare-soil codes (22-25, "Área sin vegetación") as a proxy "desmonte" class, giving the CNN 4 direct per-date outputs.* Plausible — freshly cleared land is visually distinct (bare soil) before pasture grass establishes — but conflates "bare and not yet revegetated" with "recently deforested by human clearing," which aren't the same thing in a semi-arid biome (natural bare patches, salt flats, etc. also fall in that code range).
- *Chosen: the CNN classifies 3 solid per-date classes; "desmonte" is computed downstream as bosque(t1) → not-bosque(t2), consistent with `docs/FOUNDATION.md` point 4 ("classify two or more points in time and produce a change map").* Matches how the rest of the pipeline already treats temporal change (the whole `CHANGE` node in `docs/PIPELINE.md`'s diagram), and doesn't require the CNN to learn a class MapBiomas can't reliably supervise in the first place.
- **Critical remap detail**: MapBiomas Chaco's code 15 ("Pastura," anthropogenic managed pasture) is a different category from codes 11/12/42/43/44 ("Pastizal," natural non-wooded grassland/savanna) — the Spanish names are easy to conflate but MapBiomas puts them in different top-level categories (agricultural vs. natural vegetation). Only code 15 maps to "pasto"; the "Pastizal" codes are grouped as OTHER (excluded), see `scripts/mapbiomas_legend.py`.
- **Real finding, not assumed**: the AOI has zero "cultivo" pixels in both 2019 and 2023 (confirmed via `scripts/visualize_mapbiomas_labels.py`) — its land-use dynamic is bosque↔pastura, not bosque↔cropland. This makes the wider-Chaco sampling footprint (already decided, see "Decisions" above) a hard requirement for the cultivo class to have any training examples at all, not just a generalization nice-to-have.

## Risks / Trade-offs

- **[Risk] 3x3 patches increase the training set's effective input size (9x the pixels per label) without increasing label information, which could invite overfitting on texture noise rather than genuine class signal.** → Mitigation: this is exactly what the ESA WorldCover held-out cross-check and the Chaco sub-region generalization check are for — both test whether the model is learning real signal, not the patch scheme's noise.
- **[Risk] MapBiomas label misalignment or reprojection error at the pixel level could put the wrong 3x3 Sentinel-2 block under a given label.** → Mitigation: verify alignment against a known reference (e.g. spot-check known forest/pasture boundaries) before building the full dataset, not just at final QA.
- **[Trade-off] Building over a wider Chaco footprint (for the generalization check) costs more Earth Engine compute/quota than an AOI-only dataset.** Accepted: the Community-tier GEE quota already in use (150 EECU-hours/month, no billing account) should cover this, but worth monitoring during implementation rather than assuming headroom.

## Migration Plan

Not applicable — this is a new dataset-build pipeline, no existing data or code it replaces.
