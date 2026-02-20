"""
CortexKey — Vercel Serverless API (Flask WSGI)

Single Flask app handling all API routes.
Vercel auto-detects the `app` WSGI variable.
"""

import os
import sys
import json
import numpy as np
from flask import Flask, jsonify, request

# Add api/ directory to path so _pipeline is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _pipeline import (
    generate_auth_user,
    generate_impostor,
    process_window,
    predict,
)

app = Flask(__name__)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "serial_connected": False,
        "mock_mode": "cloud",
        "auth_status": "idle",
        "deployment": "vercel",
    })


@app.route("/api/auth/start", methods=["POST", "OPTIONS"])
def auth_start():
    if request.method == "OPTIONS":
        return _cors_preflight()

    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "auth")
    num_chunks = 6

    chunks = []
    confidence_history = []

    for i in range(num_chunks):
        window = generate_auth_user() if mode == "auth" else generate_impostor()
        result = process_window(window)
        pred = predict(result["features"])
        confidence_history.append(pred["confidence"])

        if len(confidence_history) >= 3:
            smoothed = (0.5 * confidence_history[-1]
                        + 0.3 * confidence_history[-2]
                        + 0.2 * confidence_history[-3])
        else:
            smoothed = sum(confidence_history) / len(confidence_history)

        chunks.append({
            "chunk": i + 1,
            "confidence": round(smoothed, 4),
            "band_powers": result["band_powers"],
            "waveform": result["filtered"][-80:],
        })

    final_confidence = chunks[-1]["confidence"]
    status = "authenticated" if final_confidence >= 0.65 else "denied"

    resp = jsonify({
        "ok": True,
        "status": status,
        "confidence": final_confidence,
        "chunks": chunks,
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    return jsonify({
        "status": "idle",
        "confidence": 0.0,
        "chunks": 0,
        "waveform": [],
    })


@app.route("/api/auth/stop", methods=["POST", "OPTIONS"])
def auth_stop():
    if request.method == "OPTIONS":
        return _cors_preflight()
    resp = jsonify({"ok": True, "status": "idle"})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/demo/mode", methods=["POST", "OPTIONS"])
def demo_mode():
    if request.method == "OPTIONS":
        return _cors_preflight()
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "auth")
    resp = jsonify({"ok": True, "mode": mode})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def _cors_preflight():
    resp = jsonify({})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response
