= Resultados: Fase 1 (clasificación de cobertura)

== Resumen ejecutivo

Se comparó una U-Net que segmenta (candidata, con contexto espacial) contra un Random Forest
por celda (referencia) para distinguir bosque, pasto y cultivo sobre Sentinel-2, con los
compuestos de época seca y húmeda y MapBiomas Chaco como etiqueta. Todas las reglas de
selección, test y mapa de cambio se escribieron y registraron antes de puntuar.

*Resultado:* la U-Net gana en validación, empata en test y gana en 2 de las 3 regiones
reservadas (empata en la tercera). Por la regla fijada, un empate deja a la U-Net como
clasificador operativo, porque solo ella admite explicaciones por predicción. Con ella se
mapeó el cambio 2019-2023 del área del proyecto y se sorteó la muestra de referencia que
falta interpretar. La CNN de 3×3, operativa antes, queda como antecedente al final del
capítulo.

== Selección en validación

La selección corrió del 18 al 20 de noviembre de 2026 en molab (una GPU NVIDIA RTX PRO 6000
Blackwell), con 27 configuraciones de U-Net y 18 de Random Forest, 5 semillas cada una:

#table(
  columns: (auto, 1fr, auto),
  align: (left, left, center),
  table.header([*Modelo*], [*Configuración*], [*Dice macro (val.)*]),
  [U-Net, mejor de 48 px], [`lr` 0,001, lote 32], [0,8277 ± 0,0024],
  [U-Net, mejor de 96 px], [], [0,8232],
  [U-Net, mejor de 192 px], [], [0,8205],
  [Random Forest], [500 árboles, sin límite de profundidad, `max_features` 0,5], [0,8145 ± 0,0002],
)

`lr` 0,001 y lote 32 son bordes de la grilla, así que se probó un paso más (`lr` 0,003 dio
0,8228 y lote 64, 0,8235): ninguno superó a la elegida. La diferencia entre U-Net y Random
Forest (0,0132) supera el desvío combinado (0,0017), así que en validación la U-Net es mejor.
El recorte más chico (48 px, 480 m) gana a los más grandes.

== Test

El test se corrió una sola vez, con los modelos ya elegidos:

#table(
  columns: (auto, auto, auto, auto, auto),
  align: (left, center, center, center, center),
  table.header([*Modelo*], [*Dice macro*], [*Bosque*], [*Pasto*], [*Cultivo*]),
  [U-Net], [0,8159 ± 0,0104], [0,948], [0,870], [0,630],
  [Random Forest], [0,8113 ± 0,0002], [0,945], [0,870], [0,619],
)

La diferencia (0,0047) queda por debajo del desvío combinado (0,0074): *en test los dos
empatan*, contra una brecha clara en validación. Según la regla de selección del
clasificador operativo, un empate deja a la U-Net, porque solo un modelo con gradientes y
mapas de activación admite Grad-CAM por predicción; el Random Forest queda como hallazgo de
referencia. El error dominante de los dos es el cultivo, confundido con pasto.

*Repetición de semillas.* Las regiones reservadas se miden con las 5 semillas del test, y del
test solo se guardó el modelo de la semilla 42, así que las otras cuatro se reentrenaron con la
misma configuración, el mismo código y la misma GPU. Como el entrenamiento en GPU no es
determinista (capítulo 2), no salieron idénticas:

#table(
  columns: (auto, auto, auto, auto),
  align: (left, center, center, center),
  table.header([*Semilla*], [*En el test*], [*Reentrenada*], [*Diferencia*]),
  [1], [0,8234], [0,8218], [−0,0016],
  [7], [0,8236], [0,8210], [−0,0026],
  [123], [0,8210], [0,8205], [−0,0005],
  [2026], [0,7992], [0,8246], [+0,0254],
)

La semilla 2026, la peor del test por lejos, al repetirla queda con las demás: buena parte del
desvío de la U-Net en test (0,0104) viene de una corrida desfavorable, así que el empate es un
resultado prudente y no indica que la U-Net sea peor. El resultado del test no se reemplaza:
cambiar una corrida después de verla sería elegir el resultado. Los modelos reentrenados se usan
solo en las regiones reservadas.

== Regiones reservadas

Cada región se clasificó entera en 2019 y 2023 (entre 3,3 y 3,6 millones de celdas de 30 m con
etiqueta por región) con las 5 semillas de cada modelo, contra MapBiomas:

#table(
  columns: (auto, 1fr, auto, auto, auto),
  align: (left, left, center, center, left),
  table.header([*Región*], [*Paisaje*], [*U-Net*], [*RF*], [*Resultado*]),
  [Filadelfia], [Colonia menonita, bosque fragmentado], [0,830 ± 0,008], [0,810 ± 0,000], [*U-Net gana*],
  [Bahía Negra], [Bosque continuo, remoto], [0,615 ± 0,006], [0,588 ± 0,000], [*U-Net gana*],
  [Pozo Colorado], [Ganadería, ruta Trans-Chaco], [0,605 ± 0,017], [0,606 ± 0,001], [Empate],
)

En Filadelfia, donde la CNN de 3×3 perdía por las cortinas rompevientos angostas, la U-Net
gana por más del triple del desvío combinado (0,019 contra 0,006). El Dice macro bajo de Bahía
Negra y Pozo Colorado viene del cultivo: según MapBiomas hay 4 celdas de cultivo en Bahía Negra
y 3.895 en Pozo Colorado, de más de 3 millones, así que todo cultivo que marque un modelo cuenta
como error (Dice de cultivo 0,00 y 0,16) y arrastra el promedio de tres clases. En bosque, la
clase que define la pérdida, la U-Net da 0,99 y 0,97. Se informa tal cual, sin corregir la
métrica después de verla. El acuerdo de bosque con WorldCover 2021 es casi igual para los dos
modelos (0,97, 0,47 y 0,71 la U-Net; 0,97, 0,47 y 0,73 el Random Forest); el valor bajo de Bahía
Negra marca diferencias entre las dos referencias en ese paisaje más que entre los modelos.

== Mapa de cambio del área del proyecto

Con el modelo operativo (semilla 42) se clasificaron el área del proyecto y el área de
desarrollo en 2019, 2022 y 2023. La regla registrada puntuó 12 configuraciones de filtro en el
área de desarrollo, que tiene 4.848,9 ha de pérdida confirmada por Hansen y MapBiomas y
9.519,1 ha de bosque estable confirmado:

#table(
  columns: (1fr, auto, auto),
  align: (left, center, center),
  table.header([*Filtro*], [*Pérdida confirmada retenida*], [*Pérdida falsa*]),
  [Sin filtro], [95,6 %], [26,3 ha],
  [Confianza 0,7], [92,0 %], [6,7 ha],
  [Confianza 0,9 + unidad mínima (elegido)], [70,2 %], [0,4 ha],
  [Confianza 0,9 + persistencia + unidad mínima], [68,1 %], [0,4 ha],
)

Las 12 retienen más de la mitad; la pérdida falsa mínima es 0,4 ha y la logran dos
configuraciones, y entre ellas la regla elige la de menos pasos: *confianza 0,9 y unidad mínima
de 0,5 ha*. El filtro casi no marca pérdida falsa, pero deja pasar el 30 % de la pérdida
confirmada; ese costo lo mide el estrato de cambio descartado de la muestra de referencia.

Aplicado una vez al área del proyecto, da 5,1 ha de pérdida (57 celdas) y 61,6 ha de ganancia
entre 2019 y 2023, sobre 20.063,6 ha de bosque estable; ni Hansen ni MapBiomas confirman pérdida
allí. La ganancia queda a verificar con la muestra.

*Seg-Grad-CAM.* Se explicaron dos manchas de pérdida en ambas fechas: por qué la U-Net las
llamó bosque en 2019 y qué las llamó en 2023. Volver a predecir todas las ventanas que cubren
cada celda explicada devuelve las probabilidades guardadas en el mapa (diferencia máxima
8,4·10#super[-5]), así que la explicación corresponde exactamente a la predicción mapeada.

*Muestra de referencia.* Sobre este mapa se sortearon, antes de interpretar nada, los 340
puntos de la evaluación de exactitud en los seis estratos del capítulo 2 (en celdas: pérdida 57,
ganancia 684, cambio descartado 5.398, franja 334, bosque estable 221.812, no bosque estable
399). Su interpretación a ciegas, junto con 300 puntos en las regiones reservadas, da la
exactitud y el área de pérdida ajustada por error con la que cierra la fase.

== Antecedente: la CNN de 3×3

Antes de la U-Net, el clasificador con contexto era una CNN chica y propia con un bloque de
3×3 píxeles, comparada con el mismo Random Forest bajo reglas equivalentes. Por indicación del
tutor se reemplazó por la U-Net (capítulo 2). Las secciones siguientes documentan ese camino y
sus resultados, que ya no son los del sistema.

=== Resultados sobre el AOI

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

=== Evaluación de generalización geográfica

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

=== Decisión de entonces: la CNN como clasificador operativo

Grad-CAM -- la evidencia auditable por predicción individual que responde la pregunta de
investigación central del proyecto -- solo puede engancharse a un modelo diferenciable
con mapas de activación espaciales; Random Forest no puede darla bajo ninguna
implementación.

*En ese momento la CNN quedó como clasificador operativo del sistema*, decisión superada por la U-Net. Gana en 3 de los 4
contextos evaluados (AOI, Bahía Negra, Pozo Colorado) y pierde solo en Filadelfia,
con causa identificada. Se considera aceptable porque el destino real de despliegue -- el
AOI de Corazón Verde del Chaco, Fase 4 -- está dentro de la huella de entrenamiento y no
es un paisaje de colonia fragmentada como Filadelfia.

*Limitación documentada, no oculta*: no confiar en la CNN sin cruzar contra Random Forest
para clasificar bosque en paisajes con fragmentación estructuralmente similar a
Filadelfia.

=== Hiperparámetros: primera selección en validación (dataset anterior)

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

=== Tamaño de entrada de la CNN: 3×3 contra 33×33

Cada píxel de MapBiomas se alinea con un bloque de 3×3 píxeles de Sentinel-2, para conservar
la resolución nativa de 10 m. La CNN usaba una ventana de 33×33 centrada en ese bloque para
tener contexto espacial, y nunca se había comparado con una entrada de 3×3. Para compararlas se
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

=== Autocorrelación espacial y tamaño de los bloques

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

=== Dataset final y selección de variantes

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

=== Trazabilidad: 9 rondas de revisión

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

- Fase 1: interpretar a ciegas los 640 puntos de referencia y calcular la exactitud y el área de
  pérdida ajustada por error (Stehman, 2014; Olofsson et al., 2014).
- Fase 2: estimación de carbono (altura de dosel + calibración GEDI L4A + conversión a
  CO2e): propuesta, sin implementar.
- Fase 3: validación contra ecuaciones alométricas o datos de campo, si hay acceso.
- Fase 4: demo de auditoría contra Corazón Verde del Chaco.
