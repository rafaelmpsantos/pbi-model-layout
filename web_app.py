import json
import os
import tempfile
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from pbix_layout_tool import extract_relations_from_pbit

ALLOWED_EXTENSIONS = {"pbit"}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE


def _is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _extract_relations(uploaded_file) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmpdir:
        source_name = secure_filename(uploaded_file.filename or "model.pbit")
        source_path = os.path.join(tmpdir, source_name)
        output_path = os.path.join(tmpdir, "relations.json")
        uploaded_file.save(source_path)

        extract_relations_from_pbit(source_path, output_path=output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)


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
        relations = _extract_relations(uploaded_file)
    except Exception as exc:
        return jsonify({"error": f"Falha ao extrair relacionamentos: {exc}"}), 400

    return jsonify(
        {
            "file_name": uploaded_file.filename,
            "relationship_count": len(relations),
            "relations": relations,
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
        relations = _extract_relations(uploaded_file)
    except Exception as exc:
        return render_template(
            "index.html", error=f"Não foi possível processar o arquivo: {exc}"
        ), 400

    return render_template(
        "index.html",
        result={
            "file_name": uploaded_file.filename,
            "relationship_count": len(relations),
            "relations": relations,
        },
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
