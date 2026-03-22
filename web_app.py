import os
import tempfile
from datetime import datetime, timezone
from html import escape

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from pbix_layout_tool import extract_pbit_model_insights
from pbix_layout_tool import (
    DEFAULT_DIM_PREFIXES,
    DEFAULT_FACT_PREFIXES,
    build_adjacency,
    classify_tables,
    compute_layout,
)

ALLOWED_EXTENSIONS = {"pbit"}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE


def _is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _extract_model_insights(uploaded_file) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        source_name = secure_filename(uploaded_file.filename or "model.pbit")
        source_path = os.path.join(tmpdir, source_name)
        uploaded_file.save(source_path)
        return extract_pbit_model_insights(source_path)


def _build_diagram_svg(relations: list[dict]) -> str:
    table_names = sorted({r["from"] for r in relations} | {r["to"] for r in relations})
    facts, dims, others = classify_tables(
        table_names, DEFAULT_FACT_PREFIXES, DEFAULT_DIM_PREFIXES
    )
    fact_to_dims, snowflake, orphan_dims = build_adjacency(relations, facts, dims)

    node_sizes = {name: (220, 90) for name in table_names}
    positions = compute_layout(
        facts,
        dims,
        others,
        fact_to_dims,
        snowflake,
        orphan_dims,
        radius=520,
        table_width=220,
        table_height=90,
        node_sizes=node_sizes,
    )

    if not positions:
        return "<p>Nenhum relacionamento para renderizar.</p>"

    pad = 80
    min_x = min(x for x, _ in positions.values())
    min_y = min(y for _, y in positions.values())
    max_x = max(x + node_sizes[n][0] for n, (x, _) in positions.items())
    max_y = max(y + node_sizes[n][1] for n, (_, y) in positions.items())
    width = int(max_x - min_x + pad * 2)
    height = int(max_y - min_y + pad * 2)

    def normalize_xy(name: str) -> tuple[float, float]:
        x, y = positions[name]
        return x - min_x + pad, y - min_y + pad

    relation_lines = []
    for rel in relations:
        src = rel["from"]
        dst = rel["to"]
        if src not in positions or dst not in positions:
            continue
        sx, sy = normalize_xy(src)
        dx, dy = normalize_xy(dst)
        sw, sh = node_sizes[src]
        dw, dh = node_sizes[dst]
        x1 = sx + sw
        y1 = sy + sh / 2
        x2 = dx
        y2 = dy + dh / 2
        mid_x = (x1 + x2) / 2
        relation_lines.append(
            f'<path class="relation-line" data-src="{escape(src)}" data-dst="{escape(dst)}" '
            f'd="M {x1:.1f} {y1:.1f} L {mid_x:.1f} {y1:.1f} L {mid_x:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}" '
            'stroke="#9aa6b2" stroke-width="2" fill="none" />'
        )

    nodes = []
    for name in table_names:
        if name not in positions:
            continue
        x, y = normalize_xy(name)
        w, h = node_sizes[name]
        if name in facts:
            fill = "#e3f2fd"
            stroke = "#1e88e5"
        elif name in dims:
            fill = "#f3e5f5"
            stroke = "#8e24aa"
        else:
            fill = "#eceff1"
            stroke = "#607d8b"
        nodes.append(
            f'<g class="node" data-name="{escape(name)}" data-width="{w}" data-height="{h}" '
            f'transform="translate({x:.1f},{y:.1f})">'
            f'<rect x="0" y="0" rx="8" ry="8" width="{w}" height="{h}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2" />'
            f'<text x="12" y="50" font-family="Segoe UI, Arial" '
            f'font-size="14" fill="#1f2937">{escape(name)}</text>'
            "</g>"
        )

    return (
        f'<svg id="relationship-diagram" viewBox="0 0 {width} {height}" width="100%" height="640" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Diagrama de relacionamentos">'
        '<rect width="100%" height="100%" fill="#ffffff" />'
        '<g id="relationship-content">'
        '<g id="relationship-edges">'
        + "".join(relation_lines)
        + "</g>"
        '<g id="relationship-nodes">'
        + "".join(nodes)
        + "</g>"
        "</g>"
        + "</svg>"
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "utc": datetime.now(timezone.utc).isoformat()})


@app.post("/api/extract-relations")
def extract_relations_api():
    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "Arquivo .pbit não enviado."}), 400

    if not _is_allowed_file(uploaded_file.filename):
        return jsonify({"error": "Formato inválido. Envie um arquivo .pbit."}), 400

    try:
        insights = _extract_model_insights(uploaded_file)
    except Exception as exc:
        return jsonify({"error": f"Falha ao extrair relacionamentos: {exc}"}), 400

    relations = insights["relations"]
    diagram_svg = _build_diagram_svg(relations)
    return jsonify(
        {
            "file_name": uploaded_file.filename,
            **insights,
            "diagram_svg": diagram_svg,
        }
    )


@app.post("/extract")
def extract_relations_ui():
    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        return render_template("index.html", error="Envie um arquivo .pbit."), 400

    if not _is_allowed_file(uploaded_file.filename):
        return render_template(
            "index.html", error="Formato inválido. Selecione um arquivo .pbit."
        ), 400

    try:
        insights = _extract_model_insights(uploaded_file)
    except Exception as exc:
        return render_template(
            "index.html", error=f"Não foi possível processar o arquivo: {exc}"
        ), 400

    relations = insights["relations"]
    diagram_svg = _build_diagram_svg(relations)
    result = {"file_name": uploaded_file.filename, **insights, "diagram_svg": diagram_svg}
    return render_template(
        "index.html",
        result=result,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
