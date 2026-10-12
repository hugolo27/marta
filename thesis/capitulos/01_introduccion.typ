= Introducción

== El problema

Generar un Reporte de Monitoreo para un proyecto REDD+ en el Chaco paraguayo hoy combina
criterio manual de un técnico GIS, herramientas de clasificación semi-automática, y
plataformas de monitoreo satelital que ya corren a escala (Global Forest Watch/Global
Nature Watch, el propio MapBiomas). Ninguna de estas da evidencia por predicción
individual: la biomasa/carbono se calcula con métodos heterogéneos, y el auditor (VVB)
revisa el informe resultante como una caja negra, sin evidencia trazable de por qué un
área específica se clasificó como desmonte -- sea que esa clasificación haya salido de
una persona o de un algoritmo -- ni de cómo se llegó a la cifra de toneladas de CO2.

Esto genera dos problemas concretos:

+ *Costo y tiempo*: semanas y miles de dólares solo en esta etapa, antes de que
  intervenga el auditor.
+ *Falta de trazabilidad*: no hay forma sistemática de auditar _por qué_ un sistema
  (humano o automático) concluyó que hubo o no deforestación, ni de contrastar si las
  hectáreas y toneladas reclamadas por un proyecto coinciden con lo observable por
  satélite. Las evaluaciones independientes de proyectos REDD+ de primera generación
  documentan una sobreemisión sustancial de créditos, pero la ubican sobre todo en cómo
  se construyó la línea base (áreas de referencia y modelado _ex ante_) y no en cómo se
  midió la cobertura forestal @swinfield2026overcrediting.

== Pregunta de investigación

#quote(block: true)[
  ¿Es posible construir, sobre imágenes Sentinel-2 y productos satelitales abiertos, un
  pipeline que clasifique cobertura de suelo con evidencia interpretable para cada
  predicción, y que traduzca el cambio detectado en una estimación de toneladas de CO2
  asociadas, de forma que tanto la clasificación como la cifra de carbono sean auditables
  y no una caja negra?
]

El sistema trabaja a nivel de cobertura de suelo sobre píxeles de 10m (superficie/
hectáreas), no a nivel de árbol individual. REDD+ y el Chaco son el caso de estudio usado
para validar esto -- elegidos porque REDD+ tiene un problema de credibilidad documentado
y específico a ese tipo de crédito, no porque se asuma que el enfoque solo funciona para
REDD+ o solo en esta región.

== Qué pone a prueba este proyecto, en vez de asumir

- Si una CNN supera de forma significativa a un baseline más simple (Random Forest) en
  esta tarea de clasificación -- un resultado negativo acá es un hallazgo válido, no un
  fracaso del proyecto.
- Si los heatmaps de Grad-CAM se sostienen como evidencia de auditoría coherente y útil
  sobre estos datos específicos.
- Si una estimación de carbono calibrada por satélite (altura de dosel _pretrained_ +
  GEDI) produce una cifra defendible para un proyecto real registrado.
- Si un modelo de _deep learning_ espaciotemporal supera de forma significativa a un
  baseline clásico CA-Markov al predecir cambio futuro de cobertura.

== Objetivo general

Evaluar un pipeline candidato de verificación satelital para el mercado de créditos de
carbono del Chaco paraguayo: clasificación de cobertura de suelo con una CNN, puesta a
prueba contra un baseline más simple, con una capa candidata de interpretabilidad pensada
para hacer auditable la detección de cambios, combinada con una estimación de
biomasa/carbono/CO2 calibrada sobre productos satelitales abiertos -- como prototipo para
evaluar la viabilidad técnica de automatizar y hacer auditable la etapa de generación del
reporte de monitoreo (MRV).

== Alcance

*Incluido*: clasificación CNN sobre un área acotada del Chaco evaluada contra un baseline
Random Forest, Grad-CAM evaluado cualitativamente como mecanismo de auditoría, una
estimación de carbono/CO2 calibrada con GEDI, una extensión predictiva (CA-Markov vs.
_deep learning_ espaciotemporal, confirmada como núcleo obligatorio por el tutor), una
demo de auditoría contra un proyecto real registrado (verificación independiente de la
parte _observada_ de sus reportes de monitoreo, sin evaluar adicionalidad ni línea base),
un prototipo funcional/demostrable, y este documento con su defensa.

*Fuera de alcance*: reemplazar al auditor VVB o producir un reporte legalmente válido
ante Verra, procesar todo el Chaco o construir un sistema nacional de monitoreo en tiempo
real, construir el producto SaaS completo, evaluar la adicionalidad o la línea base de un
proyecto (p. ej., contra áreas de control emparejadas; queda como trabajo futuro),
trabajo de campo original para validación
_in situ_, y reservorios de carbono más allá de biomasa aérea/subterránea (madera muerta,
hojarasca y carbono del suelo quedan excluidos y documentados como limitación).
