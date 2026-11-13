from __future__ import annotations

import threading
import webbrowser

from flask import Flask, jsonify, render_template, request

from pensioni import stima_importo
from ricerca import cerca

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"
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
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/ricerca")
def api_ricerca():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    if not query:
        return jsonify({"ok": False, "error": "Inserire una query di ricerca."}), 400
    try:
        return jsonify({
            "ok": True,
            "result": cerca(
                query,
                area=payload.get("area") or None,
                ambito=payload.get("ambito") or None,
                territorio=payload.get("territorio") or None,
                alla_data=payload.get("alla_data") or None,
                limite=int(payload.get("limite", 20)),
            ),
        })
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


def main():
    # Apri il browser solo dopo che Flask ha avuto il tempo di avviare il server.
    threading.Timer(1.0, lambda: webbrowser.open(URL)).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
