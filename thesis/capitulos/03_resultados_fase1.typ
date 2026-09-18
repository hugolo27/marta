= Resultados: Fase 1 (clasificación de cobertura)

== Resumen ejecutivo

Se comparó un clasificador Random Forest (baseline, per-píxel) contra una CNN chica y
propia (candidata, con contexto espacial de 33×33 píxeles) para distinguir bosque, pasto
y cultivo sobre Sentinel-2, usando MapBiomas Chaco como etiqueta. La comparación se hizo
bajo un criterio de significancia fijado antes de ver resultados, y se extendió con una
evaluación de generalización geográfica sobre 3 sub-áreas held-out de paisajes distintos.

*Resultado*: la CNN gana la comparación de precisión sobre el AOI, y gana o empata en 2
de las 3 sub-áreas held-out independientes -- pierde claramente solo en una (Filadelfia,
Boquerón), con una causa identificada y específica de paisaje, no una falla de
generalización sin explicar. *La CNN queda confirmada como clasificador operativo del
sistema*, con esa limitación documentada explícitamente.

== Resultados sobre el AOI

Sobre el conjunto de prueba del área de estudio (~360 ejemplos, nunca usados en
entrenamiento ni ajuste), promediando 5 corridas con distinta semilla:

#table(
  columns: (auto, auto, auto),
  align: (left, center, center),
  table.header([*Modelo*], [*F1 macro promedio*], [*Desv. estándar*]),
  [Random Forest], [0,811], [0,004],
  [CNN], [0,843], [0,012],
)

La diferencia (+0,032) supera el umbral pre-registrado (0,009). Por el criterio fijado de
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
  [Filadelfia], [Colonia menonita, bosque fragmentado], [0,829 ± 0,001], [0,696 ± 0,021], [*RF gana, decisivo*],
  [Bahía Negra], [Bosque continuo, remoto], [0,611 ± 0,002], [0,611 ± 0,016], [*Empate real*],
  [Pozo Colorado], [Ganadería, ruta Trans-Chaco], [0,661 ± 0,006], [0,727 ± 0,021], [*CNN gana*],
)

*Nota metodológica*: la primera pasada por estas 3 regiones usó una sola semilla cada una
y sugería "RF gana en 2 de 3" -- con 5 semillas, el resultado de Bahía Negra resultó ser
ruido de una corrida particular que agarró a la CNN en su peor semilla; el resultado real
es un empate.

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

*La CNN queda confirmada como clasificador operativo del sistema.* Gana o empata en 3 de
los 4 contextos evaluados (AOI, Bahía Negra, Pozo Colorado) y pierde solo en Filadelfia,
con causa identificada. Se considera aceptable porque el destino real de despliegue -- el
AOI de Corazón Verde del Chaco, Fase 4 -- está dentro de la huella de entrenamiento y no
es un paisaje de colonia fragmentada como Filadelfia.

*Limitación documentada, no oculta*: no confiar en la CNN sin cruzar contra Random Forest
para clasificar bosque en paisajes con fragmentación estructuralmente similar a
Filadelfia.

== Hiperparámetros: fijados una vez, nunca ajustados

Ninguno de los hiperparámetros del modelo (`dropout`, `learning_rate`, `batch_size`,
`n_estimators`, `max_depth`, etc., sección 2.3) se ajustó empíricamente para llegar a
este resultado -- se fijaron una sola vez a valores estándar de literatura. Lo que sí
cambió el resultado a lo largo del proyecto fueron correcciones de pipeline y decisiones
de diseño de datos (semilla de aumentado, distorsión de zona UTM, fuga espacial, volumen
de entrenamiento), nunca el modelo en sí.

*Barrida de sensibilidad, corrida* (`data/study_area/hyperparameter_sweep_results.json`,
un parámetro a la vez, valores por defecto fijos en el resto):

#table(
  columns: (auto, auto, auto, 1fr),
  align: (left, left, center, left),
  table.header([*Modelo*], [*Parámetro*], [*Usado / mejor*], [*Hallazgo*]),
  [RF], [`n_estimators`], [400 / 300 o 400 (empatados)], [El valor usado ya es el óptimo empírico (300 y 400 empatan en 0,811; 500 baja a 0,810)],
  [RF], [`max_depth`], [sin límite / sin límite], [El valor usado ya es el óptimo empírico (0,811 vs. 0,806 con límite 10, 0,810 con límite 20)],
  [CNN], [`dropout`], [0,4 / 0,4], [El valor usado ya es el óptimo empírico (0,843 vs. 0,840 con 0,3, 0,831 con 0,5)],
  [CNN], [`learning_rate`], [0,001 / *0,0001*], [El valor usado *no* es el óptimo empírico en esta barrida: 0,0001 dio 0,850 ± 0,007 contra 0,843 ± 0,016 del valor usado -- diferencia pequeña y con rangos solapados a 3 semillas, no concluyente sin más corridas, pero real y no debe ocultarse],
  [CNN], [`batch_size`], [32 / 32], [El valor usado ya es el óptimo empírico (0,843 vs. 0,834 con 16 o 64)],
)

*Interpretación honesta*: la elección de rango estándar de literatura se sostiene
empíricamente en 4 de los 5 parámetros barridos. El `learning_rate` es la excepción --
un valor 10x menor rindió mejor en esta barrida acotada (3 semillas), aunque la
diferencia (+0,007) es chica frente a la variabilidad observada (± 0,007-0,016) y no se
recorrió con suficientes semillas para confirmarla como señal real y no ruido. No se
retrena la CNN de referencia con este valor sin antes correr una comparación formal de 5
semillas equivalente a la de la sección 3.2 -- este hallazgo queda documentado como
candidato a explorar, no como corrección aplicada.

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
  CO2e) -- no arrancada.
- Fase 3: validación contra ecuaciones alométricas o datos de campo, si hay acceso.
- Fase 4: demo de auditoría contra Corazón Verde del Chaco.
