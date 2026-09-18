# Arquitectura del pipeline de verificación satelital

Este documento presenta la arquitectura del pipeline de verificación satelital para créditos de
carbono en el Chaco paraguayo: las fuentes de datos utilizadas, las áreas de estudio definidas y
la razón de cada una, el procesamiento aplicado (modelos y técnicas) y los productos derivados
(comparación de cobertura, estimación de carbono observado y proyectado).

## Diagrama general

```mermaid
flowchart TD
    subgraph AOIS["Áreas de estudio"]
        AOI_CASO["AOI del caso de estudio<br/>Corazón Verde del Chaco (VCS 2611)<br/>~20.589-20.641 ha<br/>proyecto REDD+ registrado"]
        FOOTPRINT["Huella de muestreo<br/>Región Occidental, Paraguay<br/>~24.045.848 ha"]
        HELDOUT["Sub-área held-out<br/>Filadelfia, Boquerón (aprox.)<br/>~164.671 ha"]
    end

    subgraph CLASS["Clasificación (variable discreta)"]
        S2A["Sentinel-2, 2019 y 2023"]
        CNNRF["CNN vs. Random Forest<br/>bosque / pasto / cultivo<br/>ventana 33×33 px"]
        CHANGE["Cambio de cobertura<br/>bosque → no-bosque"]
        S2A --> CNNRF --> CHANGE
    end

    subgraph REGR["Regresión (variable continua)"]
        S2B["Sentinel-2, 12 bandas"]
        ETHGEDI["Altura de dosel (ETH)<br/>+ calibración GEDI L4A"]
        CARBONPIX["Carbono por unidad de área<br/>Mg CO2e/ha"]
        S2B --> ETHGEDI --> CARBONPIX
    end

    FOOTPRINT --> S2A
    FOOTPRINT --> S2B

    DELTA["CO2e observado<br/>(sobre el AOI del caso de estudio)"]
    CHANGE --> DELTA
    CARBONPIX --> DELTA

    PDD["Cifras declaradas por el proyecto<br/>(PD público, registro Verra)"]
    AUDIT["Comparación satelital vs. declarado"]
    DELTA --> AUDIT
    PDD --> AUDIT

    subgraph PRED["Predicción, cambio futuro"]
        HIST["Serie histórica MapBiomas<br/>1985-2023"]
        DRIVERS["Variables explicativas"]
        MARKOVDL["CA-Markov vs. modelo<br/>espaciotemporal"]
        FUTURECHANGE["Cambio de cobertura proyectado"]
        HIST --> MARKOVDL
        DRIVERS --> MARKOVDL
        MARKOVDL --> FUTURECHANGE
    end

    FOOTPRINT --> HIST

    FUTUREDELTA["CO2e proyectado"]
    FUTURECHANGE --> FUTUREDELTA
    CARBONPIX -.reutiliza delta histórico.-> FUTUREDELTA

    EVALGEN["Evaluación de generalización<br/>+ verificación vs. ESA WorldCover"]
    HELDOUT --> EVALGEN

    classDef aoi fill:#1e3a8a,stroke:#60a5fa,color:#fff
    classDef classif fill:#7c2d12,stroke:#c2410c,color:#fff
    classDef regress fill:#065f46,stroke:#10b981,color:#fff
    classDef merge fill:#4c1d95,stroke:#7c3aed,color:#fff
    classDef predict fill:#78350f,stroke:#d97706,color:#fff
    classDef futuremerge fill:#3b0764,stroke:#a78bfa,color:#fff,stroke-dasharray: 5 5
    classDef audit fill:#164e63,stroke:#22d3ee,color:#fff

    class AOI_CASO,FOOTPRINT,HELDOUT aoi
    class S2A,CNNRF,CHANGE classif
    class S2B,ETHGEDI,CARBONPIX regress
    class DELTA merge
    class HIST,DRIVERS,MARKOVDL,FUTURECHANGE predict
    class FUTUREDELTA futuremerge
    class AUDIT,EVALGEN,PDD audit
```

Las secciones siguientes explican cada bloque de este diagrama en detalle: de dónde sale cada
dato, cómo se procesa y para qué se usa el resultado.

## 1. Fuentes de datos

| Fuente | Qué es | Cobertura temporal/espacial | Por qué esta fuente y no una alternativa |
|---|---|---|---|
| **Sentinel-2 L2A** (Copernicus/ESA) | Imágenes multiespectrales, 13 bandas, 10 m de resolución nativa, revisita nominal de 5 días | Global; en este proyecto, usable de forma densa desde 2019 sobre el área de trabajo (chequeo empírico: 14 escenas en 2018 contra 73 en 2019 sobre el mismo polígono) | Resolución más fina que Landsat (30 m) y acceso a bandas red-edge/SWIR que un RGB simple no tiene. Se usa L2A (reflectancia de superficie) y no L1C (tope de atmósfera, sin corregir) por tres razones concretas: (1) la comparación temporal 2019 vs. 2023 necesita que los valores de reflectancia sean comparables entre fechas — con L1C, condiciones atmosféricas distintas en cada fecha meterían diferencias que no son cambio real de cobertura; (2) NDVI y otros índices espectrales solo son físicamente válidos sobre reflectancia de superficie, no sobre valores distorsionados por dispersión atmosférica; (3) MapBiomas (la etiqueta) ya sale de reflectancia de superficie de Landsat corregida — usar L2A mantiene la misma magnitud física de ambos lados del par imagen-etiqueta |
| **MapBiomas Chaco, Colección 5** | Clasificación de cobertura de suelo, un raster por año (1985-2023, 39 capas), 30 m, derivado de Landsat | Gran Chaco americano; en este proyecto, recortado a Paraguay | Es el único producto abierto con clasificación anual a escala de bioma y con suficiente profundidad histórica para modelar tendencia. Además evita tener que digitalizar el ground truth a mano, algo inviable en el volumen que pide entrenar un clasificador |
| **ESA WorldCover v200** | Cobertura de suelo global, 10 m, año de referencia 2021 | Global | Su resolución nativa coincide con la de Sentinel-2, a diferencia de MapBiomas (30 m). Se usa solo como verificación independiente sobre un área que nunca entra en entrenamiento; mezclarlo con las etiquetas de entrenamiento sería circular |
| **ETH Global Canopy Height** (Lang, Jetz, Schindler y Wegner, 2023, *Nature Ecology & Evolution*) | Modelo pre-entrenado que infiere altura de dosel a partir de Sentinel-2, con capa de incertidumbre propia, año base 2020 | Global | Se prefirió sobre la alternativa Potapov/GLAD (UMD) porque entrega altura e incertidumbre en bruto y deja la calibración a biomasa como un paso propio, auditable, en vez de heredar una calibración ya resuelta por terceros |
| **GEDI L4A** (`GEDI_L4A_AGB_Density_V3`, NASA/ORNL DAAC) | Densidad de biomasa aérea medida por lidar espacial, punto por punto | Abril 2019 a marzo 2023 sobre el AOI del caso de estudio (39 gránulos, 3.823 footprints de calidad tras filtrar por `l4a_quality_flag_rel3`, unos 18,6 footprints de calidad cada 100 ha) | Es la referencia estándar de biomasa aérea satelital, revisada por pares, y es el mismo dato contra el cual el propio modelo ETH fue validado en su publicación original |
| **FAO GAUL 2015, nivel 1** | Límites administrativos oficiales por país y departamento | Paraguay: Alto Paraguay, Boquerón y Presidente Hayes (Región Occidental) | Ya está disponible como asset nativo en Google Earth Engine, así que define la huella de muestreo ampliada (sección 2) sin necesitar un archivo geoespacial aparte |
| **Variables explicativas para el modelo predictivo** (distancia a red vial, distancia al borde de cambio observado, pendiente del terreno, tenencia de tierra o estatus de área protegida) | Capas de contexto geográfico, no series de cobertura | Pendiente de definición final | La distancia al borde de cambio se puede derivar directamente de la propia serie MapBiomas. Red vial y pendiente tienen fuentes estándar (OpenStreetMap, SRTM) que todavía no se incorporaron. Tenencia de tierra y área protegida no tienen fuente identificada por ahora: queda como pendiente explícito, no resuelto por omisión |

**Nota sobre los "niveles" de procesamiento (L1C, L2A, L4A).** El concepto general de niveles
(0 a 4: dato crudo → calibrado → variable geofísica derivada → grilla uniforme → producto de
modelo) viene de la convención de NASA/EOSDIS y lo siguen distintas misiones — por eso GEDI L4A
("Level 4A") y Sentinel-2 L2A comparten la lógica de fondo, aunque midan cosas completamente
distintas. Lo que **no** es universal es el detalle fino de cada letra: en Sentinel-2, L1C es
reflectancia "tope de atmósfera" (sin corregir) y L2A es reflectancia de superficie ya corregida
atmosféricamente (algoritmo Sen2Cor, propio de Copernicus); Landsat tiene su propio Level-1/Level-2
con su propio algoritmo, no intercambiable byte a byte con el de Sentinel-2 pese a compartir el
mismo número de nivel.

## 2. Áreas de estudio: por qué son tres y no una

El pipeline trabaja sobre tres extensiones geográficas distintas. Cada una cumple una función que
las otras dos no cubren; no son alternativas entre sí ni una versión simplificada de otra.

**AOI del caso de estudio, Corazón Verde del Chaco (VCS 2611).** El boundary es aproximado,
digitalizado a mano a partir de la Figura 2.2 del Project Description público del proyecto: no
existe un shapefile ni KML público descargable, y el Registro Verra funciona como aplicación web
que no se puede scrapear directamente. El área calculada ronda las 20.589 ha por cálculo geodésico
con `pyproj`, o 20.641 ha según el cálculo propio de Google Earth Engine (la diferencia del 0,25 %
viene del método de cálculo de área geodésica de cada herramienta, no de un error de
digitalización). Se validó contra la superficie inicial declarada en el PD, 20.515,0 ha, con una
diferencia del 0,8 %. Esta es la única de las tres áreas con cifras de hectáreas y CO2
públicamente reclamadas ante un registro, así que es la que habilita la comparación satelital
contra lo declarado (sección 4), y por eso también la más verificable contra un dato externo real.
Sobre ella se confirmó además la factibilidad de GEDI L4A, con densidad de footprints de calidad
muy por encima del mínimo que pide la regresión altura-biomasa.

**Huella de muestreo, departamentos de la Región Occidental.** El AOI del caso de estudio, aunque
sea el objeto de la auditoría, resulta insuficiente como base de entrenamiento: se verificó que no
contiene un solo píxel de la clase cultivo, ni en 2019 ni en 2023 (su dinámica de cambio observada
es bosque contra pastura). Entrenar el clasificador solo con el AOI dejaría esa clase sin ningún
ejemplo real. La huella de muestreo, los tres departamentos que forman el Chaco paraguayo, resuelve
esto sin sumar ninguna fuente de datos nueva, porque tanto MapBiomas como GEDI ya cubren todo el
Chaco de forma nativa. El AOI del caso de estudio queda geográficamente contenido dentro de esta
huella, en el departamento de Alto Paraguay.

**Sub-área held-out, Filadelfia, Boquerón.** Un recorte de unos 40×40 km dentro de la huella de
muestreo, excluido a propósito de todo entrenamiento, validación o ajuste de hiperparámetros. Las
coordenadas son aproximadas, con el mismo criterio que el AOI del caso de estudio: no hay un límite
catastral público exacto. Se eligió por ser una zona de frontera agrícola conocida (colonias
menonitas), y esto se confirmó con datos reales: contiene cobertura de cultivo genuina (2.476.960
píxeles de 10 m según ESA WorldCover), algo que el AOI del caso de estudio no tiene. Cumple dos
funciones que ninguna otra área cubre: evaluar si el clasificador entrenado generaliza a una región
geográficamente distinta dentro del mismo bioma, y servir de zona de verificación de exactitud
independiente contra ESA WorldCover, con ejemplos reales de cultivo que el AOI del caso de estudio
no posee. Se confirmó una superposición de 0 ha con el AOI del caso de estudio.

## 3. Procesamiento: qué se hace con cada fuente

### 3.1 Clasificación de cobertura (variable discreta, componente retrospectivo)

Los datos de entrenamiento se muestrean sobre la huella de muestreo, no solo sobre el AOI del caso
de estudio, por lo explicado en la sección 2. Cada ejemplo de entrenamiento es una ventana
Sentinel-2 de 33×33 píxeles centrada en un bloque de 3×3 píxeles nativos (10 m) que corresponde
exactamente a un píxel de MapBiomas (30 m). Esa correspondencia 3×3 sale directo de la relación de
resolución (30 m equivale a 3 × 10 m) y se obtiene reproyectando MapBiomas sobre la grilla propia
de Sentinel-2. La ventana de 33×33 px es la que ve el modelo como entrada, para darle contexto
espacial real; el bloque de 3×3 sigue siendo únicamente la unidad de alineación con la etiqueta. La
clase no incluye "desmonte" como cuarta categoría: MapBiomas clasifica el estado de la cobertura
por año, no eventos de tala, así que el cambio se obtiene comparando dos clasificaciones de fechas
distintas, en vez de predecirse directamente.

Las divisiones de entrenamiento, validación y prueba se asignan por bloque espacial (~2 km,
agrupados por clase) y no por punto individual: dos parches a 330 m o menos de distancia pueden
corresponder al mismo terreno real, así que una asignación puramente aleatoria por punto arriesga
contaminación entre conjuntos. Un chequeo posterior de distancia mínima confirma que ningún par de
parches entre conjuntos distintos queda por debajo de esa distancia. El muestreo de entrenamiento
se apoya en la proyección nativa de MapBiomas, no en una reproyección hacia la grilla de
Sentinel-2: la huella de muestreo cruza dos husos UTM (20S y 21S), y forzar toda el área a un único
huso arbitrario distorsionaría los puntos alejados de esa zona. La correspondencia exacta 3×3 se
demuestra de forma acotada sobre el AOI del caso de estudio, que sí queda dentro de un único huso.

Los composites de cada período se arman enmascarando nubes por-píxel vía la banda SCL (Scene
Classification Layer), no por el metadato más grueso de nubosidad por escena. Para 2019: 25 escenas,
36,4 % de nubosidad promedio por escena, 0 % de hueco residual tras el compositing. Para 2023: 24
escenas, 44,2 %, también 0 % de hueco residual. Ambos muy por debajo del umbral de 5 % fijado como
criterio → no hace falta sumar Sentinel-1 SAR para cubrir huecos.

**Hiperparámetros de entrenamiento, con su criterio de elección**

| Modelo | Parámetro | Valor | Criterio |
|---|---|---|---|
| Random Forest | Número de árboles | 400 | Rango estándar (300-500): la reducción de varianza tiene retornos decrecientes pasados unos cientos de árboles |
| Random Forest | Profundidad máxima | Sin límite | La reducción de varianza de un bosque aleatorio viene de promediar muchos árboles individualmente sobreajustados, no de limitar la profundidad de cada uno |
| Random Forest | Variables de entrada | 12 bandas + NDVI del píxel central del parche | No se usa la ventana espacial completa: el modelo no puede aprovechar el contexto espacial que sí usa la CNN, así que dársela no aportaría una comparación más justa, solo mayor dimensionalidad |
| CNN | Arquitectura | 3 bloques convolucionales (32/64/128 filtros) + pooling global + dropout | Deliberadamente pequeña, no un modelo pre-entrenado grande: mantiene legible una eventual capa de interpretabilidad y no oscurece la comparación contra el baseline |
| CNN | Tamaño de lote | 32 | Valor estándar para un conjunto de entrenamiento de este orden (~840 ejemplos) |
| CNN | Tasa de aprendizaje | 0,001 | Valor por defecto recomendado en la publicación original del optimizador Adam (Kingma y Ba, 2014) |
| CNN | Épocas máximas / paciencia | 100 / 10 | El entrenamiento se corta si la pérdida de validación deja de mejorar durante 10 épocas seguidas, en vez de fijar a priori un número de épocas arbitrario |
| CNN | Dropout | 0,4 | Rango estándar (0,3-0,5) para un conjunto de entrenamiento acotado (~280 ejemplos por clase), donde el riesgo de sobreajuste es real |
| CNN | Aumentado de datos | Rotaciones de 90°/180°/270° y espejado | Válido para imágenes satelitales vistas cenitalmente. No se aplica aumentado de color o brillo: los valores de reflectancia de Sentinel-2 tienen significado físico, y distorsionarlos podría dañar la señal en lugar de mejorar la generalización |

El criterio de comparación entre modelos se fija antes de observar resultados: ambos se entrenan y
evalúan en 5 corridas con distinta semilla aleatoria (que afecta la inicialización y el muestreo
interno de cada modelo, no la partición de datos, que permanece fija entre corridas), se mide el
F1 promediado por clase, y la CNN solo se considera superior si su F1 medio excede al de Random
Forest en más de una desviación estándar combinada entre ambas distribuciones de corridas.

### 3.2 Estimación de carbono (variable continua, componente retrospectivo)

La calibración altura-biomasa se ajusta una sola vez, usando los footprints GEDI L4A disponibles
sobre el AOI del caso de estudio (2019-2023), y después se aplica a la altura de dosel inferida
sobre cualquier año dentro de esa ventana temporal. La conversión biomasa-carbono-CO2e usa los
factores estándar del IPCC: fracción de carbono 0,47, factor raíz-tallo entre 0,20 y 0,24 según la
zona ecológica, y relación molecular CO2:C de 3,67. Se incluye biomasa subterránea para no reportar
solo el carbono aéreo.

### 3.3 Predicción de cambio futuro

"Serie histórica multianual" se refiere puntualmente a usar la profundidad temporal completa de
MapBiomas Chaco (39 capas anuales, 1985-2023), en lugar del par de fechas que usa la clasificación
(3.1). Con dos fechas solo se sabe si hubo o no cambio; con la serie completa, CA-Markov puede
construir una matriz de transición basada en la frecuencia histórica real, y el modelo
espaciotemporal candidato puede aprender una tendencia a lo largo del tiempo, no solo un salto
puntual entre dos momentos.

"Variables explicativas" son capas estáticas o casi estáticas de contexto geográfico, no series de
cobertura, que informan dónde dentro del espacio es más probable que se concentre el próximo
cambio, dado un patrón histórico (por ejemplo, la cercanía a infraestructura vial o a un borde de
cambio ya observado). El estado real de disponibilidad de estas capas está en la sección 1.

## 4. Productos: qué se calcula a partir de todo esto

**CO2e observado y auditoría.** Se calcula solo sobre los píxeles del AOI del caso de estudio,
aunque el modelo se haya entrenado con la huella de muestreo ampliada, y se contrasta contra las
hectáreas y toneladas de CO2 que el proyecto declaró públicamente ante Verra. Este es el resultado
central del componente retrospectivo.

**CO2e proyectado.** No hace falta imagen satelital futura ni volver a correr el modelo de altura
de dosel. Se reutiliza el delta de densidad de carbono ya calculado por tipo de transición
observada (3.2) y se aplica sobre los píxeles que el modelo predictivo marca como propensos a
cambiar. Si no existe un delta histórico calculado para el tipo de transición que se predice, el
valor se reporta como no disponible en vez de estimarse sin respaldo. Por eso en el diagrama esta
caja aparece con línea punteada: es una proyección apoyada en relaciones ya medidas, no una
observación nueva.

**Evaluación de generalización.** Se ejecuta sobre la sub-área held-out, nunca sobre el AOI del
caso de estudio ni sobre datos usados en entrenamiento. Combina dos verificaciones independientes:
la exactitud del clasificador en una región geográfica que nunca vio, y el contraste contra ESA
WorldCover.

## 5. Resultados: clasificación de cobertura, CNN contra Random Forest

**Resumen**: la CNN gana la comparación de precisión sobre el conjunto de prueba del área de
estudio (AOI); evaluada contra 3 sub-áreas geográficamente independientes, gana o empata en 2 de
las 3 y pierde claramente en la tercera (Filadelfia), por una razón identificada y específica de
paisaje, no una falla de generalización sin explicar. **La CNN queda confirmada como clasificador
operativo del sistema** (decisión cerrada el 2026-09-13, `phase1-classifier` tarea 4.4), con esa
limitación documentada explícitamente, no escondida.

### 5.1 Comparación de precisión sobre el AOI

Sobre el conjunto de prueba del AOI (~360 ejemplos, nunca usados en entrenamiento ni ajuste),
promediando 5 corridas con distinta semilla, sobre el dataset final (2.393 patches, 400 por
clase/período, sin fuga espacial verificada):

| Modelo | F1 macro promedio | Desviación estándar |
|---|---|---|
| Random Forest | 0,811 | 0,004 |
| CNN | 0,843 | 0,012 |

La diferencia (+0,032 a favor de la CNN) supera el umbral de una desviación estándar combinada
(0,009) fijado antes de correr el experimento. Por el criterio pre-registrado, **la CNN gana esta
comparación**, y lo hizo de forma consistente en 3 volúmenes/huellas de datos distintos probados
durante el desarrollo (ver la nota de trazabilidad al final de esta sección). Ambos modelos
muestran el mismo patrón de error: la confusión entre pasto y cultivo es sistemáticamente mayor
que la confusión de cualquiera de las dos con bosque.

### 5.2 Evaluación de generalización: 3 sub-áreas held-out independientes

El AOI por sí solo no prueba generalización geográfica — sus ejemplos de prueba salen de la misma
huella de entrenamiento. Se evaluaron ambos modelos, ya entrenados, contra 3 sub-áreas excluidas
por completo del entrenamiento, con topologías de paisaje distintas a propósito, cada una con 5
corridas de re-entrenamiento para tener una estimación real de varianza (no solo un número suelto):

| Región | Perfil de paisaje | RF (media ± desvío) | CNN (media ± desvío) | Resultado |
|---|---|---|---|---|
| Filadelfia (Boquerón) | Colonia agrícola menonita, bosque fragmentado | 0,829 ± 0,001 | 0,696 ± 0,021 | **RF gana, decisivo** (gana en las 5 semillas) |
| Bahía Negra (Alto Paraguay) | Bosque continuo, remoto | 0,611 ± 0,002 | 0,611 ± 0,016 | **Empate real** |
| Pozo Colorado (Presidente Hayes) | Ganadería, ruta Trans-Chaco | 0,661 ± 0,006 | 0,727 ± 0,021 | **CNN gana**, confirmado |

**Nota metodológica, vale la pena dejarla explícita**: la primera corrida de estas 3 regiones (una
sola semilla cada una) sugería "RF gana en 2 de 3" — con las 5 semillas, ese resultado en Bahía
Negra resultó ser ruido de una corrida particular que agarró a la CNN en su peor semilla; el
resultado real es un empate. Sin esa segunda pasada con varianza real, la conclusión habría
quedado mal reportada.

### 5.3 Por qué falla la CNN específicamente en Filadelfia

Se investigó la causa, no solo se documentó el número. Descartado: no es efecto de período (2019
y 2023 fallan a tasas casi idénticas), y no es falta de volumen de datos (duplicar el
entrenamiento a 400 ejemplos/clase/período no movió el resultado en Filadelfia, mientras que el
mismo cambio sí mejoró notablemente el bosque del propio AOI). Confirmado, con evidencia estadística
y visual: los puntos de bosque real que la CNN clasifica mal tienen una firma espectral SWIR de
canopy fino/degradado, y al inspeccionar los patches directamente, son sistemáticamente **franjas
angostas de bosque entre campos** (cortinas rompevientos, un rasgo estándar de la agricultura
menonita) que no llenan la ventana de 330m — no bloques de bosque contiguo. La CNN aprendió
"bosque" en parte como un patrón espacial de canopy grande y continuo, que no transfiere a bosque
fragmentado en tiras; Random Forest, al mirar solo el píxel central, no tiene ese modo de falla.

### 5.4 Decisión: clasificador operativo

**La CNN queda confirmada como clasificador operativo del sistema** (Grad-CAM, comparación temporal,
estimación de carbono se construyen sobre ella) — gana o empata en 3 de los 4 contextos evaluados
(AOI, Bahía Negra, Pozo Colorado) y pierde solo en Filadelfia, con una causa específica y
entendida. Se considera aceptable porque el destino real de despliegue (el AOI de Corazón Verde
del Chaco, Fase 4) está dentro de la huella de entrenamiento y no es un paisaje de colonia
fragmentada como Filadelfia (sección 2). **Limitación documentada, no oculta**: no confiar en la
CNN sin cruzar contra Random Forest para clasificar bosque en paisajes con fragmentación
estructuralmente similar a Filadelfia (franjas angostas, cortinas rompevientos). El resultado de
Random Forest no se descarta — sigue siendo la opción más robusta específicamente para ese tipo de
paisaje.

**Nota de trazabilidad**: este resultado pasó por 8 rondas de revisión de código y verificación
independiente (documentadas en `openspec/changes/phase1-classifier/tasks.md`), incluyendo dos
correcciones de rumbo reales — una fuga de datos entre períodos que originalmente mostraba un
empate técnico, y una corrección posterior de un resumen propio que sobreestimaba cuántas regiones
"generalizaba bien" la CNN. Cada corrección quedó documentada explícitamente en vez de absorbida
en silencio — es, en sí mismo, parte de cómo se construyó la confianza en el resultado final.

## 6. Justificación de cada modelo

**CNN.** Candidata de clasificación porque puede aprovechar contexto espacial (textura, patrones de
dosel) dentro de la ventana de 33×33 píxeles. Un clasificador que evalúa cada píxel de forma
aislada no puede sacarle provecho a eso por más ajustado que esté, así que si el CNN gana, gana por
una razón estructural real, no solo por mejor ajuste.

**Random Forest.** Baseline de clasificación. Es el estándar de comparación en teledetección para
esta tarea, barato de entrenar, y transparente por construcción: se puede ver qué variable pesó en
cada decisión sin agregar ninguna capa de interpretabilidad extra.

**Grad-CAM.** Se agrega sobre la CNN, pero no certifica que una predicción sea correcta: es un
mecanismo de auditoría. Para cada predicción genera un mapa de calor que muestra qué región de la
imagen sostuvo esa clasificación, y eso le permite a un revisor humano chequear si el modelo se
basó en evidencia razonable o si se equivocó de forma identificable, como confundir una nube con
una zona desmontada. No detecta manipulación intencional de las imágenes de entrada, no verifica la
calidad del propio ground truth de entrenamiento, y no reemplaza la validación de campo. Lo que
hace es bajar el costo de auditar una predicción, no eliminar la necesidad de hacerlo. Dado que la
comparación de la sección 5 no encontró una diferencia significativa entre la CNN y el baseline,
esta evaluación de Grad-CAM se sostiene como pregunta propia, independiente de cuál de los dos
modelos termine usándose en el resto del pipeline: la coherencia de sus mapas de calor sobre esta
vegetación se pone a prueba de todas formas, no solo si la CNN resultara claramente superior.

**Altura de dosel (ETH) más calibración GEDI L4A.** La justificación de la fuente ya está en la
sección 1. Como técnica, la calibración es una regresión potencial log-log simple (`AGBD = a·H^b`),
no un modelo de aprendizaje profundo: se elige porque es el método estándar en la literatura
(Asner y Mascaro, 2014) para calibrar una métrica lidar simple contra parcelas o footprints de
referencia.

**CA-Markov.** Baseline de predicción, elegido por ser el método establecido en la literatura de
modelado de cambio de uso de suelo. Es interpretable por construcción: la matriz de transición y
los pesos del mapa de idoneidad son en sí mismos la explicación del resultado, sin necesitar nada
extra encima.

**Modelo espaciotemporal (ConvLSTM o 3D-CNN).** Candidato de predicción. Puede aprender patrones de
cambio directamente de la serie histórica multianual, sin que alguien tenga que especificarle a
mano las reglas de vecindario ni los pesos de las variables explicativas que CA-Markov sí necesita.

## 7. Por qué clasificación, regresión y predicción

Estas tres componentes no son redundantes entre sí. Cada una responde una pregunta que las otras
dos no pueden responder, y juntas son el mínimo necesario para que el pipeline funcione como
herramienta de verificación y no solo como un ejercicio de clasificación de imágenes.

**Clasificación, ¿dónde?** Saber qué áreas cambiaron de cobertura es la base de cualquier sistema
de monitoreo satelital. Sin esto no hay forma de verificar si la superficie de bosque, pastura o
cultivo que declara un proyecto corresponde a lo que efectivamente se ve desde el satélite. Es
condición necesaria del resto del pipeline, aunque no suficiente por sí sola.

**Regresión, ¿cuánto?** La clasificación por sí sola entrega hectáreas, pero el mercado de créditos
de carbono transa en toneladas de CO2, no en superficie. Por más preciso que sea, un resultado de
clasificación no responde la pregunta que le importa al mercado ni permite contrastarlo contra las
cifras que un proyecto reclama públicamente. La regresión es lo que convierte un resultado espacial
en una magnitud que se puede verificar.

**Predicción, ¿qué sigue?** Los dos componentes anteriores son enteramente retrospectivos: sirven
para auditar cambio que ya pasó, pero no para anticipar dónde es probable que pase el próximo. Un
sistema que solo mira para atrás llega, por construcción, siempre después del hecho. Agregar una
capa predictiva lleva al sistema de un rol puramente forense a uno con valor para priorizar
recursos de monitoreo y fiscalización, sin debilitar el rigor retrospectivo en el que se apoya: la
proyección reutiliza las relaciones ya calibradas en el bloque retrospectivo en vez de sumar una
fuente de incertidumbre nueva.

En los tres componentes se aplica el mismo criterio de evaluación: un modelo simple e
interpretable como referencia (Random Forest, CA-Markov) contra un candidato más complejo (CNN,
modelo espaciotemporal), sin asumir de antemano que la complejidad adicional se traduce en mejor
desempeño. Que el modelo de referencia iguale o supere al candidato es, en este marco, un hallazgo
metodológico válido, no una falla del diseño.

## 8. Ítems abiertos

- Variables explicativas del modelo predictivo: tenencia de tierra y área protegida no tienen
  fuente identificada. Red vial y pendiente tienen fuente estándar disponible pero todavía no
  incorporada.
- ~~Cuál modelo usa el sistema como clasificador operativo (RF o CNN) está en revisión~~ — **resuelto,
  2026-09-13**: CNN confirmada como clasificador operativo, con la limitación de Filadelfia
  documentada explícitamente. Ver sección 5.4.
- Si el resultado de la sección 5 se sostiene al escalar a un conjunto de entrenamiento mayor ya
  no es una pregunta abierta: se probó directamente (`N_PER_CLASS` 200→400) y la conclusión se
  mantuvo — ver sección 5, nota de trazabilidad.
