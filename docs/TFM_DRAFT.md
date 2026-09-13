# MARTA — Borrador de resultados para el TFM (Fase 1: clasificación de cobertura)

**Estado: borrador vivo, no definitivo.** Este documento adapta al formato de resultados que
espera el documento final del TFM el material que ya vive, más técnico y más largo, en
`docs/METODOLOGIA_PIPELINE.md` (referencia por sección) y en las tareas de
`openspec/changes/phase1-classifier/` (registro completo de cada corrida y cada revisión de
código). Última actualización: 2026-09-13 — decisión de clasificador operativo cerrada.

## 1. Resumen ejecutivo

Se comparó un clasificador Random Forest (baseline, per-píxel) contra una CNN chica y propia
(candidata, con contexto espacial de 33×33 píxeles) para distinguir bosque, pasto y cultivo sobre
Sentinel-2, usando MapBiomas Chaco Colección 5 como etiqueta. La comparación se hizo bajo un
criterio de significancia fijado antes de ver resultados (5 corridas con semillas distintas, F1
macro, margen de una desviación estándar combinada), y se extendió con una evaluación de
generalización geográfica sobre 3 sub-áreas held-out de paisajes distintos, cada una también con 5
corridas para tener varianza real.

**Resultado**: la CNN gana la comparación de precisión sobre el AOI, y gana o empata en 2 de las 3
sub-áreas held-out independientes — pierde claramente solo en una (Filadelfia, Boquerón), con una
causa identificada y específica de paisaje, no una falla de generalización sin explicar. **La CNN
queda confirmada como clasificador operativo de MARTA**, con esa limitación documentada
explícitamente.

## 2. Metodología de la comparación

- **Random Forest**: 400 árboles, sin límite de profundidad, entrenado sobre 13 canales por
  píxel (12 bandas Sentinel-2 + NDVI) tomados del centro de cada patch.
- **CNN (`SmallCNN`)**: arquitectura propia y chica (3 bloques convolucionales 32/64/128 filtros +
  pooling global + dropout 0,4), no un backbone pre-entrenado — para que la comparación sea
  honesta sobre datos de este proyecto, y para no oscurecer una futura capa de interpretabilidad
  (Grad-CAM, todavía no implementada).
- **Criterio de victoria, fijado antes de entrenar**: ambos modelos se entrenan y evalúan 5 veces
  con semillas distintas; la CNN solo cuenta como ganadora si su F1 macro promedio supera al de
  Random Forest en más de una desviación estándar combinada entre ambas distribuciones de
  corridas. Detalle completo en `docs/METODOLOGIA_PIPELINE.md`, sección 3.1.
- **Volumen de entrenamiento**: 400 ejemplos por clase y período (2.393 patches en total),
  escalado desde 200 durante el desarrollo específicamente para probar si la comparación era
  sensible al volumen de datos — lo fue en estabilidad de proceso (ver sección 6), no en la
  conclusión final.

## 3. Resultados: comparación de precisión sobre el AOI

Sobre el conjunto de prueba del área de estudio (~360 ejemplos, nunca usados en entrenamiento ni
ajuste), promediando 5 corridas con distinta semilla:

| Modelo | F1 macro promedio | Desviación estándar |
|---|---|---|
| Random Forest | 0,811 | 0,004 |
| CNN | 0,843 | 0,012 |

La diferencia (+0,032) supera el umbral pre-registrado (0,009). Por el criterio fijado de
antemano, **la CNN gana esta comparación**. Ambos modelos muestran el mismo patrón de error: la
confusión entre pasto y cultivo es sistemáticamente mayor que la confusión de cualquiera de las
dos con bosque — una limitación de qué distingue el sensor, no del modelo.

## 4. Resultados: evaluación de generalización geográfica

El AOI por sí solo no prueba generalización — sus ejemplos de prueba salen de la misma huella de
entrenamiento. Se evaluaron ambos modelos contra 3 sub-áreas geográficamente excluidas por
completo del entrenamiento, elegidas con topologías de paisaje distintas a propósito, cada una con
5 corridas de re-entrenamiento:

| Región | Paisaje | RF (media ± desvío) | CNN (media ± desvío) | Resultado |
|---|---|---|---|---|
| Filadelfia (Boquerón) | Colonia agrícola menonita, bosque fragmentado | 0,829 ± 0,001 | 0,696 ± 0,021 | **RF gana, decisivo** |
| Bahía Negra (Alto Paraguay) | Bosque continuo, remoto | 0,611 ± 0,002 | 0,611 ± 0,016 | **Empate real** |
| Pozo Colorado (Presidente Hayes) | Ganadería, ruta Trans-Chaco | 0,661 ± 0,006 | 0,727 ± 0,021 | **CNN gana** |

**Nota metodológica importante**: la primera pasada por estas 3 regiones usó una sola semilla cada
una y sugería "RF gana en 2 de 3" — con 5 semillas, el resultado de Bahía Negra resultó ser ruido
de una corrida particular que agarró a la CNN en su peor semilla; el resultado real es un empate.
Sin la repetición con varianza real, la conclusión habría quedado mal caracterizada. Se documenta
este proceso de corrección deliberadamente (sección 6), no se oculta.

**Causa de la falla en Filadelfia, diagnosticada con evidencia, no solo hipotetizada**: descartado
que sea efecto de período (2019/2023 fallan por igual) o de volumen de datos (duplicar el
entrenamiento no cambió el resultado en Filadelfia, aunque sí mejoró el bosque del propio AOI). Los
puntos de bosque real mal clasificados tienen firma espectral SWIR de canopy fino/degradado, y la
inspección visual directa confirma que son **franjas angostas de bosque entre campos** (cortinas
rompevientos, típicas de la agricultura menonita) que no llenan la ventana de 330m — no bloques de
bosque contiguo. La CNN aprendió "bosque" en parte como un patrón espacial de canopy grande y
continuo, que no transfiere a bosque fragmentado en tiras; Random Forest, al mirar solo el píxel
central, no tiene ese modo de falla.

**Cross-check contra ESA WorldCover** (independiente, nunca usado en entrenamiento) — resultados
consistentes con lo anterior: agreement alto en bosque para ambos modelos salvo el sesgo esperado
por sub-predicción de bosque de la CNN en Filadelfia; "pasto" es un proxy débil en las 3 regiones
porque la clase "Grassland" de WorldCover no distingue pastura manejada de pastizal natural, algo
que MapBiomas sí separa. Detalle numérico completo por región en
`data/study_area/{filadelfia,bahia_negra,pozo_colorado}_holdout_results.json`.

## 5. Decisión: clasificador operativo (cerrada)

Grad-CAM — la evidencia auditable por predicción individual que responde la pregunta de
investigación central del proyecto — solo puede engancharse a un modelo diferenciable con mapas de
activación espaciales; Random Forest no puede darla bajo ninguna implementación.

**La CNN queda confirmada como clasificador operativo de MARTA.** Gana o empata en 3 de los 4
contextos evaluados (AOI, Bahía Negra, Pozo Colorado) y pierde solo en Filadelfia, con causa
identificada y específica de paisaje. Se considera aceptable porque el destino real de despliegue
— el AOI de Corazón Verde del Chaco, Fase 4 — está dentro de la huella de entrenamiento y no es un
paisaje de colonia fragmentada como Filadelfia.

**Limitación documentada, no oculta**: no confiar en la CNN sin cruzar contra Random Forest para
clasificar bosque en paisajes con fragmentación estructuralmente similar a Filadelfia (franjas
angostas, cortinas rompevientos). El resultado de Random Forest no se descarta — sigue siendo la
opción más robusta específicamente para ese tipo de paisaje, y queda disponible como chequeo
cruzado. Registro completo de la decisión en `openspec/changes/phase1-classifier/tasks.md`, tarea
4.4, y `design.md`.

## 6. Trazabilidad y reproducibilidad

Cada corrida de entrenamiento y evaluación (las 5 semillas de la comparación en el AOI, y las 5
semillas de cada una de las 3 evaluaciones held-out) queda registrada en **MLflow**, experimento
`phase1-classifier` — hiperparámetros, métricas por clase, y artefactos de resultado por corrida,
no solo el número final reportado acá. Esto permite auditar cualquier número de este documento
hasta la corrida exacta que lo produjo, en vez de tener que confiar en que el número está bien
transcripto.

Además, el pipeline completo pasó por **8 rondas de revisión de código y verificación
independiente**, documentadas en detalle en `openspec/changes/phase1-classifier/tasks.md`. La
conclusión cambió de dirección varias veces a lo largo del proceso — "RF gana claro" → "empate
técnico" → "CNN gana" → confirmación de que la brecha de Filadelfia era real, no un bug → volumen
de datos duplicado para descartar que fuera un problema de escala → causa de Filadelfia
diagnosticada con evidencia visual → **una sobre-generalización propia del equipo, corregida al
recalcular las 3 regiones held-out con varianza real en vez de una sola corrida**. Cada corrección
quedó documentada explícitamente en el momento en que se encontró, no absorbida en silencio ni
prolijamente escondida en una versión final. Este proceso es en sí mismo parte de la respuesta a
la pregunta de investigación del TFM: un pipeline auditable no es solo el que da evidencia por
predicción (Grad-CAM, todavía pendiente), sino el que se somete a esa misma exigencia de
trazabilidad en su propia construcción — incluida la propia interpretación de sus resultados.

## 7. Próximos pasos

- Grad-CAM sobre la CNN, ahora confirmada como clasificador operativo.
- Fase 2: estimación de carbono (altura de dosel + calibración GEDI L4A + conversión a CO2e).
- Comparación temporal (2019 vs. 2023) usando el clasificador ya seleccionado, para producir el
  mapa de cambio que alimenta la estimación de carbono.
