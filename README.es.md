# **Monitoring & Auditable Reporting for Transparent Accounting**

*Idiomas: [English](README.md) | **Español***

Trabajo Final de Maestría (TFM) para la Maestría en Inteligencia Artificial y Análisis de Datos (MIAyCD), Facultad Politécnica, Universidad Nacional de Asunción (UNA).

## Sobre el proyecto

MARTA clasifica cobertura de suelo (bosque / pasto / desmonte / cultivo) sobre imágenes Sentinel-2 del Chaco paraguayo usando una CNN, y suma interpretabilidad (Grad-CAM) para que cada predicción sea auditable en vez de una caja negra. Aplica al contexto del monitoreo (MRV) de proyectos REDD+ en el mercado de créditos de carbono.

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

## Metodología de trabajo

Los cambios no triviales (pipeline de datos, arquitectura del modelo, alcance) se documentan como propuestas siguiendo [OpenSpec](https://openspec.dev) antes de implementarse: cada una queda como `proposal.md` + `design.md` + specs + `tasks.md` en `openspec/changes/`, y al completarse pasa a `openspec/specs/` como referencia vigente. La intención es que el seguimiento del tutor pueda hacerse sobre estas propuestas, no solo sobre el historial de commits.

## Licencia

Todos los derechos reservados. El repositorio es público únicamente con fines de transparencia y revisión académica, no de reutilización.
