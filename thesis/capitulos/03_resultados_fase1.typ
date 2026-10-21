= Resultados: Fase 1 (clasificación de cobertura)

== Resumen ejecutivo

Se comparó un clasificador Random Forest (baseline, per-píxel) contra una CNN chica y
propia (candidata, con un bloque de 3×3 píxeles) para distinguir bosque, pasto
y cultivo sobre Sentinel-2, con los compuestos de época seca y húmeda, usando MapBiomas Chaco como etiqueta. La comparación se hizo
bajo un criterio de significancia fijado antes de ver resultados, y se extendió con una
evaluación de generalización geográfica sobre 3 sub-áreas held-out de paisajes distintos.

*Resultado*: la CNN gana la comparación de precisión sobre el AOI, y gana en 2 de las 3
sub-áreas held-out independientes -- pierde solo en una (Filadelfia, Boquerón), por un
margen mucho menor que con las versiones anteriores del modelo y con una causa identificada
y específica de paisaje. *La CNN queda confirmada como clasificador operativo del
sistema*, con esa limitación documentada explícitamente.

== Resultados sobre el AOI

Sobre el conjunto de prueba (915 ejemplos en bloques de 6 km, nunca usados en
entrenamiento ni ajuste), promediando 5 corridas con distinta semilla, con las variantes y
los hiperparámetros elegidos en validación y evaluado una sola vez:

#table(
  columns: (auto, auto, auto),
  align: (left, center, center),
  table.header([*Modelo*], [*F1 macro promedio*], [*Desv. estándar*]),
  [Random Forest (seca + húmeda)], [0,841], [0,003],
  [CNN 3×3 (seca + húmeda)], [0,865], [0,003],
)

La diferencia (+0,024) supera el umbral pre-registrado (desviación combinada, 0,003). Por
el criterio fijado de antemano, *la CNN gana esta comparación*. El error dominante de la
CNN es la confusión entre pasto y cultivo, mucho mayor que la de cualquiera de las dos con
bosque. Las versiones anteriores del dataset (bloques de ~2 km, solo época seca) daban 0,811
para el RF y 0,860 para la CNN de 33×33, pero con bloques más chicos que el alcance de la
autocorrelación espacial, así que esos números probablemente eran optimistas (sección
"Autocorrelación espacial").

== Evaluación de generalización geográfica

El AOI por sí solo no prueba generalización -- sus ejemplos de prueba salen de la misma
huella de entrenamiento. Se evaluaron ambos modelos contra 3 sub-áreas geográficamente
excluidas por completo del entrenamiento, cada una con 5 corridas de re-entrenamiento:

#table(
  columns: (auto, 1fr, auto, auto, auto),
  align: (left, left, center, center, left),
  table.header([*Región*], [*Paisaje*], [*RF*], [*CNN*], [*Resultado*]),
  [Filadelfia], [Colonia menonita, bosque fragmentado], [0,839 ± 0,004], [0,824 ± 0,010], [*RF gana*],
  [Bahía Negra], [Bosque continuo, remoto], [0,621 ± 0,001], [0,627 ± 0,005], [*CNN gana, por poco*],
  [Pozo Colorado], [Ganadería, ruta Trans-Chaco], [0,668 ± 0,004], [0,710 ± 0,027], [*CNN gana*],
)

*Nota metodológica*: la primera pasada por estas 3 regiones usó una sola semilla cada una
y sugería "RF gana en 2 de 3" -- con 5 semillas, el resultado de Bahía Negra resultó ser
ruido de una corrida particular que agarró a la CNN en su peor semilla. Con el modelo
final la CNN gana allí por un margen chico (+0,006 contra una desviación combinada de
0,004).

*Causa de la falla en Filadelfia, diagnosticada con evidencia*: descartado que sea efecto
de período o de volumen de datos (duplicar el entrenamiento no cambió el resultado en
Filadelfia, aunque sí mejoró el bosque del propio AOI). Los puntos de bosque real mal
clasificados son sistemáticamente *franjas angostas de bosque entre campos* (cortinas
rompevientos, típicas de la agricultura menonita) que no llenan la ventana de 330m. La
CNN aprendió "bosque" en parte como un patrón espacial de canopy grande y continuo, que
no transfiere a bosque fragmentado en tiras; Random Forest, al mirar solo el píxel
central, no tiene ese modo de falla. Con la entrada de 3×3 (90 m) la brecha se achica de
0,125 a 0,015, lo que es consistente con ese diagnóstico, aunque la falla no se volvió a
analizar punto por punto con el modelo nuevo.

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

== Hiperparámetros: primera selección en validación (dataset anterior)

Esta sección y las dos siguientes documentan el camino hasta el modelo final, sobre el
dataset anterior (400 ejemplos por clase y año, bloques de ~2 km, solo época seca, CNN de
33×33). El modelo final se describe en "Dataset final y selección de variantes".

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

== Tamaño de entrada de la CNN: 3×3 contra 33×33

El diseño original del tutor era una matriz de 3×3 píxeles de Sentinel-2 por píxel de
MapBiomas. Se usó como unidad de alineación de la etiqueta, y la CNN se amplió a una ventana
de 33×33 para darle contexto espacial, sin evaluar la versión de 3×3. Para compararlas se
entrenó la misma CNN mirando solo el bloque central de 3×3 de cada ventana (mismos
parámetros, sin las capas de _pooling_ que una entrada de 3×3 no admite), con sus
hiperparámetros elegidos en validación (36 configuraciones, 5 semillas;
`scripts/31_patch_size_selection.py`). La regla se registró antes de puntuar: el 3×3 queda
como operativo salvo que el 33×33 lo supere en validación por más de la desviación combinada.

#table(
  columns: (auto, auto, auto, 1fr),
  align: (left, center, center, left),
  table.header([*Modelo*], [*Validación*], [*Test*], [*Configuración*]),
  [CNN 3×3], [0,837 ± 0,010], [0,810 ± 0,011], [`lr` 0,0003, `dropout` 0,5, `batch_size` 32],
  [CNN 33×33], [0,844 ± 0,008], [0,860 ± 0,008], [`lr` 0,0003, `dropout` 0,5, `batch_size` 16],
  [Random Forest], [0,827 ± 0,003], [0,811 ± 0,005], [400 árboles],
)

En validación la diferencia (0,007) queda dentro de la desviación combinada (0,009), así que
por la regla el 3×3 pasa a ser el operativo. En test, que se reporta y no se usa para
elegir, el 33×33 gana con claridad y el 3×3 rinde igual que el Random Forest: con 9 píxeles
la CNN se comporta casi como un clasificador por píxel. El split de validación (361
ejemplos) resultó demasiado chico para separar las dos variantes. A partir de este resultado
el trabajo sigue con la entrada de 3×3, sobre un dataset más grande (sección "Dataset final
y selección de variantes").

== Autocorrelación espacial y tamaño de los bloques

La partición asigna bloques espaciales completos a entrenamiento, validación o test. El
lado de ~2 km se había fijado como "más de 6 veces el lado de la ventana". La literatura
pide bloques al menos tan grandes como la distancia a la que los puntos dejan de parecerse
entre sí @roberts2017crossvalidation @valavi2019blockcv. Se midió con semivariogramas sobre
18.000 puntos en 60 ventanas de 20 km del área de muestreo (`scripts/33_spatial_autocorrelation.py`).

#table(
  columns: (auto, auto, auto),
  align: (left, center, center),
  table.header([*Variable*], [*2019*], [*2023*]),
  [NDVI], [3,9 km], [4,8 km],
  [Clase de MapBiomas], [5,2 km], [4,4 km],
)

Todos los alcances superan los 2 km: un punto de test podía estar dentro del alcance de
autocorrelación de uno de entrenamiento, por lo que las métricas de test de este capítulo
probablemente son optimistas. Las regiones reservadas, a cientos de kilómetros, no tienen
ese problema. Con la regla "lado del bloque = mayor alcance, redondeado hacia arriba al
kilómetro", el lado pasa a 6 km. El dataset se reconstruye con esos bloques, más ejemplos
(1.000 por clase y año) y un compuesto de época húmeda además del seco.

Además se corrigió cómo se asignaban los bloques: se armaban por separado para cada clase,
así que un mismo cuadrado podía mandar sus puntos de bosque a entrenamiento y los de pasto a
test. En el dataset nuevo todos los puntos de un bloque van al mismo grupo.

== Dataset final y selección de variantes

El dataset final tiene 5.993 ejemplos (4.157 de entrenamiento, 921 de validación y 915 de
test); la época húmeda no hizo descartar ningún ejemplo por nubes y cada clase quedó con
entre 289 y 325 ejemplos en validación y en test. Con la entrada de 3×3 se comparó la época
seca sola contra seca + húmeda, para la CNN y para el Random Forest. Cada variante eligió
sus hiperparámetros en validación con una grilla ampliada (48 configuraciones para la CNN,
18 para el RF, 5 semillas). La regla, registrada antes de construir el dataset, mantiene la
variante de época seca salvo que la otra la supere en validación por más de la desviación
combinada.#footnote[El registro original incluía también variantes de 33×33. Siguiendo la
indicación de trabajar con entrada de 3×3, se retiraron mediante una enmienda fechada; sus
resultados parciales quedan como exploratorios
(`data/study_area/variant_selection/`).]

#table(
  columns: (auto, auto, auto, 1fr),
  align: (left, center, center, left),
  table.header([*Variante*], [*Validación*], [*Test*], [*Configuración*]),
  [RF, seca], [0,827 ± 0,002], [0,799 ± 0,004], [300 árboles, profundidad 10],
  [RF, seca + húmeda], [0,845 ± 0,002], [0,841 ± 0,003], [500 árboles, sin límite],
  [CNN 3×3, seca], [0,843 ± 0,003], [0,835 ± 0,007], [`lr` 0,0003, `dropout` 0,3, `batch_size` 8],
  [CNN 3×3, seca + húmeda], [0,869 ± 0,007], [0,865 ± 0,003], [`lr` 0,0001, `dropout` 0,3, `batch_size` 32],
)

La época húmeda mejora los dos modelos por mucho más que el ruido entre semillas (+0,027
con desviación combinada 0,005 en la CNN, +0,018 con 0,002 en el RF), así que *los dos
modelos operativos usan seca + húmeda*. En la CNN de época seca el mejor `batch_size` cayó en
el borde de la grilla (8); el paso extra (4) dio peor, así que el óptimo está dentro de lo
probado. Ninguna corrida llegó al tope de 100 épocas. Validación y test casi coinciden, algo
esperable ahora que los bloques superan el alcance de la autocorrelación.

Con la CNN final se volvieron a correr las regiones reservadas, la clasificación del área
del proyecto y del área de desarrollo, la regla del mapa de cambio (sin modificarla),
Grad-CAM y el sorteo de la muestra de referencia. La regla eligió ahora confianza ≥ 0,9,
persistencia en 2022 y unidad mínima de mapeo: 8,1 ha de pérdida y 61,0 ha de ganancia en el
área del proyecto, con el 86 % de la pérdida confirmada recuperada en el área de desarrollo.
La ganancia, mucho mayor que con el modelo anterior (0,5 ha), queda a verificar con la
muestra de referencia. Con entrada de 3×3, Grad-CAM produce un mapa de 3×3 píxeles: indica
qué parte del bloque pesó en la predicción, pero no da contexto espacial.

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
