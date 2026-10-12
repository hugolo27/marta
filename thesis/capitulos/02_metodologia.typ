= Metodología

== Áreas de estudio

- *AOI del caso de estudio*: Corazón Verde del Chaco (VCS 2611), ~20.589 ha -- el
  proyecto REDD+ real y registrado que la demo de auditoría (Fase 4) compara contra lo
  observado por satélite.
- *Huella de muestreo*: 3 departamentos del Chaco paraguayo (Alto Paraguay, Boquerón,
  Presidente Hayes), ~24 millones de ha -- necesaria porque el AOI por sí solo no
  contiene ni un píxel de la clase "cultivo".
- *3 sub-áreas held-out* (Filadelfia, Bahía Negra, Pozo Colorado) -- excluidas de todo
  entrenamiento, reservadas para probar generalización geográfica real, no solo
  desempeño dentro del AOI.

== Construcción del dataset

Sentinel-2 (10m, 13 bandas) emparejado con etiquetas MapBiomas Chaco (30m) -- ratio
exacto 3:1 en resolución. Cada ejemplo de entrenamiento es un patch de 33×33 píxeles
(~330m de lado), no un solo píxel de 3×3 -- la CNN necesita contexto espacial real para
tener algo que aprender. Tres clases por fecha: bosque / pasto / cultivo (código
MapBiomas 15 específicamente = pastura real, no confundir con pastizal natural).
"Desmonte" no es una clase que el modelo prediga directamente -- se deriva comparando la
clasificación de un mismo punto entre dos fechas (bosque → no-bosque).

*Hallazgo metodológico central: la fuga espacial.* Cada patch cubre 330m en el terreno.
Dos patches cuyos centros están a menos de esa distancia pueden solaparse físicamente --
si uno cae en `train` y el otro en `test`, el modelo se evalúa parcialmente sobre datos
que ya vio. Esto apareció dos veces, por dos rutas distintas (dentro de un mismo período,
y entre 2019 y 2023), y corregir cada ocurrencia cambió la conclusión de la comparación
RF vs. CNN. El chequeo final (`enforce_spatial_buffer()`) es un paso obligatorio y
automático del pipeline, no una verificación manual puntual.

== Los dos modelos

- *Random Forest* (baseline): mira solo el píxel central, valores espectrales puros --
  sin noción de vecindad espacial.
- *CNN* (candidata, `SmallCNN`): 3 bloques convolucionales chicos, arquitectura propia,
  no un backbone pre-entrenado -- necesita justificar su complejidad extra con datos
  propios, y mantiene legible una futura capa de interpretabilidad (Grad-CAM).

*Criterio de comparación, fijado antes de entrenar*: ambos modelos se entrenan y evalúan
5 veces con semillas distintas; la CNN solo cuenta como ganadora si su F1 macro promedio
supera al de Random Forest en más de una desviación estándar combinada entre ambas
distribuciones de corridas.

=== Hiperparámetros finales

#table(
  columns: (auto, auto, auto, 1fr),
  align: (left, left, center, left),
  table.header([*Modelo*], [*Parámetro*], [*Valor*], [*Por qué*]),
  [RF], [`n_estimators`], [400], [Rango estándar (300-500); retornos decrecientes pasado
    unos cientos de árboles],
  [RF], [`max_depth`], [sin límite], [No es riesgoso en un forest -- la reducción de
    varianza viene de promediar árboles, no de podar],
  [CNN], [arquitectura], [32→64→128], [Red chica y propia, no un backbone pre-entrenado],
  [CNN], [batch size], [32], [Estándar para ~1.673 ejemplos de entrenamiento],
  [CNN], [learning rate], [0,001], [Default del paper original de Adam @kingma2014adam],
  [CNN], [dropout], [0,4], [Rango estándar (0,3-0,5) para un dataset chico],
  [CNN], [épocas / paciencia], [100 / 10], [Corta tras 10 épocas sin mejora en validación],
)

Estos valores se fijaron una sola vez, citando rango estándar de literatura, y no se
ajustaron empíricamente durante el desarrollo. Una barrida de sensibilidad de un
parámetro a la vez (diseñada junto con el resto de esta metodología) verifica esta
elección contra el propio dataset -- resultado en la sección de resultados de Fase 1.

== Detección de cambio y evaluación de exactitud

*Cambio bosque/no bosque con post-proceso pre-registrado.* El primer mapa de cambio del AOI
reportaba 1.007 ha de pérdida de bosque; Hansen Global Forest Change registra 0,1 ha en
2020-2023 y MapBiomas no coincide con ninguno de esos píxeles, así que era casi todo error
de comisión. El producto principal pasó a ser el cambio bosque/no bosque, y el post-proceso
se eligió con una regla escrita y registrada en MLflow antes de puntuar: entre 12
configuraciones, la que menos pérdida falsa deja en el AOI sin perder más de la mitad de la
pérdida confirmada en un área de desarrollo con deforestación real. Quedó elegida confianza
≥ 0,7 en ambas fechas más persistencia en 2022: pérdida mapeada de 81,9 ha.

*Evaluación contra referencia independiente.* La exactitud medida hasta ahí es acuerdo con
otros mapas, no con el terreno. El test final usa la vara que el propio proyecto del caso
de estudio fija para su monitoreo (VM0007): puntos interpretados sobre imagen de alta
resolución, al menos 50 por clase, exactitud general ≥ 90 %. El diseño, fijado antes de
interpretar:

- *Muestra estratificada de 340 puntos* en seis estratos: pérdida y ganancia mapeadas, el
  cambio que el post-proceso descartó, una franja de 60 m alrededor del cambio y de la
  pérdida que marcan Hansen o MapBiomas, y bosque y no bosque estables. Los estratos extra
  apuntan a donde puede esconderse pérdida que el mapa no vio.
- *Estimadores de Stehman (2014) y Olofsson et al. (2014)* para la exactitud y las áreas
  ajustadas por error con intervalo de confianza. Esas áreas, no los píxeles mapeados, son
  las que pasan a la estimación de carbono.
- *Dos definiciones de bosque:* la del proyecto (MDL: 25 % de copa, 0,5 ha, 5 m) como
  principal y la del nivel de referencia nacional (FREL, Región Occidental: 10 % de copa,
  1 ha, 3 m) como secundaria, derivada de los atributos registrados por punto sin
  interpretar dos veces.
- *Resultado central:* la exactitud del usuario y del productor de la clase pérdida. En un
  área casi intacta, la exactitud general es alta casi sin importar el mapa de cambio.
- *Consistencia del intérprete:* repetición a ciegas del 20 % de los puntos, idealmente por
  una segunda persona, ya que el intérprete principal es el autor del modelo.

