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

Sentinel-2 L2A (10m, 12 bandas + NDVI; B10 no está en L2A) emparejado con etiquetas MapBiomas Chaco (30m): cada
píxel de MapBiomas corresponde a un bloque de 3×3 píxeles de Sentinel-2. La relación es
exacta de norte a sur; de este a oeste es aproximada, porque MapBiomas usa una grilla en
grados (0,000269°) que en el Chaco mide 27 a 28 m de ancho. Para cada año se arman dos compuestos de mediana sin nubes: época
seca (junio a septiembre) y época húmeda (enero a abril del mismo año). Cada ejemplo guarda
una ventana de 33×33 píxeles (~330m de lado) con los 26 canales (13 secos y 13 húmedos); la
CNN operativa usa el bloque central de 3×3, la unidad de alineación original. Se sortean
1.000 puntos por clase y por año (2019 y 2023), estratificados sobre MapBiomas: 5.993
ejemplos después de los controles de calidad. Tres clases por fecha: bosque / pasto / cultivo (código
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

*Partición por bloques medidos.* Los ejemplos se reparten en entrenamiento, validación y
test (70/15/15) por bloques espaciales completos, con una sola asignación para los dos años.
El lado del bloque sale de semivariogramas del NDVI y de la clase de MapBiomas: el mayor
alcance práctico medido, redondeado hacia arriba, da 6 km
@roberts2017crossvalidation @valavi2019blockcv. Todos los puntos de un bloque van al mismo
grupo sin importar su clase, y el armado se detiene si alguna clase queda con menos del
10 % de sus puntos en validación o en test.

== Los dos modelos

- *Random Forest* (baseline): mira solo el píxel central, valores espectrales puros --
  sin noción de vecindad espacial.
- *CNN* (candidata, `SmallCNN`): 3 bloques convolucionales chicos, arquitectura propia,
  no un backbone pre-entrenado -- necesita justificar su complejidad extra con datos
  propios, y mantiene legible una futura capa de interpretabilidad (Grad-CAM). Recibe el
  bloque de 3×3 píxeles con sus vecinos inmediatos.

*Normalización de la entrada de la CNN.* Las bandas vienen como reflectancia por 10.000
(valores de ~70 a ~4.700) y el NDVI va de −0,3 a 0,9, así que sin escalar el NDVI casi no
pesa en la primera capa. Cada canal se estandariza con la media y el desvío del grupo de
entrenamiento, que quedan guardados con los pesos del modelo; el Random Forest no lo
necesita, porque sus cortes no dependen de la escala.

*Criterio de comparación, fijado antes de entrenar*: ambos modelos se entrenan y evalúan
5 veces con semillas distintas; la CNN solo cuenta como ganadora si su F1 macro promedio
supera al de Random Forest en más de una desviación estándar combinada entre ambas
distribuciones de corridas.

=== Hiperparámetros finales

#table(
  columns: (auto, auto, auto, 1fr),
  align: (left, left, center, left),
  table.header([*Modelo*], [*Parámetro*], [*Valor*], [*Por qué*]),
  [RF], [entrada], [seca + húmeda], [Elegida en validación frente a solo seca],
  [RF], [`n_estimators`], [500], [Elegido en validación entre 300, 400 y 500],
  [RF], [`max_depth`], [sin límite], [No es riesgoso en un forest -- la reducción de
    varianza viene de promediar árboles, no de podar],
  [CNN], [entrada], [3×3, seca + húmeda], [Elegida en validación frente a 3×3 seca],
  [CNN], [arquitectura], [32→64→128], [Red chica y propia, no un backbone pre-entrenado],
  [CNN], [batch size], [32], [Elegido en validación entre 8, 16, 32 y 64],
  [CNN], [learning rate], [0,0001], [Elegido en validación entre 0,0001, 0,0003 y 0,001, alrededor del default de Adam @kingma2014adam],
  [CNN], [dropout], [0,3], [Elegido en validación entre 0,3 y 0,6],
  [CNN], [épocas / paciencia], [100 / 10], [Corta tras 10 épocas sin mejora en validación],
)

Las variantes y los hiperparámetros se eligen en el split de validación, con una grilla
completa por variante, 5 semillas por configuración y reglas escritas antes de puntuar,
cuyo texto queda registrado en MLflow con su huella SHA-256. Si el valor elegido cae en el
borde de la grilla, ese eje se extiende un paso. Entre variantes, la más simple (solo época
seca) se mantiene salvo que otra la supere por más de la desviación estándar combinada. El
test se evalúa una sola vez, con lo ya elegido; el detalle está en los resultados de
Fase 1. En todo el trabajo, la dispersión entre semillas se reporta como desvío muestral.

== Detección de cambio y evaluación de exactitud

*Cambio bosque/no bosque con post-proceso pre-registrado.* El primer mapa de cambio del AOI
reportaba 1.007 ha de pérdida de bosque; Hansen Global Forest Change registra 0,1 ha en
2020-2023 y MapBiomas no coincide con ninguno de esos píxeles, así que era casi todo error
de comisión. El producto principal pasó a ser el cambio bosque/no bosque, y el post-proceso
se eligió con una regla escrita y registrada en MLflow antes de puntuar: entre 12
configuraciones, la que menos pérdida falsa deja en el AOI sin perder más de la mitad de la
pérdida confirmada en un área de desarrollo con deforestación real. Con la CNN final
quedó elegida confianza ≥ 0,9 en ambas fechas, persistencia en 2022 y unidad mínima de
mapeo: pérdida mapeada de 8,1 ha. (Con CNN anteriores, la misma regla había dejado 81,9 ha
y 7,6 ha.)

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

