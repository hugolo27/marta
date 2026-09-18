# Documento del TFM (Typst)

Borrador del documento final, a pedido del tutor (usar Typst en vez de Word/LaTeX).
Reemplaza gradualmente a `docs/TFM_DRAFT.md` (gitignored, ya no se actualiza) a medida
que se migra contenido.

**Estado: esqueleto inicial, estructura genérica.** El formato oficial de anteproyecto
sigue el "Manual de Postgrado" del Rectorado (FP-UNA) — todavía no está en el repo. Ajustar
portada, estructura de capítulos y normas de citado apenas esté disponible.

## Compilar

```bash
typst compile thesis/main.typ thesis/main.pdf
```

Vista previa en vivo mientras se edita:

```bash
typst watch thesis/main.typ thesis/main.pdf
```

## Estructura

- `main.typ` — portada, índice, incluye los capítulos, bibliografía al final.
- `capitulos/01_introduccion.typ` — adaptado de `docs/FOUNDATION.es.md`.
- `capitulos/02_metodologia.typ` — adaptado de `docs/METODOLOGIA_PIPELINE.md` secciones 1-3.1.
- `capitulos/03_resultados_fase1.typ` — migrado y actualizado de `docs/TFM_DRAFT.md` (que
  quedó desactualizado: mencionaba Grad-CAM y comparación temporal como pendientes, ya
  están hechos; contaba 8 rondas de revisión, son 9).
- `capitulos/04_proximos_pasos.typ` — tabla de estado por fase.
- `referencias.bib` — solo entradas con datos bibliográficos verificados. Hay un TODO con
  las que faltan verificar antes de citar (no inventar autor/DOI/año).

## Pendiente

- Nombre real del tutor y fecha de presentación: la portada tiene placeholders
  (`[completar]`) — este repo no nombra al tutor fuera de `README.md`, así que completar
  eso a mano en la copia final antes de enviar, no en este archivo versionado.
- Sección de resultados de Fase 2, 3, 4 a medida que existan.
- Resultado de la barrida de hiperparámetros (`data/study_area/hyperparameter_sweep_results.json`)
  una vez corrida — hay un TODO marcado en el capítulo de resultados.
