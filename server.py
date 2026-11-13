from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from pensioni import stima_importo
from ricerca import cerca

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "status": "ready", "name": "Jarvis Consulenti"})


@app.post("/api/pensione")
def api_pensione():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "result": stima_importo(payload)})
    except ValueError as exc:  # pragma: no cover - runtime validation path
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/ricerca")
def api_ricerca():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    if not query:
        return jsonify({"ok": False, "error": "Inserire una query di ricerca."}), 400
    try:
        filtro_area = payload.get("area")
        filtro_ambito = payload.get("ambito")
        filtro_territorio = payload.get("territorio")
        data_ref = payload.get("alla_data")
        limite = payload.get("limite", 20)
        return jsonify({
            "ok": True,
            "result": cerca(
                query,
                area=filtro_area,
                ambito=filtro_ambito,
                territorio=filtro_territorio,
                alla_data=data_ref,
                limite=int(limite),
            ),
        })
    except ValueError as exc:  # pragma: no cover - runtime validation path
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
