#set document(title: "[Título del TFM — completar]", author: "Hugo López")
#set page(paper: "a4", margin: (x: 2.5cm, y: 2.5cm), numbering: "1")
#set text(font: "New Computer Modern", size: 11pt, lang: "es")
#set heading(numbering: "1.1")
#set par(justify: true, leading: 0.65em)

// --- Portada ---
// Plantilla genérica de tesis de posgrado. El formato oficial de la FP-UNA sigue el
// "Manual de Postgrado" del Rectorado (ver thesis/README.md) -- todavía no incorporado
// acá porque no está disponible en el repo. Ajustar portada/estructura cuando llegue.
#align(center)[
  #v(3cm)
  #text(size: 14pt)[Facultad Politécnica — Universidad Nacional de Asunción]
  #v(0.3cm)
  #text(size: 12pt)[Maestría en Inteligencia Artificial y Análisis de Datos]
  #v(3cm)
  #text(size: 20pt, weight: "bold")[\[Título del TFM — completar\]]
  #v(0.5cm)
  #text(size: 13pt, style: "italic")[Trabajo Final de Maestría]
  #v(3cm)
  #text(size: 12pt)[Hugo López]
  #v(0.3cm)
  #text(size: 11pt)[Tutor: \[completar\]]
  #v(1cm)
  #text(size: 11pt)[\[Fecha de presentación\]]
]
#pagebreak()

#outline(title: "Índice")
#pagebreak()

#include "capitulos/01_introduccion.typ"
#include "capitulos/02_metodologia.typ"
#include "capitulos/03_resultados_fase1.typ"
#include "capitulos/04_proximos_pasos.typ"

#bibliography("referencias.bib")
