= Resultados: Fase 1 (clasificación de cobertura)

== Resumen ejecutivo

Se comparó un clasificador Random Forest (baseline, per-píxel) contra una CNN chica y
propia (candidata, con contexto espacial de 33×33 píxeles) para distinguir bosque, pasto
y cultivo sobre Sentinel-2, usando MapBiomas Chaco como etiqueta. La comparación se hizo
bajo un criterio de significancia fijado antes de ver resultados, y se extendió con una
evaluación de generalización geográfica sobre 3 sub-áreas held-out de paisajes distintos.

*Resultado*: la CNN gana la comparación de precisión sobre el AOI, y gana en 2 de las 3
sub-áreas held-out independientes -- pierde claramente solo en una (Filadelfia,
Boquerón), con una causa identificada y específica de paisaje, no una falla de
generalización sin explicar. *La CNN queda confirmada como clasificador operativo del
sistema*, con esa limitación documentada explícitamente.

== Resultados sobre el AOI

Sobre el conjunto de prueba del área de estudio (~360 ejemplos, nunca usados en
entrenamiento ni ajuste), promediando 5 corridas con distinta semilla, con los
hiperparámetros elegidos en validación y evaluado una sola vez:

#table(
  columns: (auto, auto, auto),
  align: (left, center, center),
  table.header([*Modelo*], [*F1 macro promedio*], [*Desv. estándar*]),
  [Random Forest], [0,811], [0,005],
  [CNN], [0,860], [0,008],
)

La diferencia (+0,049) supera el umbral pre-registrado (desviación combinada, 0,007). Con
los hiperparámetros iniciales la CNN también ganaba (0,843 contra 0,811). Por el criterio fijado de
antemano, *la CNN gana esta comparación*. Ambos modelos muestran el mismo patrón de
error: la confusión entre pasto y cultivo es sistemáticamente mayor que la confusión de
cualquiera de las dos con bosque -- una limitación de qué distingue el sensor, no del
modelo.

== Evaluación de generalización geográfica

El AOI por sí solo no prueba generalización -- sus ejemplos de prueba salen de la misma
huella de entrenamiento. Se evaluaron ambos modelos contra 3 sub-áreas geográficamente
excluidas por completo del entrenamiento, cada una con 5 corridas de re-entrenamiento:

#table(
  columns: (auto, 1fr, auto, auto, auto),
  align: (left, left, center, center, left),
  table.header([*Región*], [*Paisaje*], [*RF*], [*CNN*], [*Resultado*]),
  [Filadelfia], [Colonia menonita, bosque fragmentado], [0,831 ± 0,001], [0,706 ± 0,016], [*RF gana, decisivo*],
  [Bahía Negra], [Bosque continuo, remoto], [0,611 ± 0,002], [0,619 ± 0,004], [*CNN gana, por poco*],
  [Pozo Colorado], [Ganadería, ruta Trans-Chaco], [0,661 ± 0,007], [0,727 ± 0,017], [*CNN gana*],
)

*Nota metodológica*: la primera pasada por estas 3 regiones usó una sola semilla cada una
y sugería "RF gana en 2 de 3" -- con 5 semillas, el resultado de Bahía Negra resultó ser
ruido de una corrida particular que agarró a la CNN en su peor semilla. Con los
hiperparámetros iniciales el resultado era un empate; con los elegidos en validación la
CNN gana por un margen chico (+0,008 contra una desviación combinada de 0,003).

*Causa de la falla en Filadelfia, diagnosticada con evidencia*: descartado que sea efecto
de período o de volumen de datos (duplicar el entrenamiento no cambió el resultado en
Filadelfia, aunque sí mejoró el bosque del propio AOI). Los puntos de bosque real mal
clasificados son sistemáticamente *franjas angostas de bosque entre campos* (cortinas
rompevientos, típicas de la agricultura menonita) que no llenan la ventana de 330m. La
CNN aprendió "bosque" en parte como un patrón espacial de canopy grande y continuo, que
no transfiere a bosque fragmentado en tiras; Random Forest, al mirar solo el píxel
central, no tiene ese modo de falla.

== Decisión: clasificador operativo

Grad-CAM -- la evidencia auditable por predicción individual que responde la pregunta de
investigación central del proyecto -- solo puede engancharse a un modelo diferenciable
con mapas de activación espaciales; Random Forest no puede darla bajo ninguna
implementación.

*La CNN queda confirmada como clasificador operativo del sistema.* Gana en 3 de los 4
contextos evaluados (AOI, Bahía Negra, Pozo Colorado) y pierde solo en Filadelfia,
con causa identificada. Se considera aceptable porque el destino real de despliegue -- el
AOI de Corazón Verde del Chaco, Fase 4 -- está dentro de la huella de entrenamiento y no
es un paisaje de colonia fragmentada como Filadelfia.

*Limitación documentada, no oculta*: no confiar en la CNN sin cruzar contra Random Forest
para clasificar bosque en paisajes con fragmentación estructuralmente similar a
Filadelfia.

== Hiperparámetros: elegidos en validación

Los valores iniciales se fijaron una vez con rangos estándar de literatura (sección 2.3).
Lo que cambió el resultado a lo largo del proyecto fueron correcciones de pipeline y
decisiones de diseño de datos (semilla de aumentado, distorsión de zona UTM, fuga
espacial, volumen de entrenamiento), no los hiperparámetros.

Después se eligieron en el split de validación (`scripts/24_hyperparameter_selection.py`):
grilla completa para cada modelo (18 configuraciones de RF, 36 de la CNN), 5 semillas por
configuración, F1 macro en validación y desvío muestral. La regla se fijó antes de
puntuar: la configuración inicial se mantiene salvo que la mejor la supere por más de la
desviación estándar combinada, el mismo criterio que decide RF contra CNN.

#table(
  columns: (auto, auto, auto, auto, 1fr),
  align: (left, left, center, center, left),
  table.header([*Modelo*], [*Mejor configuración*], [*Mejor*], [*Inicial*], [*Decisión*]),
  [RF], [300 árboles, profundidad 10, `max_features` 0,5], [0,832 ± 0,007], [0,827 ± 0,003], [Se mantiene la inicial: +0,005 frente a una desviación combinada de 0,006],
  [CNN], [`lr` 0,0003, `dropout` 0,5, `batch_size` 16], [0,844 ± 0,008], [0,826 ± 0,016], [Se adopta: +0,018 frente a 0,013],
)

Ninguna corrida llegó al tope de 100 épocas; con la configuración elegida, el early
stopping corta entre las épocas 24 y 39. El test se evaluó una sola vez, con estas
configuraciones. Una barrida anterior, de un parámetro a la vez y con 3 semillas, se había
evaluado sobre el split de test; no se usó para elegir nada y queda solo como registro
(`data/study_area/hyperparameter_sweep_test_split.json`).

Como la CNN operativa cambió, se volvieron a correr la clasificación del AOI, el mapa de
cambio (con la misma regla de post-proceso, sin modificar), Grad-CAM y el sorteo de la
muestra de referencia, que todavía no se había interpretado.

== Trazabilidad: 9 rondas de revisión

La conclusión cambió de dirección varias veces a lo largo del proceso: "RF gana claro" →
"empate técnico" → "CNN gana" → confirmación de que la brecha de Filadelfia era real →
volumen de datos duplicado para descartar que fuera un problema de escala → causa de
Filadelfia diagnosticada con evidencia visual → una sobre-generalización propia del
equipo corregida al recalcular las 3 regiones con varianza real → una novena ronda,
pedida antes de dar por cerrado el trabajo de las rondas 7-8, que encontró y corrigió un
script de diagnóstico roto por un refactor previo, un bug de asignación de _splits_ que
afectaba 64 ubicaciones, y un patrón de indexado fragil en la evaluación _held-out_. Cada
corrección quedó documentada en el momento en que se encontró, no absorbida en silencio.

Cada corrida queda registrada en MLflow (experimento `phase1-classifier`): hiperparámetros,
métricas por clase, y artefactos de resultado -- permite auditar cualquier número de este
documento hasta la corrida exacta que lo produjo.

== Próximos pasos

- Fase 2: estimación de carbono (altura de dosel + calibración GEDI L4A + conversión a
  CO2e): propuesta, sin implementar.
- Fase 3: validación contra ecuaciones alométricas o datos de campo, si hay acceso.
- Fase 4: demo de auditoría contra Corazón Verde del Chaco.
