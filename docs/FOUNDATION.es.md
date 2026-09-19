# Fundamento del proyecto

*Idiomas: [English](FOUNDATION.md) | **Español***

## El problema

Generar un Reporte de Monitoreo para un proyecto REDD+ en el Chaco paraguayo hoy combina criterio manual de un técnico GIS, herramientas de clasificación semi-automática, y plataformas de monitoreo satelital que ya corren a escala (Global Forest Watch/Global Nature Watch, el propio MapBiomas). Ninguna de estas da evidencia por predicción individual: la biomasa/carbono se calcula con métodos heterogéneos, y el auditor (VVB) revisa el informe resultante como una caja negra, sin evidencia trazable de por qué un área específica se clasificó como desmonte — sea que esa clasificación haya salido de una persona o de un algoritmo — ni de cómo se llegó a la cifra de toneladas de CO2.

Esto genera dos problemas concretos:

1. **Costo y tiempo:** semanas y miles de dólares solo en esta etapa, antes de que intervenga el auditor.
2. **Falta de trazabilidad:** no hay forma sistemática de auditar *por qué* un sistema (humano o automático) concluyó que hubo o no deforestación, ni de contrastar si las hectáreas y toneladas reclamadas por un proyecto coinciden con lo observable por satélite. Las evaluaciones independientes de proyectos REDD+ de primera generación documentan una sobreemisión sustancial de créditos, pero la ubican sobre todo en cómo se construyó la línea base (áreas de referencia y modelado ex ante) y no en cómo se midió la cobertura forestal (Swinfield et al., 2026).

## La pregunta de investigación

> ¿Es posible construir, sobre imágenes Sentinel-2 y productos satelitales abiertos, un pipeline que clasifique cobertura de suelo con evidencia interpretable para cada predicción, y que traduzca el cambio detectado en una estimación de toneladas de CO2 asociadas, de forma que tanto la clasificación como la cifra de carbono sean auditables y no una caja negra?

El sistema trabaja a nivel de cobertura de suelo sobre píxeles de 10m (superficie/hectáreas), no a nivel de árbol individual. REDD+ y el Chaco son el caso de estudio usado para validar esto — elegidos porque REDD+ tiene un problema de credibilidad documentado y específico a ese tipo de crédito (ver Justificación más abajo), no porque se asuma que el enfoque solo funciona para REDD+ o solo en esta región.

**Lo que este proyecto efectivamente pone a prueba, en vez de asumir:**

- Si una CNN supera de forma significativa a un baseline más simple (Random Forest) en esta tarea de clasificación — un resultado negativo acá es un hallazgo válido, no un fracaso del proyecto.
- Si los heatmaps de Grad-CAM se sostienen como evidencia de auditoría coherente y útil sobre estos datos específicos. Los métodos de interpretabilidad suelen validarse en condiciones distintas a la vegetación seca y dispersa del Chaco, así que no se asume que esto se transfiera sin más.
- Si una estimación de carbono calibrada por satélite (altura de dosel pretrained + GEDI) produce una cifra defendible para un proyecto real registrado, dado los sesgos ya documentados de los modelos subyacentes en vegetación de dosel bajo.
- Si un modelo de deep learning espaciotemporal supera de forma significativa a un baseline clásico CA-Markov al predecir cambio futuro de cobertura — la misma prueba de "¿la complejidad extra se justifica?" aplicada a la extensión predictiva (ver punto 10 más abajo), en espejo con la comparación CNN vs. Random Forest.

## Objetivo general

Evaluar un pipeline candidato de verificación satelital para el mercado de créditos de carbono del Chaco paraguayo: clasificación de cobertura de suelo con una CNN, puesta a prueba contra un baseline más simple, con una capa candidata de interpretabilidad pensada para hacer auditable la detección de cambios, combinada con una estimación de biomasa/carbono/CO2 calibrada sobre productos satelitales abiertos — como prototipo para evaluar la viabilidad técnica de automatizar y hacer auditable la etapa de generación del reporte de monitoreo (MRV).

## Enfoque en evaluación

Los siguientes componentes conforman el enfoque que se pone a prueba, no un sistema terminado que se presenta como validado. Cada uno tiene un paso de evaluación explícito, porque su idoneidad para estos datos particulares —vegetación del Chaco, un tipo de crédito, un caso de estudio— todavía no está establecida.

1. **Dataset:** imágenes Sentinel-2 + MapBiomas Chaco como ground truth, sobre un área de estudio acotada. Caso de estudio: Corazón Verde del Chaco (VCS 2611), un proyecto REDD+ real y registrado — elegido porque permite validar el enfoque de auditoría contra cifras reales y públicamente reclamadas, no porque el método sea específico de REDD+. Boundary aproximado (ver `openspec/specs/study-area/`), confirmado por el tutor, chequeo de factibilidad GEDI aprobado.
2. **Candidato de clasificación:** una CNN adaptada a las 13 bandas espectrales de Sentinel-2 (no solo RGB), con índices espectrales (NDVI y similares) como canales adicionales — evaluada contra el baseline del punto siguiente, no asumida superior por defecto.
3. **Baseline:** Random Forest sobre atributos espectrales, corrido específicamente para probar si la complejidad adicional de la CNN se justifica.
4. **Comparación temporal:** clasificar dos o más momentos y generar un mapa de cambio (hectáreas que pasaron de bosque a otra clase) — el mecanismo de detección de cambio, independiente de cuál clasificador de los puntos 2–3 resulte mejor.
5. **Candidato de interpretabilidad:** Grad-CAM, generando un mapa de calor por predicción pensado para mostrar qué región de la imagen sustenta cada clasificación. Elegido por sobre otros métodos de XAI según la literatura previa (menor costo computacional, interpretabilidad comparable; Kakogeorgiou y Karantzalos, 2021) — pero su coherencia real sobre estos datos se evalúa, no se asume (ver objetivo 7).
6. **Estimación de carbono:** para las hectáreas de cambio detectadas, un pipeline candidato para estimar toneladas de CO2 asociadas:
   - **Altura de dosel por inferencia** (sin reentrenar), corriendo el modelo pretrained ETH Zürich Global Canopy Height (10m, año base 2020) y filtrando estimaciones con la capa de incertidumbre del propio modelo — su paper reporta sesgo de sobreestimación en canopias bajas (≈2 m entre 5 y 20 m, y algo de sobreestimación bajo 5 m), un rango común en la vegetación chaqueña, aunque también reporta un sesgo medio bajo (<1 m) para bosque seco tropical — un promedio por bioma validado contra GEDI y no contra mediciones de campo, así que estos resultados necesitan escrutinio en el Chaco y no deben tomarse al pie de la letra.
   - **Calibración altura → biomasa** con una regresión potencial log-log (`AGBD = a · altura^b`) ajustada contra footprints GEDI L4A en la región de estudio — condicionada a un chequeo temprano de factibilidad sobre densidad/calidad de footprints GEDI en el Chaco.
   - **Conversión biomasa → carbono → CO2e** con factores estándar IPCC (ver fórmula abajo), incluyendo el factor de biomasa subterránea (root-to-shoot) para no reportar solo carbono aéreo.
7. **Evaluación:** cuantitativa (accuracy, IoU/Dice, matriz de confusión, comparación CNN vs. baseline) y cualitativa (si los heatmaps de Grad-CAM realmente coinciden con el cambio conocido, calidad del ajuste altura-biomasa por validación cruzada) — acá es donde los puntos 2 y 5 obtienen una respuesta real, no solo una intención declarada.
8. **Prototipo funcional del flujo completo:** imagen satelital → clasificación → comparación temporal → heatmap → estimación de CO2 asociado, presentable en el simposio independientemente de cuáles decisiones de modelo específicas terminen sosteniéndose.
9. **Demo de auditoría (caso de estudio):** correr el pipeline completo sobre Corazón Verde del Chaco y comparar hectáreas/CO2 observados por satélite contra las cifras observadas en los reportes de monitoreo públicos del proyecto. Es una verificación independiente de la parte *observada* del reporte (deforestación dentro del área del proyecto y stock de carbono), con evidencia por predicción. No evalúa adicionalidad ni la línea base, donde las evaluaciones independientes ubican la mayor parte de la sobreemisión (Swinfield et al., 2026), así que por sí sola no puede establecer si los créditos de este proyecto se sobreemitieron. Es un caso de estudio de un proyecto puntual — no una afirmación general sobre el mercado REDD+ en su conjunto.
10. **Extensión predictiva (nueva respecto a la metodología de 6 fases originalmente documentada por el tutor):** más allá de validar el cambio pasado (puntos 3-4-6-9, todos retrospectivos), proyectar el cambio futuro de cobertura y su CO2e asociado para el área de estudio, con la misma postura de "baseline vs. candidato" que los puntos 2-3:
    - **Baseline:** CA-Markov — una matriz de transición de Markov (frecuencia histórica de cambio de clase, a partir de una serie multi-año de MapBiomas) combinada con un autómata celular que asigna ese cambio a píxeles específicos usando reglas de vecindario y un mapa de idoneidad (capas de drivers como caminos, distancia a bordes ya desmontados, terreno, tenencia de tierra). Interpretable por construcción — la matriz de transición y los pesos de idoneidad son en sí mismos la explicación, sin necesitar una capa de interpretabilidad aparte.
    - **Candidato:** un modelo de deep learning espaciotemporal (ConvLSTM o 3D-CNN) sobre la pila de mapas multi-año, evaluado contra el baseline CA-Markov vía backtesting (entrenar con años 1..N-1, predecir un año N ya conocido, puntuar con Figure of Merit/Kappa) — no asumido superior por defecto, misma postura que el punto 2 vs. el punto 3.
    - La cifra de CO2e proyectada reutiliza los números de densidad de carbono por tipo de transición ya calculados para el cambio observado (puntos 4-6), aplicados sobre los píxeles que cada modelo predice que van a cambiar — no requiere imágenes satelitales sintéticas del futuro ni volver a correr la inferencia de altura de dosel.
    - Esta extensión fue propuesta por el tutor en conversación y no forma parte de su metodología originalmente documentada (`research_docs/METODOLOGIA_TUTOR.md`, enteramente retrospectiva/basada en stock).

### Validación (si hay datos disponibles)

Contraste opcional contra ecuaciones alométricas locales publicadas para Paraguay, o mediciones de campo (posible colaboración con A Todo Pulmón Paraguay / Colosos de la Tierra), en vez de depender solo de GEDI.

### Fórmula de estimación de carbono

```
AGBD (Mg/ha)      = a · H^b                 — regresión log-log, H = altura de dosel (m), calibrada contra GEDI L4A
AGB_total (Mg/ha) = AGBD × (1 + R)           — R = ratio raíz-tallo IPCC (~0.20–0.24 según clase de biomasa/zona ecológica)
Carbono (Mg C/ha) = AGB_total × 0.47         — fracción de carbono por defecto (IPCC 2006 GL Vol.4)
CO2e (Mg CO2/ha)  = Carbono × 3.67           — relación de pesos moleculares CO2:C (44/12)

ΔCO2e (Mg CO2) = Σ sobre píxeles de cambio [ CO2e_densidad_antes − CO2e_densidad_después ] × área_ha
```

`ΔCO2e` es la cifra que efectivamente le importaría al mercado de carbono (toneladas evitadas/emitidas) si el pipeline se sostiene bajo evaluación — es lo que conecta la clasificación (punto 4) con la estimación de carbono (punto 6).

## Qué resolvería la interpretabilidad, si se sostiene (y qué no resolvería de todos modos)

Grad-CAM, incluso si sus heatmaps resultan coherentes sobre estos datos, no detectaría fraude directamente. Lo que sí haría es convertir una afirmación de clasificación ("esto es desmonte") en algo verificable con evidencia visual trazable, reduciendo el costo de auditar y haciendo visibles errores sistemáticos del modelo — por ejemplo, una nube confundida con desmonte. Lo que no haría, incluso funcionando como se espera: verificar que el ground truth de entrenamiento sea correcto en sí mismo, impedir la manipulación intencional de las imágenes de entrada, o reemplazar la validación de campo.

## Alcance

**Incluido:** clasificación con CNN sobre un área acotada del Chaco evaluada contra un baseline Random Forest, Grad-CAM evaluado cualitativamente como mecanismo de auditoría, una estimación de carbono/CO2 calibrada con GEDI, una extensión predictiva (CA-Markov como baseline vs. deep learning espaciotemporal como candidato, ver punto 10 más arriba), una demo de auditoría contra un proyecto real registrado, un prototipo funcional/demostrable, documento y defensa siguiendo la estructura estándar del Manual de Postgrado.

**Fuera de alcance:** reemplazar al auditor VVB o generar un reporte legalmente válido ante Verra, procesar el Chaco completo o construir un sistema de monitoreo nacional en tiempo real, construir el producto SaaS completo (ingesta automática, dashboard, API para terceros, polígonos libres dibujados por el usuario en cualquier parte de la región), evaluar la adicionalidad o la línea base de un proyecto (por ejemplo, contra áreas de control emparejadas), que queda como trabajo futuro, trabajo de campo propio para validación in situ, pools de carbono más allá de biomasa aérea y subterránea (madera muerta, hojarasca y carbono del suelo quedan fuera y documentados como limitación).

El recorte a REDD+ y a un proyecto puntual como caso de estudio es una decisión de alcance para que el TFM sea abordable en el tiempo disponible — no una afirmación de que el enfoque de clasificación y estimación de carbono solo funcione para REDD+. Si generaliza a otros tipos de crédito o regiones queda explícitamente sin probar, y se deja como trabajo futuro.

**Sobre la generalización dentro del Chaco específicamente:** la demo de caso de estudio (punto 9) está fija a un AOI, pero eso es una decisión de alcance sobre la *demo*, no un techo técnico duro sobre el *modelo*. La muestra de entrenamiento del clasificador y la muestra de calibración GEDI se toman deliberadamente de una huella más amplia que el único AOI del caso de estudio (tanto MapBiomas como GEDI tienen cobertura de todo el Chaco, no solo sobre Corazón Verde del Chaco), así que el pipeline entrenado es candidato a generalizar a otras áreas dentro del Chaco paraguayo — puesto a prueba, no asumido, vía un chequeo de accuracy sobre una sub-área held-out durante la evaluación (punto 7), no construyendo la herramienta interactiva multi-polígono que queda explícitamente fuera de alcance arriba. Generalizar más allá del Chaco paraguayo (otros países del Chaco, otros biomas) queda sin probar y fuera de alcance.

---

Este documento es un resumen público del planteamiento. El detalle completo (estado del arte, marco legal, metodología del tutor, bitácora de decisiones) se mantiene en notas de investigación privadas fuera de este repositorio.
