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

## Working methodology

Non-trivial changes (data pipeline, model architecture, scope) are documented as proposals following [OpenSpec](https://openspec.dev) before implementation: each one lives as `proposal.md` + `design.md` + specs + `tasks.md` under `openspec/changes/`, and once completed moves to `openspec/specs/` as the current reference. The intent is that the tutor can follow progress through these proposals, not just through commit history.

## License

All rights reserved. This repository is public solely for transparency and academic review purposes, not for reuse.
