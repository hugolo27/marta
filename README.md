# Estado de la selección de la U-Net en molab

Rama escrita por `notebooks/molab_selection.py` (rama `feat/phase1-segmentation`) mientras corre la tarea 4.2 de `phase1-segmentation`. No se mergea.

- `results.json`: copia de `data/study_area/unet_selection/results.json`, subida cada vez que `38_unet_selection.py score` guarda una semilla.
- `sessions.json`: una entrada por sesión de selección, con commit, GPU y versión de PyTorch. La primera fija las tres.
- `probe.json`: segundos por época de la sesión de prueba.

Cuando la selección termina, `results.json` se commitea en `feat/phase1-segmentation` y las corridas de MLflow se reconstruyen desde ese archivo.
