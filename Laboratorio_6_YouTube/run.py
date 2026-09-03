#!/usr/bin/env python3
"""Genera todos los entregables del avance del Laboratorio 6 (secciones 1 a 4)."""

from __future__ import annotations

import ast
import html
import json
import math
import re
import textwrap
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "resultados"
TABLES_DIR = RESULTS_DIR / "tablas"
FIGURES_DIR = RESULTS_DIR / "figuras"
REPORT_DIR = RESULTS_DIR / "informe"

VIDEOS_CSV = DATA_DIR / "youtube_videos.csv"
COMMENTS_CSV = DATA_DIR / "youtube_comments.csv"
REPORT_PDF = REPORT_DIR / "Informe_Avance_Laboratorio_6_YouTube.pdf"
REPORT_MD = REPORT_DIR / "Informe_Avance_Editable.md"

STUDENT_NAME = "Daniel Adolfo Sarmiento Peralta"
COURSE = "CC3084 - Data Science"
LAB_TITLE = "Laboratorio 6 - Analisis de redes sociales: YouTube"


SPANISH_STOPWORDS = {
    "a", "aca", "ahi", "al", "algo", "algun", "alguna", "algunas", "alguno", "algunos",
    "alla", "alli", "ante", "antes", "aquel", "aquella", "aquellas", "aquello", "aquellos",
    "aqui", "asi", "aun", "aunque", "bajo", "bien", "cada", "casi", "como", "con", "contra",
    "cual", "cuando", "de", "del", "desde", "donde", "dos", "durante", "e", "el", "ella",
    "ellas", "ello", "ellos", "en", "entre", "era", "eramos", "eran", "eras", "eres", "es",
    "esa", "esas", "ese", "eso", "esos", "esta", "estaba", "estaban", "estado", "estamos",
    "estan", "estar", "estas", "este", "esto", "estos", "fue", "fuera", "fueron", "ha", "hace",
    "hacia", "han", "hasta", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me",
    "mi", "mis", "mismo", "mucho", "muy", "nada", "ni", "no", "nos", "nosotros", "nuestra",
    "nuestro", "o", "otra", "otras", "otro", "otros", "para", "pero", "poco", "por", "porque",
    "que", "quien", "se", "sea", "ser", "si", "sin", "sobre", "son", "su", "sus", "tambien",
    "te", "tener", "tiene", "tienen", "todo", "todos", "tu", "tus", "un", "una", "uno", "unos",
    "usted", "ustedes", "ya", "yo", "video", "videos", "youtube", "canal", "suscribete", "gracias",
    "mas", "más", "solo", "sólo",
}

POSITIVE_WORDS = {
    "alegre", "alegria", "amable", "amor", "apoyo", "apoyar", "bien", "bonita", "bonito", "buena",
    "bueno", "celebro", "correcto", "excelente", "exito", "felicidades", "feliz", "genial", "gusta",
    "hermosa", "hermoso", "increible", "justicia", "lindo", "logro", "maravilla", "maravilloso",
    "mejor", "orgullo", "positivo", "preciosa", "saludos", "seguro", "suerte", "verdad", "viva",
}

NEGATIVE_WORDS = {
    "abuso", "asalto", "asesino", "carcel", "corrupcion", "corrupto", "crimen", "delincuente", "dolor",
    "engaño", "estafa", "fracaso", "ilegal", "inseguridad", "lamentable", "ladron", "mal", "malo",
    "mafia", "mafioso", "mentira", "miedo", "miserable", "muerto", "odio", "peor", "problema", "robo",
    "triste", "vergüenza", "violencia", "vulgar",
}


def ensure_directories() -> None:
    for path in (TABLES_DIR, FIGURES_DIR, REPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def save_csv(frame: pd.DataFrame, filename: str) -> None:
    frame.to_csv(TABLES_DIR / filename, index=False, encoding="utf-8-sig")


def normalize_identifier(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    cleaned = unicodedata.normalize("NFKC", str(value)).strip()
    return cleaned if cleaned else pd.NA


def normalize_display_name(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    cleaned = unicodedata.normalize("NFKC", html.unescape(str(value)))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else pd.NA


def parse_count(value: object) -> tuple[int, bool]:
    """Convierte conteos como '2,390 vistas', '1.2 K' o blancos a enteros."""
    if pd.isna(value):
        return 0, True
    raw = unicodedata.normalize("NFKC", str(value)).strip().lower()
    if raw in {"", "-", "--", "nan", "none"}:
        return 0, True
    raw = raw.replace("vistas", "").replace("vista", "").replace("likes", "").strip()
    match = re.search(r"([-+]?\d+(?:[.,]\d+)?)\s*([kmb]|mil|millones?)?", raw)
    if not match:
        return 0, False
    number_text, suffix = match.groups()
    suffix = suffix or ""
    if suffix:
        number_text = number_text.replace(",", ".")
        multiplier = {"k": 1_000, "mil": 1_000, "m": 1_000_000, "millon": 1_000_000,
                      "millones": 1_000_000, "b": 1_000_000_000}.get(suffix, 1)
        return int(round(float(number_text) * multiplier)), True
    digits = re.sub(r"[^0-9+-]", "", number_text)
    try:
        return int(digits), True
    except ValueError:
        return 0, False


def extract_list(value: object) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (ValueError, SyntaxError):
        pass
    return [part.strip() for part in re.split(r"[|,;]", text) if part.strip()]


def extract_hashtags(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [tag.casefold() for tag in re.findall(r"(?<!\w)#([A-Za-z0-9_ÁÉÍÓÚÜÑáéíóúüñ]+)", str(value))]


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", html.unescape(str(value))).casefold()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"#([\wÁÉÍÓÚÜÑáéíóúüñ]+)", r" \1 ", text)
    text = re.sub(r"(?:^|\s)[/@][\w.%+-]+", " ", text)
    text = "".join(ch if unicodedata.category(ch)[0] in {"L", "Z"} else " " for ch in text)
    tokens = re.findall(r"[a-záéíóúüñ]+", text)
    tokens = [token for token in tokens if len(token) >= 3 and token not in SPANISH_STOPWORDS]
    return " ".join(tokens)


def sentiment_score(cleaned_text: str) -> tuple[float, str, int, int]:
    tokens = cleaned_text.split()
    positives = sum(token in POSITIVE_WORDS for token in tokens)
    negatives = sum(token in NEGATIVE_WORDS for token in tokens)
    score = (positives - negatives) / max(1, positives + negatives)
    label = "positivo" if score > 0 else "negativo" if score < 0 else "neutral"
    return score, label, positives, negatives


def safe_mode(series: pd.Series) -> str:
    nonempty = series.dropna().astype(str)
    return nonempty.mode().iloc[0] if not nonempty.empty else ""


def iqr_outliers(series: pd.Series) -> int:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return 0
    q1, q3 = numeric.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return int((numeric > q3).sum() + (numeric < q1).sum())
    return int(((numeric < q1 - 1.5 * iqr) | (numeric > q3 + 1.5 * iqr)).sum())


def make_quality_tables(videos: pd.DataFrame, comments: pd.DataFrame) -> dict[str, pd.DataFrame]:
    original_columns = {
        "youtube_videos": [
            "video_id", "title", "channel_name", "channel_id", "source_query", "source_group",
            "dataset_sources", "channel_handle", "published_time", "view_count_text",
            "description_snippet", "video_url", "query_hits", "keywords", "description", "view_count",
            "publish_date", "upload_date", "category", "owner_handle",
        ],
        "youtube_comments": [
            "video_id", "comment_id", "video_title", "channel_name", "channel_id", "author_name",
            "author_channel_id", "text", "source_query", "source_group", "dataset_sources",
            "author_handle", "published_text", "like_count_text", "reply_count", "is_pinned",
            "viewer_rating",
        ],
    }
    rows = []
    for name, frame, pk in (
        ("youtube_videos", videos, "video_id"),
        ("youtube_comments", comments, "comment_id"),
    ):
        frame = frame[original_columns[name]]
        constants = []
        for col in frame.columns:
            series = frame[col]
            try:
                unique_count = series.nunique(dropna=False)
            except TypeError:
                unique_count = series.map(lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
                                          if isinstance(value, (list, dict)) else str(value)).nunique(dropna=False)
            if unique_count <= 1:
                constants.append(col)
        rows.append({
            "dataset": name,
            "filas": len(frame),
            "columnas": frame.shape[1],
            "llave_primaria": pk,
            "duplicados_llave": int(frame[pk].duplicated().sum()),
            "celdas_faltantes": int(frame.isna().sum().sum()),
            "variables_constantes": ", ".join(constants) if constants else "Ninguna",
        })
    overview = pd.DataFrame(rows)

    missing_rows = []
    for name, frame in (("youtube_videos", videos), ("youtube_comments", comments)):
        frame = frame[original_columns[name]]
        for column in frame.columns:
            count = int(frame[column].isna().sum())
            blank = int(frame[column].astype("string").str.strip().eq("").fillna(False).sum())
            if count or blank:
                missing_rows.append({
                    "dataset": name,
                    "variable": column,
                    "faltantes_na": count,
                    "blancos_texto": blank,
                    "porcentaje_afectado": round(100 * (count + blank) / len(frame), 2),
                })
    missing = pd.DataFrame(missing_rows).sort_values(
        ["dataset", "porcentaje_afectado"], ascending=[True, False]
    )

    dtypes = pd.concat([
        pd.DataFrame({"dataset": "youtube_videos", "variable": original_columns["youtube_videos"],
                      "tipo_observado": videos[original_columns["youtube_videos"]].dtypes.astype(str).values}),
        pd.DataFrame({"dataset": "youtube_comments", "variable": original_columns["youtube_comments"],
                      "tipo_observado": comments[original_columns["youtube_comments"]].dtypes.astype(str).values}),
    ], ignore_index=True)

    outliers = pd.DataFrame([
        {"dataset": "youtube_videos", "variable": "view_count", "atipicos_iqr": iqr_outliers(videos["view_count"])},
        {"dataset": "youtube_comments", "variable": "reply_count", "atipicos_iqr": iqr_outliers(comments["reply_count"])},
        {"dataset": "youtube_comments", "variable": "like_count", "atipicos_iqr": iqr_outliers(comments["like_count"])},
    ])
    return {"resumen": overview, "faltantes": missing, "tipos": dtypes, "atipicos": outliers}


class UnionFind:
    def __init__(self, items: list[str]):
        self.parent = {item: item for item in items}
        self.size = {item: 1 for item in items}

    def find(self, item: str) -> str:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            nxt = self.parent[item]
            self.parent[item] = root
            item = nxt
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]


def build_network(videos: pd.DataFrame, comments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    edge_base = (
        comments.groupby(["author_channel_id", "video_id"], as_index=False)
        .agg(
            peso_comentarios=("comment_id", "size"),
            me_gusta_recibidos=("like_count", "sum"),
            respuestas_recibidas=("reply_count", "sum"),
        )
    )
    edge_base["source"] = "autor::" + edge_base["author_channel_id"].astype(str)
    edge_base["target"] = "video::" + edge_base["video_id"].astype(str)
    edges = edge_base[[
        "source", "target", "author_channel_id", "video_id", "peso_comentarios",
        "me_gusta_recibidos", "respuestas_recibidas",
    ]].copy()

    author_nodes = (
        comments.groupby("author_channel_id", as_index=False)
        .agg(
            etiqueta=("author_name", safe_mode),
            handle=("author_handle", safe_mode),
            comentarios=("comment_id", "size"),
            videos_unicos=("video_id", "nunique"),
            canales_unicos=("channel_id", "nunique"),
            sentimiento_medio=("sentimiento_score", "mean"),
        )
    )
    author_nodes["node_id"] = "autor::" + author_nodes["author_channel_id"].astype(str)
    author_nodes["tipo"] = "autor"
    author_nodes["channel_id"] = ""
    author_nodes["categoria"] = ""
    author_nodes["visualizaciones"] = np.nan
    author_nodes["autores_unicos"] = np.nan

    comment_counts = (
        comments.groupby("video_id", as_index=False)
        .agg(comentarios=("comment_id", "size"), autores_unicos=("author_channel_id", "nunique"),
             sentimiento_medio=("sentimiento_score", "mean"))
    )
    video_nodes = videos[videos["video_id"].isin(comments["video_id"].unique())].copy()
    video_nodes = video_nodes.merge(comment_counts, on="video_id", how="left", validate="one_to_one")
    video_nodes["node_id"] = "video::" + video_nodes["video_id"].astype(str)
    video_nodes["tipo"] = "video"
    video_nodes["etiqueta"] = video_nodes["title"]
    video_nodes["handle"] = video_nodes["channel_handle"]
    video_nodes["videos_unicos"] = np.nan
    video_nodes["canales_unicos"] = np.nan
    video_nodes["visualizaciones"] = video_nodes["view_count"]
    video_nodes["categoria"] = video_nodes["category"]
    video_nodes = video_nodes.rename(columns={"channel_name": "canal"})

    nodes = pd.concat([
        author_nodes[["node_id", "tipo", "etiqueta", "handle", "author_channel_id", "channel_id",
                      "comentarios", "videos_unicos", "canales_unicos", "visualizaciones", "autores_unicos",
                      "categoria", "sentimiento_medio"]],
        video_nodes[["node_id", "tipo", "etiqueta", "handle", "video_id", "channel_id", "canal",
                     "comentarios", "videos_unicos", "canales_unicos", "visualizaciones", "autores_unicos",
                     "categoria", "sentimiento_medio"]].rename(columns={"video_id": "author_channel_id"}),
    ], ignore_index=True, sort=False)
    nodes = nodes.rename(columns={"author_channel_id": "id_original"})

    all_node_ids = nodes["node_id"].tolist()
    uf = UnionFind(all_node_ids)
    for row in edges.itertuples(index=False):
        uf.union(row.source, row.target)
    roots = {node: uf.find(node) for node in all_node_ids}
    root_sizes = Counter(roots.values())
    ordered_roots = [root for root, _ in root_sizes.most_common()]
    component_map = {root: index + 1 for index, root in enumerate(ordered_roots)}
    nodes["componente"] = nodes["node_id"].map(lambda node: component_map[roots[node]])
    node_component = nodes.set_index("node_id")["componente"].to_dict()
    edges["componente"] = edges["source"].map(node_component)

    n_authors = int((nodes["tipo"] == "autor").sum())
    n_videos = int((nodes["tipo"] == "video").sum())
    n_edges = len(edges)
    degrees = Counter()
    for row in edges.itertuples(index=False):
        degrees[row.source] += 1
        degrees[row.target] += 1
    component_sizes = nodes.groupby("componente").size().sort_values(ascending=False)
    metrics = {
        "autores": n_authors,
        "videos": n_videos,
        "nodos": len(nodes),
        "aristas": n_edges,
        "peso_total": int(edges["peso_comentarios"].sum()),
        "densidad_bipartita": n_edges / (n_authors * n_videos) if n_authors and n_videos else 0,
        "grado_medio": 2 * n_edges / len(nodes) if len(nodes) else 0,
        "componentes": int(len(component_sizes)),
        "componente_mayor": int(component_sizes.iloc[0]) if len(component_sizes) else 0,
        "autores_recurrentes": int((author_nodes["videos_unicos"] > 1).sum()),
        "autores_multicanal": int((author_nodes["canales_unicos"] > 1).sum()),
    }
    return nodes, edges, metrics


def force_layout(nodes: list[str], edges: pd.DataFrame, seed: int = 3066) -> dict[str, np.ndarray]:
    """Disposicion de fuerzas determinista sin dependencias de grafos externas."""
    index = {node: i for i, node in enumerate(nodes)}
    rng = np.random.default_rng(seed)
    pos = rng.normal(0, 0.25, size=(len(nodes), 2))
    if not len(nodes):
        return {}
    edge_pairs = np.array([(index[s], index[t]) for s, t in edges[["source", "target"]].itertuples(index=False)], dtype=int)
    n = len(nodes)
    k = 1.1 / math.sqrt(max(n, 1))
    temperature = 0.16
    for _ in range(90):
        delta = pos[:, None, :] - pos[None, :, :]
        dist2 = np.sum(delta * delta, axis=2) + np.eye(n)
        inv_dist = 1.0 / np.sqrt(dist2)
        repulsion = (delta * (k * k / dist2)[:, :, None]).sum(axis=1)
        attraction = np.zeros_like(pos)
        for i, j in edge_pairs:
            vector = pos[i] - pos[j]
            distance = max(float(np.linalg.norm(vector)), 1e-4)
            force = vector * (distance / k)
            attraction[i] -= force
            attraction[j] += force
        displacement = repulsion + attraction - 0.08 * pos
        lengths = np.linalg.norm(displacement, axis=1)
        displacement = displacement / np.maximum(lengths[:, None], 1e-9) * np.minimum(lengths, temperature)[:, None]
        pos += displacement
        temperature *= 0.965
    pos -= pos.mean(axis=0)
    scale = np.abs(pos).max()
    if scale:
        pos /= scale
    return {node: pos[index[node]] for node in nodes}


def shorten(text: object, width: int = 36) -> str:
    return textwrap.shorten(str(text), width=width, placeholder="...")


def save_figure(filename: str) -> None:
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / filename, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close()


def create_figures(videos: pd.DataFrame, comments: pd.DataFrame, nodes: pd.DataFrame,
                   edges: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> None:
    sns.set_theme(style="whitegrid", font_scale=0.9)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titleweight": "bold"})

    top_channels = tables["canales_participacion"].head(12).sort_values("comentarios")
    plt.figure(figsize=(10, 6))
    sns.barplot(data=top_channels, x="comentarios", y="channel_name", color="#275DAD")
    plt.title("Canales con mayor participacion observada")
    plt.xlabel("Comentarios recolectados")
    plt.ylabel("Canal")
    save_figure("01_comentarios_por_canal.png")

    top_videos = tables["videos_participacion"].head(12).sort_values("comentarios")
    plt.figure(figsize=(11, 7))
    labels = [shorten(value, 48) for value in top_videos["title"]]
    plt.barh(labels, top_videos["comentarios"], color="#E76F51")
    plt.title("Videos con mayor participacion observada")
    plt.xlabel("Comentarios recolectados")
    plt.ylabel("Video")
    save_figure("02_comentarios_por_video.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
    sns.histplot(np.log10(videos["view_count"].clip(lower=1)), bins=24, color="#2A9D8F", ax=axes[0])
    axes[0].set_title("Distribucion de visualizaciones")
    axes[0].set_xlabel("log10(visualizaciones)")
    axes[0].set_ylabel("Videos")
    reply_like = comments[["like_count", "reply_count"]].copy()
    melted = reply_like.melt(var_name="metrica", value_name="conteo")
    sns.boxplot(data=melted, x="metrica", y="conteo", color="#F4A261", ax=axes[1], showfliers=False)
    axes[1].set_title("Me gusta y respuestas por comentario")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Conteo (sin atipicos visibles)")
    save_figure("03_distribuciones_conteos.png")

    concentration = tables["concentracion"]
    plt.figure(figsize=(9, 5.5))
    for kind, color in (("video", "#E76F51"), ("canal", "#275DAD")):
        subset = concentration[concentration["tipo"] == kind]
        plt.plot(subset["proporcion_unidades"], subset["proporcion_comentarios"], label=kind.capitalize(), color=color, lw=2.5)
    plt.plot([0, 1], [0, 1], "--", color="gray", label="Distribucion uniforme")
    plt.title("Concentracion acumulada de comentarios")
    plt.xlabel("Proporcion acumulada de unidades")
    plt.ylabel("Proporcion acumulada de comentarios")
    plt.legend()
    save_figure("04_concentracion_participacion.png")

    correlation = tables["popularidad_participacion"]
    plt.figure(figsize=(9, 6))
    sns.scatterplot(data=correlation, x="view_count", y="comentarios", hue="tiene_comentarios",
                    palette={False: "#B8B8B8", True: "#D1495B"}, alpha=0.75, s=45, legend=True)
    plt.xscale("symlog", linthresh=10)
    plt.yscale("symlog", linthresh=1)
    plt.title("Visualizaciones frente a comentarios observados")
    plt.xlabel("Visualizaciones (escala simetrica logaritmica)")
    plt.ylabel("Comentarios recolectados")
    save_figure("05_visualizaciones_vs_comentarios.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 7))
    words = tables["palabras"].head(15).sort_values("frecuencia")
    bigrams = tables["bigramas"].head(15).sort_values("frecuencia")
    axes[0].barh(words["termino"], words["frecuencia"], color="#457B9D")
    axes[0].set_title("Palabras frecuentes")
    axes[0].set_xlabel("Frecuencia")
    axes[1].barh(bigrams["termino"], bigrams["frecuencia"], color="#8D5A97")
    axes[1].set_title("Bigramas frecuentes")
    axes[1].set_xlabel("Frecuencia")
    save_figure("06_palabras_bigramas.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    categories = tables["categorias"].head(10).sort_values("videos")
    axes[0].barh(categories["category"], categories["videos"], color="#2A9D8F")
    axes[0].set_title("Videos por categoria")
    axes[0].set_xlabel("Videos")
    sentiment = tables["sentimiento_resumen"]
    axes[1].bar(sentiment["sentimiento"], sentiment["comentarios"], color=["#C44536", "#A8A8A8", "#3A7D44"])
    axes[1].set_title("Sentimiento preliminar por lexico")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Comentarios")
    save_figure("07_categorias_sentimiento.png")

    node_ids = nodes["node_id"].tolist()
    positions = force_layout(node_ids, edges)
    component_by_node = nodes.set_index("node_id")["componente"].to_dict()
    type_by_node = nodes.set_index("node_id")["tipo"].to_dict()
    label_by_node = nodes.set_index("node_id")["etiqueta"].to_dict()
    degree = Counter()
    for row in edges.itertuples(index=False):
        degree[row.source] += 1
        degree[row.target] += 1
    cmap = plt.get_cmap("tab20")
    plt.figure(figsize=(13, 10))
    for row in edges.itertuples(index=False):
        x = [positions[row.source][0], positions[row.target][0]]
        y = [positions[row.source][1], positions[row.target][1]]
        plt.plot(x, y, color="#9E9E9E", alpha=min(0.45, 0.08 + 0.05 * row.peso_comentarios), lw=0.45 + 0.2 * row.peso_comentarios, zorder=1)
    author_nodes = [node for node in node_ids if type_by_node[node] == "autor"]
    video_nodes = [node for node in node_ids if type_by_node[node] == "video"]
    plt.scatter([positions[node][0] for node in author_nodes], [positions[node][1] for node in author_nodes],
                c=[cmap((component_by_node[node] - 1) % 20) for node in author_nodes], s=14,
                marker="o", alpha=0.82, linewidths=0, zorder=2)
    plt.scatter([positions[node][0] for node in video_nodes], [positions[node][1] for node in video_nodes],
                c=[cmap((component_by_node[node] - 1) % 20) for node in video_nodes],
                s=[55 + 8 * degree[node] for node in video_nodes], marker="s", edgecolors="#1D1D1D",
                linewidths=0.5, alpha=0.95, zorder=3)
    label_candidates = sorted(video_nodes, key=lambda node: degree[node], reverse=True)[:12]
    label_candidates += sorted(author_nodes, key=lambda node: degree[node], reverse=True)[:5]
    for node in label_candidates:
        x, y = positions[node]
        plt.text(x + 0.012, y + 0.012, shorten(label_by_node[node], 28), fontsize=6.5, zorder=4)
    legend = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#275DAD", markersize=7, label="Autor"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#E76F51", markeredgecolor="#1D1D1D", markersize=8, label="Video"),
    ]
    plt.legend(handles=legend, loc="best")
    plt.title("Red bipartita completa autor-video\nColor = componente; grosor = comentarios del autor en el video")
    plt.axis("off")
    save_figure("08_red_bipartita_completa.png")


def frequency_table(items: list[str], column: str = "termino") -> pd.DataFrame:
    counts = Counter(item for item in items if item)
    return pd.DataFrame(counts.most_common(), columns=[column, "frecuencia"])


def cumulative_concentration(counts: pd.Series, kind: str) -> pd.DataFrame:
    ordered = counts.sort_values(ascending=False).reset_index(drop=True)
    if ordered.empty:
        return pd.DataFrame(columns=["tipo", "rango", "proporcion_unidades", "proporcion_comentarios"])
    return pd.DataFrame({
        "tipo": kind,
        "rango": np.arange(1, len(ordered) + 1),
        "proporcion_unidades": np.arange(1, len(ordered) + 1) / len(ordered),
        "proporcion_comentarios": ordered.cumsum() / ordered.sum(),
    })


def analyze() -> dict:
    ensure_directories()
    if not VIDEOS_CSV.exists() or not COMMENTS_CSV.exists():
        raise FileNotFoundError("No se encontraron los dos CSV dentro de la carpeta data/.")

    videos_raw = pd.read_csv(VIDEOS_CSV)
    comments_raw = pd.read_csv(COMMENTS_CSV)
    videos = videos_raw.copy()
    comments = comments_raw.copy()

    for column in ("video_id", "channel_id"):
        videos[column] = videos[column].map(normalize_identifier)
    for column in ("video_id", "comment_id", "channel_id", "author_channel_id"):
        comments[column] = comments[column].map(normalize_identifier)
    for column in ("title", "channel_name", "channel_handle", "owner_handle"):
        videos[column] = videos[column].map(normalize_display_name)
    for column in ("video_title", "channel_name", "author_name", "author_handle"):
        comments[column] = comments[column].map(normalize_display_name)

    parsed_views = videos["view_count_text"].map(parse_count)
    videos["view_count_text_numerico"] = parsed_views.map(lambda item: item[0])
    videos["view_count_text_valido"] = parsed_views.map(lambda item: item[1])
    videos["view_count"] = pd.to_numeric(videos["view_count"], errors="coerce").fillna(0).astype("int64")
    videos["publish_date"] = pd.to_datetime(videos["publish_date"], errors="coerce", utc=True)
    videos["upload_date"] = pd.to_datetime(videos["upload_date"], errors="coerce", utc=True)
    videos["query_hits_lista"] = videos["query_hits"].map(extract_list)
    videos["keywords_lista"] = videos["keywords"].map(extract_list)

    parsed_likes = comments["like_count_text"].map(parse_count)
    comments["like_count"] = parsed_likes.map(lambda item: item[0]).astype("int64")
    comments["like_count_valido"] = parsed_likes.map(lambda item: item[1])
    comments["reply_count"] = pd.to_numeric(comments["reply_count"], errors="coerce").fillna(0).astype("int64")
    comments["texto_original"] = comments["text"].astype("string").fillna("")
    comments["texto_limpio"] = comments["texto_original"].map(clean_text)
    sentiment = comments["texto_limpio"].map(sentiment_score)
    comments["sentimiento_score"] = sentiment.map(lambda item: item[0])
    comments["sentimiento"] = sentiment.map(lambda item: item[1])
    comments["palabras_positivas"] = sentiment.map(lambda item: item[2])
    comments["palabras_negativas"] = sentiment.map(lambda item: item[3])

    quality = make_quality_tables(videos, comments)
    for name, table in quality.items():
        save_csv(table, f"calidad_{name}.csv")

    video_reference = videos[[
        "video_id", "title", "channel_id", "channel_name", "channel_handle", "view_count",
        "publish_date", "category", "source_query", "source_group", "video_url",
    ]].copy()
    integrated = comments.merge(
        video_reference,
        on="video_id",
        how="left",
        validate="many_to_one",
        indicator=True,
        suffixes=("_comentario", "_video"),
    )
    matched = int((integrated["_merge"] == "both").sum())
    integrated["asociado_con_video"] = integrated["_merge"].eq("both")
    integrated = integrated.drop(columns=["_merge"])

    comments_per_video = comments.groupby("video_id", as_index=False).agg(
        comentarios=("comment_id", "size"),
        autores_unicos=("author_channel_id", "nunique"),
        me_gusta=("like_count", "sum"),
        respuestas=("reply_count", "sum"),
        sentimiento_medio=("sentimiento_score", "mean"),
    )
    videos_participation = (
        videos.merge(comments_per_video, on="video_id", how="left", validate="one_to_one")
        .fillna({"comentarios": 0, "autores_unicos": 0, "me_gusta": 0, "respuestas": 0})
    )
    for column in ("comentarios", "autores_unicos", "me_gusta", "respuestas"):
        videos_participation[column] = videos_participation[column].astype(int)
    videos_participation = videos_participation.sort_values(["comentarios", "view_count"], ascending=False)

    channels_video = videos.groupby(["channel_id", "channel_name"], as_index=False).agg(
        videos=("video_id", "nunique"), visualizaciones=("view_count", "sum")
    )
    channels_comment = comments.groupby(["channel_id", "channel_name"], as_index=False).agg(
        comentarios=("comment_id", "size"), autores_unicos=("author_channel_id", "nunique")
    )
    channels_participation = channels_video.merge(
        channels_comment[["channel_id", "comentarios", "autores_unicos"]], on="channel_id", how="left"
    ).fillna({"comentarios": 0, "autores_unicos": 0})
    channels_participation[["comentarios", "autores_unicos"]] = channels_participation[["comentarios", "autores_unicos"]].astype(int)
    channels_participation = channels_participation.sort_values(["comentarios", "visualizaciones"], ascending=False)

    authors = comments.groupby("author_channel_id", as_index=False).agg(
        author_name=("author_name", safe_mode), author_handle=("author_handle", safe_mode),
        comentarios=("comment_id", "size"), videos_unicos=("video_id", "nunique"),
        canales_unicos=("channel_id", "nunique"), me_gusta_recibidos=("like_count", "sum"),
        respuestas_recibidas=("reply_count", "sum"), sentimiento_medio=("sentimiento_score", "mean"),
    ).sort_values(["videos_unicos", "canales_unicos", "comentarios"], ascending=False)

    categories = videos.groupby("category", as_index=False).agg(
        videos=("video_id", "nunique"), visualizaciones=("view_count", "sum")
    )
    category_comments = integrated.groupby("category", as_index=False).agg(
        comentarios=("comment_id", "size"), autores_unicos=("author_channel_id", "nunique")
    )
    categories = categories.merge(category_comments, on="category", how="left").fillna(0)
    categories[["comentarios", "autores_unicos"]] = categories[["comentarios", "autores_unicos"]].astype(int)
    categories = categories.sort_values("videos", ascending=False)

    queries_videos = videos.groupby(["source_group", "source_query"], as_index=False).agg(
        videos=("video_id", "nunique"), visualizaciones=("view_count", "sum")
    ).sort_values("videos", ascending=False)
    queries_comments = comments.groupby(["source_group", "source_query"], as_index=False).agg(
        comentarios=("comment_id", "size"), autores_unicos=("author_channel_id", "nunique")
    ).sort_values("comentarios", ascending=False)

    comment_tokens = [token for text in comments["texto_limpio"] for token in text.split()]
    bigram_items = [f"{a} {b}" for text in comments["texto_limpio"] for a, b in zip(text.split(), text.split()[1:])]
    words = frequency_table(comment_tokens)
    bigrams = frequency_table(bigram_items)
    all_hashtags = []
    for series in (videos["title"], videos["description"], comments["texto_original"]):
        for value in series:
            all_hashtags.extend(extract_hashtags(value))
    hashtags = frequency_table(all_hashtags, "hashtag")

    video_counts = comments.groupby("video_id").size()
    channel_counts = comments.groupby("channel_id").size()
    concentration = pd.concat([
        cumulative_concentration(video_counts, "video"),
        cumulative_concentration(channel_counts, "canal"),
    ], ignore_index=True)

    popularity = videos_participation[[
        "video_id", "title", "channel_name", "view_count", "comentarios", "autores_unicos", "category"
    ]].copy()
    popularity["tiene_comentarios"] = popularity["comentarios"] > 0
    commented = popularity[popularity["tiene_comentarios"]]
    pearson_all = float(popularity["view_count"].corr(popularity["comentarios"], method="pearson"))
    spearman_all = float(popularity["view_count"].corr(popularity["comentarios"], method="spearman"))
    pearson_commented = float(commented["view_count"].corr(commented["comentarios"], method="pearson"))
    spearman_commented = float(commented["view_count"].corr(commented["comentarios"], method="spearman"))

    sentiment_summary = comments.groupby("sentimiento", as_index=False).agg(
        comentarios=("comment_id", "size"), porcentaje=("comment_id", lambda s: 100 * len(s) / len(comments))
    )
    sentiment_order = pd.Categorical(sentiment_summary["sentimiento"], ["negativo", "neutral", "positivo"], ordered=True)
    sentiment_summary = sentiment_summary.assign(_order=sentiment_order).sort_values("_order").drop(columns="_order")
    sentiment_by_video = comments.groupby(["video_id", "video_title"], as_index=False).agg(
        comentarios=("comment_id", "size"), sentimiento_medio=("sentimiento_score", "mean"),
        positivos=("sentimiento", lambda s: int((s == "positivo").sum())),
        negativos=("sentimiento", lambda s: int((s == "negativo").sum())),
    ).sort_values("comentarios", ascending=False)

    nodes, edges, network_metrics = build_network(videos, comments)
    save_csv(nodes, "red_bipartita_nodos.csv")
    save_csv(edges, "red_bipartita_aristas.csv")

    recurring = authors[authors["videos_unicos"] > 1].copy()
    video_author_sets = comments.groupby("video_id")["author_channel_id"].apply(set).to_dict()
    shared_pairs = []
    video_ids = sorted(video_author_sets)
    title_lookup = videos.set_index("video_id")["title"].to_dict()
    channel_lookup = videos.set_index("video_id")["channel_name"].to_dict()
    for i, left in enumerate(video_ids):
        for right in video_ids[i + 1:]:
            shared = video_author_sets[left] & video_author_sets[right]
            if shared:
                shared_pairs.append({
                    "video_id_1": left, "titulo_1": title_lookup.get(left, ""), "canal_1": channel_lookup.get(left, ""),
                    "video_id_2": right, "titulo_2": title_lookup.get(right, ""), "canal_2": channel_lookup.get(right, ""),
                    "autores_compartidos": len(shared),
                })
    shared_audiences = pd.DataFrame(shared_pairs)
    if not shared_audiences.empty:
        shared_audiences = shared_audiences.sort_values("autores_compartidos", ascending=False)

    component_by_video = nodes[nodes["tipo"] == "video"].set_index("id_original")["componente"].to_dict()
    comments["componente_red"] = comments["video_id"].map(component_by_video)
    component_rows = []
    for component, subset in comments.groupby("componente_red"):
        tokens = [token for text in subset["texto_limpio"] for token in text.split()]
        top_terms = ", ".join(term for term, _ in Counter(tokens).most_common(6))
        component_rows.append({
            "componente": int(component),
            "comentarios": len(subset),
            "autores": subset["author_channel_id"].nunique(),
            "videos": subset["video_id"].nunique(),
            "canales": subset["channel_id"].nunique(),
            "sentimiento_medio": subset["sentimiento_score"].mean(),
            "terminos_frecuentes": top_terms,
        })
    components = pd.DataFrame(component_rows).sort_values("comentarios", ascending=False)

    cleaning_effect = pd.DataFrame([
        {"metrica": "Registros originales", "valor": len(comments)},
        {"metrica": "Registros eliminados", "valor": 0},
        {"metrica": "Textos modificados", "valor": int((comments["texto_original"].str.strip() != comments["texto_limpio"]).sum())},
        {"metrica": "Textos vacios antes", "valor": int(comments["texto_original"].str.strip().eq("").sum())},
        {"metrica": "Textos vacios despues", "valor": int(comments["texto_limpio"].str.strip().eq("").sum())},
        {"metrica": "Textos duplicados antes", "valor": int(comments["texto_original"].duplicated().sum())},
        {"metrica": "Textos duplicados despues", "valor": int(comments["texto_limpio"].duplicated().sum())},
        {"metrica": "Conteos like no validos", "valor": int((~comments["like_count_valido"]).sum())},
    ])

    id_consistency = pd.DataFrame([
        {"comprobacion": "video_id duplicado en videos", "casos": int(videos["video_id"].duplicated().sum())},
        {"comprobacion": "comment_id duplicado", "casos": int(comments["comment_id"].duplicated().sum())},
        {"comprobacion": "channel_id con varios nombres en videos", "casos": int((videos.groupby("channel_id")["channel_name"].nunique() > 1).sum())},
        {"comprobacion": "author_channel_id con varios nombres", "casos": int((comments.groupby("author_channel_id")["author_name"].nunique() > 1).sum())},
        {"comprobacion": "upload_date distinto de publish_date", "casos": int((videos["upload_date"] != videos["publish_date"]).sum())},
        {"comprobacion": "owner_handle distinto de channel_handle", "casos": int((videos["owner_handle"] != videos["channel_handle"]).sum())},
    ])

    summary = pd.DataFrame([
        {"metrica": "Videos", "valor": len(videos)},
        {"metrica": "Canales de videos", "valor": videos["channel_id"].nunique()},
        {"metrica": "Comentarios", "valor": len(comments)},
        {"metrica": "Autores de comentarios", "valor": comments["author_channel_id"].nunique()},
        {"metrica": "Videos con comentarios recolectados", "valor": comments["video_id"].nunique()},
        {"metrica": "Canales con comentarios recolectados", "valor": comments["channel_id"].nunique()},
        {"metrica": "Comentarios asociados a video", "valor": matched},
        {"metrica": "Me gusta acumulados en comentarios", "valor": int(comments["like_count"].sum())},
        {"metrica": "Respuestas acumuladas", "valor": int(comments["reply_count"].sum())},
    ])

    tables = {
        "resumen": summary,
        "limpieza": cleaning_effect,
        "consistencia": id_consistency,
        "videos_participacion": videos_participation,
        "canales_participacion": channels_participation,
        "autores": authors,
        "categorias": categories,
        "consultas_videos": queries_videos,
        "consultas_comentarios": queries_comments,
        "hashtags": hashtags,
        "palabras": words,
        "bigramas": bigrams,
        "concentracion": concentration,
        "popularidad_participacion": popularity,
        "sentimiento_resumen": sentiment_summary,
        "sentimiento_video": sentiment_by_video,
        "audiencias_compartidas": shared_audiences,
        "autores_recurrentes": recurring,
        "componentes_preliminares": components,
    }

    export_map = {
        "resumen": "resumen_general.csv",
        "limpieza": "efecto_limpieza.csv",
        "consistencia": "consistencia_identificadores.csv",
        "videos_participacion": "eda_videos.csv",
        "canales_participacion": "eda_canales.csv",
        "autores": "eda_autores.csv",
        "categorias": "eda_categorias.csv",
        "consultas_videos": "eda_consultas_videos.csv",
        "consultas_comentarios": "eda_consultas_comentarios.csv",
        "hashtags": "eda_hashtags.csv",
        "palabras": "eda_palabras.csv",
        "bigramas": "eda_bigramas.csv",
        "concentracion": "eda_concentracion.csv",
        "popularidad_participacion": "eda_popularidad_participacion.csv",
        "sentimiento_resumen": "eda_sentimiento_preliminar.csv",
        "sentimiento_video": "eda_sentimiento_por_video.csv",
        "audiencias_compartidas": "eda_audiencias_compartidas.csv",
        "autores_recurrentes": "eda_autores_recurrentes.csv",
        "componentes_preliminares": "eda_componentes_preliminares.csv",
    }
    for key, filename in export_map.items():
        save_csv(tables[key], filename)

    videos_export = videos.copy()
    videos_export["query_hits_lista"] = videos_export["query_hits_lista"].map(json.dumps)
    videos_export["keywords_lista"] = videos_export["keywords_lista"].map(json.dumps)
    save_csv(videos_export, "youtube_videos_limpio.csv")
    save_csv(comments, "youtube_comments_limpio.csv")
    save_csv(integrated, "youtube_integrado.csv")

    create_figures(videos, comments, nodes, edges, tables)

    return {
        "videos": videos,
        "comments": comments,
        "integrated": integrated,
        "tables": tables,
        "quality": quality,
        "nodes": nodes,
        "edges": edges,
        "network": network_metrics,
        "matched": matched,
        "pearson_all": pearson_all,
        "spearman_all": spearman_all,
        "pearson_commented": pearson_commented,
        "spearman_commented": spearman_commented,
    }


def register_fonts() -> tuple[str, str]:
    candidates = [
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("LabSans", str(regular)))
            pdfmetrics.registerFont(TTFont("LabSansBold", str(bold)))
            return "LabSans", "LabSansBold"
    return "Helvetica", "Helvetica-Bold"


def format_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (np.floating, float)):
        return f"{float(value):,.3f}"
    if isinstance(value, (np.integer, int)):
        return f"{int(value):,}"
    return str(value)


def build_report(result: dict) -> None:
    regular_font, bold_font = register_fonts()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="LabTitle", parent=styles["Title"], fontName=bold_font, fontSize=23,
        leading=28, alignment=TA_CENTER, textColor=colors.HexColor("#17324D"), spaceAfter=18,
    ))
    styles.add(ParagraphStyle(
        name="LabSubtitle", parent=styles["Normal"], fontName=regular_font, fontSize=13,
        leading=18, alignment=TA_CENTER, textColor=colors.HexColor("#44617A"), spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="LabH1", parent=styles["Heading1"], fontName=bold_font, fontSize=16,
        leading=20, textColor=colors.HexColor("#17324D"), spaceBefore=12, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="LabH2", parent=styles["Heading2"], fontName=bold_font, fontSize=12,
        leading=15, textColor=colors.HexColor("#275DAD"), spaceBefore=9, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="LabBody", parent=styles["BodyText"], fontName=regular_font, fontSize=9.2,
        leading=13.2, alignment=TA_JUSTIFY, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="LabSmall", parent=styles["BodyText"], fontName=regular_font, fontSize=7.6,
        leading=10, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="LabCaption", parent=styles["BodyText"], fontName=regular_font, fontSize=7.8,
        leading=10, alignment=TA_CENTER, textColor=colors.HexColor("#555555"), spaceAfter=9,
    ))

    spanish_replacements = {
        "Analisis": "Análisis", "analisis": "análisis", "comprension": "comprensión",
        "integracion": "integración", "Relacion": "Relación", "relacion": "relación",
        "participacion": "participación", "observacion": "observación", "unicos": "únicos",
        "unico": "único", "numero": "número", "tambien": "también", "categoria": "categoría",
        "clasificacion": "clasificación", "busqueda": "búsqueda", "descripcion": "descripción",
        "diagnostico": "diagnóstico", "asimetrica": "asimétrica", "maximo": "máximo",
        "automaticamente": "automáticamente", "automatico": "automático", "auditoria": "auditoría",
        "visualizacion": "visualización", "graficas": "gráficas", "numerico": "numérico",
        "minusculas": "minúsculas", "puntuacion": "puntuación", "espanol": "español",
        "lematizacion": "lematización", "linguistico": "lingüístico", "ejecucion": "ejecución",
        "Concentracion": "Concentración", "concentracion": "concentración", "correlacion": "correlación",
        "asociacion": "asociación", "seleccion": "selección", "recoleccion": "recolección",
        "Conexion": "Conexión", "conexion": "conexión", "calculo": "cálculo", "terminos": "términos",
        "mayoritariamente": "mayoritariamente", "publico": "publicó", "publico": "publicó",
        "creo": "creó", "limito": "limitó", "esteticas": "estéticas", "metricas": "métricas",
        "distribucion": "distribución", "interpretacion": "interpretación", "construccion": "construcción",
        "Definicion": "Definición", "definicion": "definición", "investigacion": "investigación",
        "metodologicas": "metodológicas", "informe": "informe", "Pagina": "Página",
    }

    def polish_spanish(text: object) -> str:
        rendered = str(text)
        for source, target in spanish_replacements.items():
            rendered = re.sub(rf"\b{re.escape(source)}\b", target, rendered)
        return rendered

    def p(text: object, style: str = "LabBody") -> Paragraph:
        return Paragraph(escape(polish_spanish(text)), styles[style])

    def heading(text: str, level: int = 1) -> Paragraph:
        return p(text, "LabH1" if level == 1 else "LabH2")

    def bullet(text: str) -> Paragraph:
        return Paragraph(escape(polish_spanish(text)), styles["LabBody"], bulletText="-")

    def dataframe_table(frame: pd.DataFrame, columns: list[str] | None = None,
                        max_rows: int = 10, widths: list[float] | None = None) -> Table:
        display = frame.copy()
        if columns:
            display = display[columns]
        display = display.head(max_rows)
        data = [[Paragraph(escape(str(col)), styles["LabSmall"]) for col in display.columns]]
        for row in display.itertuples(index=False):
            data.append([Paragraph(escape(format_value(value)), styles["LabSmall"]) for value in row])
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), bold_font),
            ("FONTNAME", (0, 1), (-1, -1), regular_font),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#BBC7D1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F7")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return table

    def figure(filename: str, caption: str, width: float = 7.15 * inch, height: float | None = None) -> list:
        path = FIGURES_DIR / filename
        image = Image(str(path), width=width, height=height) if height else Image(str(path), width=width, height=width * 0.58)
        return [image, p(caption, "LabCaption")]

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular_font, 7.5)
        canvas.setFillColor(colors.HexColor("#687785"))
        canvas.drawString(0.65 * inch, 0.38 * inch, "Laboratorio 6 - Avance reproducible")
        canvas.drawRightString(7.85 * inch, 0.38 * inch, f"Página {doc.page}")
        canvas.restoreState()

    tables = result["tables"]
    quality = result["quality"]
    videos = result["videos"]
    comments = result["comments"]
    network = result["network"]

    top_video = tables["videos_participacion"].iloc[0]
    top_channel = tables["canales_participacion"].iloc[0]
    top_word = tables["palabras"].iloc[0]
    top_bigram = tables["bigramas"].iloc[0]
    top_hashtag = tables["hashtags"].iloc[0] if not tables["hashtags"].empty else None
    sentiment_lookup = tables["sentimiento_resumen"].set_index("sentimiento")["porcentaje"].to_dict()
    recurring = tables["autores_recurrentes"]
    shared = tables["audiencias_compartidas"]
    video_counts = comments.groupby("video_id").size().sort_values(ascending=False)
    channel_counts = comments.groupby("channel_id").size().sort_values(ascending=False)

    doc = SimpleDocTemplate(
        str(REPORT_PDF), pagesize=letter, rightMargin=0.55 * inch, leftMargin=0.55 * inch,
        topMargin=0.55 * inch, bottomMargin=0.6 * inch,
        title="Informe de avance - Laboratorio 6 YouTube",
        author=STUDENT_NAME,
    )
    story = []
    story += [Spacer(1, 0.75 * inch), p("Universidad del Valle de Guatemala", "LabSubtitle"),
              p("Facultad de Ingenieria - Departamento de Ciencias de la Computacion", "LabSubtitle"),
              Spacer(1, 0.35 * inch), p(LAB_TITLE, "LabTitle"),
              p("INFORME DE AVANCE: ACTIVIDADES 1 A 4", "LabSubtitle"), Spacer(1, 0.45 * inch),
              p(f"Autor: {STUDENT_NAME}", "LabSubtitle"), p(COURSE, "LabSubtitle"),
              p("Semestre II - 2026", "LabSubtitle"), Spacer(1, 0.65 * inch),
              p("Este informe fue generado de forma reproducible a partir de los dos archivos CSV proporcionados. Todas las tablas y figuras se reconstruyen ejecutando python run.py.", "LabCaption"),
              PageBreak()]

    story += [heading("Resumen ejecutivo")]
    story += [p(
        f"Se analizaron {len(videos):,} videos pertenecientes a {videos['channel_id'].nunique():,} canales y "
        f"{len(comments):,} comentarios publicados por {comments['author_channel_id'].nunique():,} autores unicos. "
        f"Los {result['matched']:,} comentarios ({100 * result['matched'] / len(comments):.1f} %) pudieron asociarse con un registro de video mediante video_id. "
        f"La participacion observada esta fuertemente concentrada: el video con mas comentarios reune "
        f"{100 * video_counts.iloc[0] / len(comments):.1f} % y los cinco primeros reunen "
        f"{100 * video_counts.head(5).sum() / len(comments):.1f} %."
    )]
    story += [p(
        f"La red bipartita contiene {network['autores']:,} autores, {network['videos']:,} videos y "
        f"{network['aristas']:,} pares autor-video distintos. Cada arista representa exclusivamente que un autor "
        f"publico uno o mas comentarios principales en un video; no demuestra amistad, respuesta directa, acuerdo ni aprobacion."
    )]
    story += [dataframe_table(tables["resumen"], max_rows=20, widths=[4.7 * inch, 1.4 * inch]), PageBreak()]

    story += [heading("1. Carga, comprension e integracion de los datos")]
    story += [heading("1.1 y 1.2. Unidad de observacion, llaves y variables", 2)]
    dataset_description = pd.DataFrame([
        {"archivo": "youtube_videos.csv", "unidad": "Un video", "llave primaria": "video_id",
         "variables relevantes": "channel_id, title, view_count, publish_date, category, source_query, keywords, description"},
        {"archivo": "youtube_comments.csv", "unidad": "Un comentario principal", "llave primaria": "comment_id",
         "variables relevantes": "video_id, author_channel_id, text, like_count_text, reply_count, source_query"},
    ])
    story += [dataframe_table(dataset_description, max_rows=5, widths=[1.25 * inch, 1.05 * inch, 1.05 * inch, 3.7 * inch])]
    story += [p("Los nombres y handles se conservan como atributos descriptivos. No reemplazan los identificadores estables. En particular, channel_name identifica visualmente al propietario del video, mientras author_name identifica visualmente al autor del comentario.")]
    story += [heading("1.3. Relacion entre entidades", 2)]
    for text in (
        "Canal-video: un channel_id puede publicar varios videos; cada video pertenece al channel_id registrado.",
        "Video-comentario: video_id actua como llave primaria en videos y llave foranea en comentarios.",
        "Autor-comentario: author_channel_id identifica la cuenta que publico el comentario; no es el channel_id del canal comentado.",
        "Categoria: category describe la categoria asignada al video y se hereda a los comentarios solo mediante la union con video_id.",
        "Consulta: source_query y source_group describen el procedimiento de muestreo, no una clasificacion tematica definitiva.",
    ):
        story.append(bullet(text))
    story += [heading("1.4. Integracion", 2), p(
        f"Se aplico una union muchos-a-uno desde comentarios hacia videos usando video_id y se valido que video_id fuera unico en la tabla de videos. "
        f"Resultado: {result['matched']:,} de {len(comments):,} comentarios asociados; quedaron {len(comments) - result['matched']:,} sin coincidencia."
    )]
    story += [PageBreak(), heading("2. Calidad, limpieza y preprocesamiento")]
    story += [heading("2.1. Diagnostico inicial", 2), dataframe_table(
        quality["resumen"], max_rows=5, widths=[1.2 * inch, 0.55 * inch, 0.65 * inch, 1.05 * inch, 0.8 * inch, 0.9 * inch, 1.9 * inch]
    )]
    story += [p(
        f"Las llaves primarias no presentan duplicados. viewer_rating esta vacia en los {len(comments)} comentarios e is_pinned es constante False. "
        f"Las visualizaciones son muy asimetricas: la mediana es {videos['view_count'].median():,.0f}, frente a un maximo de {videos['view_count'].max():,.0f}; "
        f"por eso los valores altos se tratan como observaciones validas potencialmente influyentes y no se eliminan automaticamente."
    )]
    story += [heading("Faltantes y blancos relevantes", 2), dataframe_table(
        quality["faltantes"], max_rows=12, widths=[1.3 * inch, 1.55 * inch, 0.85 * inch, 0.85 * inch, 1.05 * inch]
    )]
    story += [heading("Consistencia de identificadores", 2), dataframe_table(
        tables["consistencia"], max_rows=10, widths=[5.3 * inch, 0.9 * inch]
    )]
    story += [heading("2.2. Variables delicadas", 2)]
    for text in (
        "viewer_rating se excluye del analisis porque no tiene valores; is_pinned se conserva para auditoria pero no discrimina registros.",
        "published_time y published_text son tiempos relativos al momento de recoleccion; no se convierten en fechas exactas.",
        "view_count_text y like_count_text requieren limpieza. Para visualizaciones se usa view_count, ya numerica; los blancos de like_count_text se interpretan como cero visible y se documentan.",
        "source_query y source_group describen cobertura de busqueda. No se interpretan automaticamente como tema real.",
        "reply_count indica cantidad de respuestas, pero no contiene identidad de quienes respondieron; nunca se usa para crear aristas entre usuarios.",
        "Los conteos son fotografias del momento de recoleccion y no son directamente comparables sin considerar antiguedad y cobertura.",
    ):
        story.append(bullet(text))
    story += [heading("2.3 y 2.4. Normalizacion y conteos", 2), p(
        "Los identificadores se normalizaron con Unicode NFKC y recorte de espacios, manteniendo video_id, comment_id, channel_id y author_channel_id. "
        "Los nombres se limpiaron solo para presentacion. El conversor numerico reconoce separadores y sufijos K, M, B, mil y millones; conserva una bandera de validez. "
        "En like_count_text, los espacios en blanco se transformaron a cero porque representan ausencia de un conteo visible, no un valor de popularidad desconocido."
    )]
    story += [heading("2.5 a 2.7. Limpieza de texto", 2), p(
        "texto_original conserva el comentario exacto para auditoria. texto_limpio usa minusculas, elimina URL y menciones, separa el contenido de hashtags, "
        "elimina puntuacion, numeros, emojis y simbolos, y remueve stopwords en espanol. Se conservaron tildes y la letra ñ. No se aplico lematizacion: "
        "un modelo linguistico externo introduciria una descarga y una version adicional; para este avance se priorizo reproducibilidad local y se documenta la decision."
    ), dataframe_table(tables["limpieza"], max_rows=12, widths=[4.8 * inch, 1.2 * inch]), PageBreak()]

    story += [heading("3. Analisis exploratorio")]
    story += [heading("3.1. Participacion, popularidad y contenido", 2)]
    story += figure("01_comentarios_por_canal.png", "Figura 1. Comentarios recolectados por canal. La cobertura de comentarios se concentra en ocho canales.")
    story += figure("02_comentarios_por_video.png", "Figura 2. Videos con mayor numero de comentarios observados.")
    story += [p(
        f"El video con mayor participacion es '{shorten(top_video['title'], 90)}' del canal {top_video['channel_name']}, con "
        f"{int(top_video['comentarios'])} comentarios y {int(top_video['autores_unicos'])} autores unicos. El canal con mayor participacion es "
        f"{top_channel['channel_name']}, con {int(top_channel['comentarios'])} comentarios ({100 * top_channel['comentarios'] / len(comments):.1f} % del total)."
    )]
    story += figure("03_distribuciones_conteos.png", "Figura 3. Distribuciones de visualizaciones, me gusta y respuestas. La asimetria obliga a interpretar medias y correlaciones con cautela.")
    story += figure("06_palabras_bigramas.png", "Figura 4. Frecuencias de palabras y bigramas en texto_limpio; complementan, pero no sustituyen, el contexto cualitativo.")
    hashtag_text = f"El hashtag mas frecuente es #{top_hashtag['hashtag']} ({int(top_hashtag['frecuencia'])} apariciones)." if top_hashtag is not None else "No se detectaron hashtags."
    story += [p(
        f"La palabra mas frecuente es '{top_word['termino']}' ({int(top_word['frecuencia'])}) y el bigrama principal es "
        f"'{top_bigram['termino']}' ({int(top_bigram['frecuencia'])}). {hashtag_text} Las tablas completas se encuentran en resultados/tablas."
    )]
    story += figure("07_categorias_sentimiento.png", "Figura 5. Categorias de los videos y clasificacion preliminar de sentimiento.")
    story += [p(
        f"El analisis preliminar basado en lexico clasifica {sentiment_lookup.get('neutral', 0):.1f} % como neutral, "
        f"{sentiment_lookup.get('positivo', 0):.1f} % como positivo y {sentiment_lookup.get('negativo', 0):.1f} % como negativo. "
        "Es una aproximacion transparente y reproducible, pero no resuelve negacion, ironia, contexto ni variacion dialectal; no reemplaza el modelo final solicitado en la actividad 9."
    )]
    story += [PageBreak(), heading("3.2. Concentracion de la participacion", 2)]
    story += figure("04_concentracion_participacion.png", "Figura 6. Curvas acumuladas de concentracion. Una curva por encima de la diagonal indica que pocas unidades acumulan gran parte de los comentarios.")
    story += [p(
        f"El primer video concentra {100 * video_counts.iloc[0] / len(comments):.1f} % de los comentarios; los cinco primeros, "
        f"{100 * video_counts.head(5).sum() / len(comments):.1f} %; y los diez primeros, {100 * video_counts.head(10).sum() / len(comments):.1f} %. "
        f"Por canal, el primero concentra {100 * channel_counts.iloc[0] / len(comments):.1f} % y los cinco primeros, "
        f"{100 * channel_counts.head(5).sum() / len(comments):.1f} %. Esta concentracion describe la muestra y tambien refleja el procedimiento de recoleccion."
    )]
    story += [heading("3.3. Visualizaciones y comentarios", 2)]
    story += figure("05_visualizaciones_vs_comentarios.png", "Figura 7. Relacion entre visualizaciones publicas y comentarios presentes en el archivo entregado.")
    story += [p(
        f"Para los {len(videos)} videos, la correlacion de Pearson entre visualizaciones y comentarios observados es {result['pearson_all']:.3f}, y Spearman es {result['spearman_all']:.3f}. "
        f"Si se restringe a los {comments['video_id'].nunique()} videos con comentarios recolectados, Pearson es {result['pearson_commented']:.3f} y Spearman es {result['spearman_commented']:.3f}. "
        "Estas asociaciones no miden la tasa real de comentar: el archivo de comentarios cubre solo una seleccion de videos y posiblemente no contiene todos los comentarios existentes."
    )]
    story += [heading("3.5. Respuestas a las preguntas obligatorias", 2)]
    for text in (
        f"Videos y canales con mayor participacion: lidera '{shorten(top_video['title'], 75)}' y el canal {top_channel['channel_name']}. Los rankings completos se entregan en eda_videos.csv y eda_canales.csv.",
        f"Audiencias compartidas: {len(recurring)} autores comentaron en mas de un video y {network['autores_multicanal']} lo hicieron en mas de un canal. Se detectaron {len(shared)} pares de videos con al menos un autor compartido.",
        f"Posibles puentes: se consideran candidatos preliminares los autores con mayor cantidad de videos_unicos y canales_unicos. Esta es recurrencia observada, no centralidad de intermediacion; el calculo formal corresponde a actividades posteriores.",
        f"Temas y sentimiento: los terminos dominantes incluyen '{top_word['termino']}' y '{top_bigram['termino']}'. Los componentes conexos preliminares se caracterizan en eda_componentes_preliminares.csv; el sentimiento por lexico es mayoritariamente {max(sentiment_lookup, key=sentiment_lookup.get) if sentiment_lookup else 'no disponible'}.",
        f"Visibilidad y participacion: no coinciden necesariamente. La correlacion sobre videos comentados es Spearman={result['spearman_commented']:.3f}, y varios videos con muchas vistas carecen de comentarios en el archivo por cobertura, no necesariamente por ausencia de participacion real.",
        "Limitaciones de cobertura: seleccion por consultas y canales, solo comentarios principales recuperados, fechas relativas, conteos observados en un momento, falta de relaciones autor-respuesta y fuerte concentracion en pocos videos.",
    ):
        story.append(bullet(text))
    story += [heading("3.6. Preguntas adicionales", 2)]
    liked_pct = 100 * (comments["like_count"] > 0).mean()
    replied_pct = 100 * (comments["reply_count"] > 0).mean()
    source_video = videos["source_group"].value_counts().idxmax()
    source_comment = comments["source_group"].value_counts().idxmax()
    for text in (
        f"¿Cuantos comentarios recibieron reacciones visibles? {liked_pct:.1f} % tiene al menos un me gusta y {replied_pct:.1f} % tiene al menos una respuesta.",
        f"¿La mayoria de autores participa repetidamente? No: {len(recurring)} de {comments['author_channel_id'].nunique()} autores ({100 * len(recurring) / comments['author_channel_id'].nunique():.1f} %) comenta en mas de un video observado.",
        f"¿El origen de recoleccion dominante es el mismo para videos y comentarios? En videos domina '{source_video}', mientras en comentarios domina '{source_comment}'. Esto confirma que ambos archivos tienen coberturas distintas.",
    ):
        story.append(bullet(text))

    story += [PageBreak(), heading("4. Red bipartita autor-video")]
    story += [heading("4.1 y 4.2. Definicion y construccion", 2), p(
        "La red es no dirigida y bipartita. Un conjunto de nodos contiene author_channel_id y el otro video_id. Se creo una arista por cada par autor-video observado. "
        "El peso es la cantidad de comentarios principales que ese autor publico en ese video. reply_count no crea aristas porque no identifica a quienes respondieron."
    )]
    metrics_table = pd.DataFrame([
        {"metrica": "Autores", "valor": network["autores"]},
        {"metrica": "Videos", "valor": network["videos"]},
        {"metrica": "Nodos totales", "valor": network["nodos"]},
        {"metrica": "Aristas autor-video", "valor": network["aristas"]},
        {"metrica": "Peso total (comentarios)", "valor": network["peso_total"]},
        {"metrica": "Densidad bipartita", "valor": network["densidad_bipartita"]},
        {"metrica": "Componentes conexos preliminares", "valor": network["componentes"]},
        {"metrica": "Nodos en componente mayor", "valor": network["componente_mayor"]},
    ])
    story += [dataframe_table(metrics_table, max_rows=20, widths=[4.7 * inch, 1.5 * inch])]
    story += [heading("4.3. Tablas entregadas", 2), p(
        "red_bipartita_nodos.csv contiene node_id, tipo y atributos descriptivos. red_bipartita_aristas.csv contiene source, target, peso_comentarios, me_gusta y respuestas agregadas. "
        "Los prefijos autor:: y video:: evitan colisiones entre identificadores de distinto tipo."
    )]
    story += figure("08_red_bipartita_completa.png", "Figura 8. Red bipartita completa. No se eliminaron nodos ni aristas por razones esteticas; solo se limitaron las etiquetas para mantener legibilidad.", width=7.1 * inch, height=5.45 * inch)
    story += [heading("4.4 y 4.5. Lectura correcta de la red", 2), p(
        f"La red contiene {network['componentes']} componentes conexos observados. Los colores muestran componentes, no comunidades detectadas estadisticamente. "
        f"{network['autores_recurrentes']} autores conectan al menos dos videos y son candidatos a estudiar como participantes recurrentes. "
        "Una conexion solo afirma co-participacion de un autor en un video. No permite saber si leyo otros comentarios, respondio a otro usuario, estuvo de acuerdo, conoce al canal o mantiene una relacion social fuera de YouTube."
    )]

    story += [PageBreak(), heading("Conclusiones del avance")]
    for text in (
        f"La integracion es completa para el archivo entregado: {result['matched']} de {len(comments)} comentarios encuentran su video mediante video_id.",
        "Los identificadores son consistentes, pero las variables de tiempo relativo, los conteos textuales y las variables constantes requieren tratamiento explicito.",
        f"La participacion observada esta concentrada: cinco videos acumulan {100 * video_counts.head(5).sum() / len(comments):.1f} % de los comentarios.",
        "Las visualizaciones publicas y los comentarios recolectados describen dimensiones distintas y no deben interpretarse como equivalentes ni como causalidad.",
        f"La red bipartita documenta {network['aristas']} relaciones autor-video distintas y conserva todas las estructuras observadas.",
        "Los resultados describen exclusivamente la muestra recolectada. No se generalizan a todos los usuarios de YouTube ni a toda la poblacion de Guatemala.",
    ):
        story.append(bullet(text))
    story += [heading("Reproducibilidad", 2), p(
        "El proyecto incluye datos, codigo, dependencias, tablas y figuras. Desde la carpeta raiz, cree el entorno, instale requirements.txt y ejecute python run.py. "
        "La ejecucion sobrescribe los resultados con versiones reconstruidas a partir de los CSV. El README contiene instrucciones para Windows, macOS y Linux."
    )]

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)


def build_markdown_report(result: dict) -> None:
    tables = result["tables"]
    comments = result["comments"]
    videos = result["videos"]
    network = result["network"]
    top_video = tables["videos_participacion"].iloc[0]
    content = f"""# {LAB_TITLE}

## Informe de avance: actividades 1 a 4

**Autor:** {STUDENT_NAME}  
**Curso:** {COURSE}  
**Fecha de generacion:** {datetime.now().date().isoformat()}

## Resumen

- Videos: {len(videos)}
- Canales: {videos['channel_id'].nunique()}
- Comentarios: {len(comments)}
- Autores: {comments['author_channel_id'].nunique()}
- Comentarios asociados mediante `video_id`: {result['matched']} de {len(comments)}
- Red bipartita: {network['nodos']} nodos y {network['aristas']} aristas

## 1. Carga, comprension e integracion

`youtube_videos.csv` tiene como unidad un video y llave primaria `video_id`.  
`youtube_comments.csv` tiene como unidad un comentario principal y llave primaria `comment_id`; `video_id` es llave foranea.

La union muchos-a-uno asocio {result['matched']} comentarios. Los ID se mantienen como identificadores y los nombres/handles como etiquetas.

## 2. Calidad, limpieza y preprocesamiento

Se conservaron `texto_original` y `texto_limpio`. La limpieza usa Unicode NFKC, minusculas, separacion de hashtags, eliminacion de URL, menciones, puntuacion, numeros, emojis y stopwords. No se aplico lematizacion para evitar una dependencia linguistica externa no incluida en el entorno reproducible.

Las tablas completas estan en `resultados/tablas/`, incluyendo faltantes, tipos, atipicos IQR, consistencia de identificadores y efecto de limpieza.

## 3. Analisis exploratorio

El video con mayor participacion es **{top_video['title']}**, con {int(top_video['comentarios'])} comentarios. Las figuras cuantifican canales, videos, concentracion, relacion vistas-comentarios, palabras, bigramas, categorias y sentimiento preliminar.

![Comentarios por video](../figuras/02_comentarios_por_video.png)

![Concentracion](../figuras/04_concentracion_participacion.png)

## 4. Red bipartita autor-video

Cada arista conecta un `author_channel_id` con un `video_id` cuando el autor publico al menos un comentario principal. Su peso es el numero de comentarios del autor en ese video. No representa amistad, respuesta directa ni aprobacion.

![Red bipartita](../figuras/08_red_bipartita_completa.png)

## Limitaciones

- Cobertura parcial de comentarios y seleccion por consultas/canales.
- Fechas relativas en comentarios.
- Conteos observados en un momento de recoleccion.
- `reply_count` no identifica autores de respuestas.
- Participacion concentrada en pocos videos.
- Los resultados describen la muestra y no se generalizan a toda la poblacion de Guatemala o YouTube.
"""
    REPORT_MD.write_text(content, encoding="utf-8")


def main() -> None:
    result = analyze()
    build_report(result)
    build_markdown_report(result)
    manifest = {
        "estado": "completado",
        "alcance": "actividades 1 a 4",
        "fecha_generacion_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "archivos_entrada": [str(VIDEOS_CSV.relative_to(ROOT)), str(COMMENTS_CSV.relative_to(ROOT))],
        "informe_pdf": str(REPORT_PDF.relative_to(ROOT)),
        "informe_editable": str(REPORT_MD.relative_to(ROOT)),
        "tablas_generadas": len(list(TABLES_DIR.glob("*.csv"))),
        "figuras_generadas": len(list(FIGURES_DIR.glob("*.png"))),
    }
    (RESULTS_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Analisis completado.")
    print(f"Informe PDF: {REPORT_PDF}")
    print(f"Tablas: {TABLES_DIR}")
    print(f"Figuras: {FIGURES_DIR}")


if __name__ == "__main__":
    main()
