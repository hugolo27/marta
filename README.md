# **Monitoring & Auditable Reporting for Transparent Accounting**

*Languages: **English** | [Español](README.es.md)*

Final Master's Project (TFM) for the Master's Degree in Artificial Intelligence and Data Analysis (MIAyCD), Polytechnic School, Universidad Nacional de Asunción (UNA).

## About the project

MARTA classifies land cover (forest / pasture / clearing / crop) over Sentinel-2 imagery of the Paraguayan Chaco using a CNN, and adds interpretability (Grad-CAM) so every prediction is auditable instead of a black box. It applies to the monitoring (MRV) context of REDD+ projects in the carbon credit market.

The full framing (research question, objectives, scope and out-of-scope) is in [`docs/FOUNDATION.md`](docs/FOUNDATION.md).

## Repository structure

```
├── data/
│   └── study_area/         # study area boundary (GeoJSON) — the one versioned exception under data/
├── docs/
│   └── FOUNDATION.md       # project framing
├── openspec/                # specs and change proposals (OpenSpec methodology)
└── research_docs/           # private research notes (not versioned)
```

## Useful links

**Data sources**
- [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/) — Sentinel-2 imagery
- [MapBiomas Chaco](https://chaco.mapbiomas.org/en/collection-maps/) — land cover ground truth
- [ESA WorldCover](https://esa-worldcover.org/en/data-access) — independent 10m land cover cross-check
- [ETH Global Canopy Height](https://www.research-collection.ethz.ch/handle/20.500.11850/609802) — pretrained canopy height model (Lang et al. 2023)
- [NASA Earthdata Login](https://urs.earthdata.nasa.gov/) — GEDI L4A access
- [Google Earth Engine signup](https://signup.earthengine.google.com/) — noncommercial/academic track

**Reference**
- [Corazón Verde del Chaco, Verra Registry (VCS 2611)](https://registry.verra.org/app/projectDetail/VCS/2611) — the case-study project used in the audit demo

**Tools**
- [geojson.io](https://geojson.io/) — paste `data/study_area/aoi.geojson` here for an instant map view of the study area, no install/login needed

## Working methodology

Non-trivial changes (data pipeline, model architecture, scope) are documented as proposals following [OpenSpec](https://openspec.dev) before implementation: each one lives as `proposal.md` + `design.md` + specs + `tasks.md` under `openspec/changes/`, and once completed moves to `openspec/specs/` as the current reference. The intent is that the tutor can follow progress through these proposals, not just through commit history.

## License

All rights reserved. This repository is public solely for transparency and academic review purposes, not for reuse.
