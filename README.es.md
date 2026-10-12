# **Monitoring & Auditable Reporting for Transparent Accounting**

*Idiomas: [English](README.md) | **Español***

Trabajo Final de Maestría (TFM) para la Maestría en Inteligencia Artificial y Análisis de Datos (MIAyCD), Facultad Politécnica, Universidad Nacional de Asunción (UNA).

## Sobre el proyecto

MARTA clasifica cobertura de suelo (bosque / pasto / cultivo por fecha; el desmonte se deriva comparando dos fechas) sobre imágenes Sentinel-2 del Chaco paraguayo usando una CNN, y suma interpretabilidad (Grad-CAM) para que cada predicción sea auditable en vez de una caja negra. Aplica al contexto del monitoreo (MRV) de proyectos REDD+ en el mercado de créditos de carbono.

El planteamiento completo (pregunta de investigación, objetivos, alcance y fuera de alcance) está en [`docs/FOUNDATION.es.md`](docs/FOUNDATION.es.md).

## Estructura del repositorio

```
├── data/
│   └── study_area/         # boundary del área de estudio (GeoJSON) — la única excepción versionada bajo data/
├── docs/
│   └── FOUNDATION.md       # planteamiento del proyecto
├── openspec/                # specs y propuestas de cambio (metodología OpenSpec)
└── research_docs/           # notas de investigación privadas (no versionadas)
```

## Enlaces útiles

**Fuentes de datos**
- [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/) — imágenes Sentinel-2
- [MapBiomas Chaco](https://chaco.mapbiomas.org/en/collection-maps/) — cobertura de suelo (ground truth)
- [ESA WorldCover](https://esa-worldcover.org/en/data-access) — chequeo de accuracy independiente, 10m
- [ETH Global Canopy Height](https://www.research-collection.ethz.ch/handle/20.500.11850/609802) — modelo pretrained de altura de dosel (Lang et al. 2023)
- [NASA Earthdata Login](https://urs.earthdata.nasa.gov/) — acceso a GEDI L4A
- [Registro Google Earth Engine](https://signup.earthengine.google.com/) — track noncommercial/académico

**Referencia**
- [Corazón Verde del Chaco, Verra Registry (VCS 2611)](https://registry.verra.org/app/projectDetail/VCS/2611) — proyecto caso de estudio de la demo de auditoría

**Herramientas**
- [geojson.io](https://geojson.io/) — pegar `data/study_area/aoi.geojson` ahí para ver el área de estudio en un mapa al instante, sin instalar ni loguearse

## Metodología de trabajo

Los cambios no triviales (pipeline de datos, arquitectura del modelo, alcance) se documentan como propuestas siguiendo [OpenSpec](https://openspec.dev) antes de implementarse: cada una queda como `proposal.md` + `design.md` + specs + `tasks.md` en `openspec/changes/`, y al completarse pasa a `openspec/specs/` como referencia vigente. La intención es que el seguimiento del tutor pueda hacerse sobre estas propuestas, no solo sobre el historial de commits.

## Licencia

Todos los derechos reservados. El repositorio es público únicamente con fines de transparencia y revisión académica, no de reutilización.
