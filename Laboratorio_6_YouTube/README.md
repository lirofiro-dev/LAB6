# Laboratorio 6 — Análisis de redes sociales: YouTube

**CC3084 — Data Science · Universidad del Valle de Guatemala · Semestre II 2026**

Análisis de la estructura de participación de usuarios, la relación entre canales y temas, y el contenido de las conversaciones en una muestra de videos y comentarios de YouTube. El cuaderno cubre las 10 actividades de la consigna: carga e integración, calidad y limpieza, análisis exploratorio, red bipartita autor-video, proyecciones, topología y fragmentación, comunidades, centralidad y participantes puente, contenido y sentimiento, e interpretación/limitaciones/conclusiones.

## Contenido del repositorio

```
Laboratorio_6_YouTube/
├── Laboratorio_6.ipynb          # Cuaderno principal (ejecutar de arriba hacia abajo)
├── requirements.txt              # Dependencias de Python
├── run.py                        # Script auxiliar que genera el informe de AVANCE (secciones 1-4) en PDF con reportlab
├── data/
│   ├── youtube_videos.csv        # 293 videos, 20 variables
│   └── youtube_comments.csv      # 406 comentarios, 17 variables
├── docs/
│   └── consigna_original.pdf     # Enunciado del laboratorio
└── resultados/
    ├── tablas/                   # ~43 CSV generados por el cuaderno (calidad, EDA, redes, comunidades, centralidad, sentimiento)
    ├── figuras/                  # 9 figuras PNG generadas por el cuaderno
    ├── informe/                  # Informe de avance (secciones 1-4) entregado previamente
    └── manifest.json             # Metadatos del informe de avance (secciones 1-4)
```

> **Nota:** todo lo que hay dentro de `resultados/` se **regenera automáticamente** al ejecutar el cuaderno completo; no es necesario editarlo a mano.

## Requisitos

- Python 3.10 – 3.12
- Conda (o cualquier gestor de entornos virtuales)

## Instalación del entorno (Conda)

Desde esta carpeta (`Laboratorio_6_YouTube/`):

```bash
# 1. Crear el entorno
conda create -n lab6-youtube python=3.11 -y

# 2. Activar el entorno
conda activate lab6-youtube

# 3. Instalar las dependencias del proyecto
pip install -r requirements.txt

# 4. Registrar el entorno como kernel de Jupyter
python -m ipykernel install --user --name lab6-youtube --display-name "Python (lab6-youtube)"
```

### Dependencias principales (`requirements.txt`)

| Paquete | Uso en el proyecto |
|---|---|
| `pandas`, `numpy` | Carga, limpieza e integración de los datos |
| `matplotlib`, `seaborn` | Visualizaciones y figuras del EDA |
| `scipy` | Estadísticos (correlaciones, distribuciones) |
| `networkx` | Construcción de la red bipartita, proyecciones, topología, centralidad |
| `python-louvain` (`import community`) | Detección de comunidades (algoritmo Louvain) |
| `reportlab` | Generación del PDF del informe de avance (`run.py`) |
| `jupyter`, `ipykernel`, `nbconvert` | Ejecutar el cuaderno y exportarlo (HTML/PDF) |

## Cómo ejecutar el análisis

### Opción A — Notebook completo (recomendado, cubre las 10 secciones)

```bash
conda activate lab6-youtube
jupyter notebook Laboratorio_6.ipynb
```

Correr todas las celdas en orden (`Kernel → Restart & Run All`). El cuaderno:

1. Carga `data/youtube_videos.csv` y `data/youtube_comments.csv`.
2. Limpia, normaliza e integra ambos conjuntos.
3. Genera el análisis exploratorio, la red bipartita autor-video, sus proyecciones, la detección de comunidades, las métricas de centralidad y el análisis de contenido/sentimiento.
4. Exporta automáticamente todas las tablas a `resultados/tablas/` y todas las figuras a `resultados/figuras/`.

También puede ejecutarse sin abrir la interfaz, desde la terminal:

```bash
jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=900 Laboratorio_6.ipynb
```

### Opción B — Exportar el notebook ya ejecutado a PDF/HTML

```bash
# HTML (con outputs embebidos)
jupyter nbconvert --to html Laboratorio_6.ipynb --output Informe_Final_Laboratorio_6_YouTube

# PDF vía LaTeX (requiere una instalación de TeX Live completa, incluyendo el paquete "soul")
jupyter nbconvert --to pdf Laboratorio_6.ipynb --output Informe_Final_Laboratorio_6_YouTube

# Alternativa si falta LaTeX: HTML -> PDF con wkhtmltopdf
wkhtmltopdf --enable-local-file-access --load-error-handling ignore \
  --load-media-error-handling ignore \
  Informe_Final_Laboratorio_6_YouTube.html Informe_Final_Laboratorio_6_YouTube.pdf
```

### Opción C — Solo el avance (secciones 1 a 4, script independiente)

```bash
conda activate lab6-youtube
python run.py
```

Genera `resultados/informe/Informe_Avance_Laboratorio_6_YouTube.pdf` (secciones 1-4 únicamente). **No** cubre las secciones 5-10; para el análisis completo usar el notebook.

## Notas metodológicas importantes

- **`reply_count` nunca se interpreta como una arista entre usuarios.** Indica cuántas respuestas recibió un comentario, pero no identifica a sus autores. Todas las redes construidas en este proyecto usan exclusivamente la co-participación autor–video (un autor comentó en un video), nunca relaciones de respuesta directa.
- **Cobertura parcial de comentarios.** De los 293 videos, solo 19 (de 8 canales) tienen comentarios recolectados. Todos los resultados de redes, comunidades y centralidad son válidos únicamente para esa submuestra.
- **Sentimiento por léxico en español.** El análisis de sentimiento (sección 9) usa un léxico propio de polaridad (positivo/negativo) aplicado sobre `texto_limpio`, elegido por ser reproducible sin conexión a internet y auditable comentario por comentario (a diferencia de librerías orientadas al inglés como VADER o modelos transformer que requieren descargas pesadas). Ver la justificación completa en la sección 9.1 del notebook.
- Los resultados descriptivos y de asociación son válidos **solo dentro de la muestra recolectada**; no deben generalizarse a todos los usuarios de YouTube ni a la población de Guatemala (ver sección 10.3 del notebook).

## Entregables de este laboratorio

Según la consigna, además de este repositorio se debe entregar por separado:

- Informe en PDF (`Informe_Final_Laboratorio_6_YouTube.pdf`).
- Enlace al espacio colaborativo del grupo.
- Enlace a este repositorio.
