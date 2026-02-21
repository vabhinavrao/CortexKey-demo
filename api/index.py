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


@app.route("/api/demo_mode", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/demo/mode", methods=["GET", "POST", "OPTIONS"])
def demo_mode():
    if request.method == "OPTIONS":
        return _cors_preflight()
    
    if request.method == "GET":
        # Return a simple demo page
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CortexKey Demo - API Test</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .status {
            background: #f0f0f0;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 8px;
        }
        .status-label {
            font-weight: 600;
            color: #333;
        }
        .status-value {
            color: #667eea;
            font-family: 'Courier New', monospace;
        }
        .btn-group {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 20px;
        }
        button {
            padding: 15px 25px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        button:active {
            transform: translateY(0);
        }
        .response {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
            display: none;
        }
        .response.show {
            display: block;
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-success {
            background: #10b981;
            color: white;
        }
        .badge-warning {
            background: #f59e0b;
            color: white;
        }
        .link {
            color: #667eea;
            text-decoration: none;
            font-size: 14px;
            display: block;
            margin-top: 20px;
            text-align: center;
        }
        .link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 CortexKey Demo API</h1>
        <p class="subtitle">Production deployment test interface</p>
        
        <div class="status">
            <div class="status-item">
                <span class="status-label">Status:</span>
                <span class="status-value"><span class="badge badge-success">✓ ONLINE</span></span>
            </div>
            <div class="status-item">
                <span class="status-label">Mode:</span>
                <span class="status-value">Mock/Cloud</span>
            </div>
            <div class="status-item">
                <span class="status-label">Environment:</span>
                <span class="status-value">Vercel Production</span>
            </div>
            <div class="status-item">
                <span class="status-label">API Version:</span>
                <span class="status-value">v1.0.0</span>
            </div>
        </div>

        <div class="btn-group">
            <button class="btn-primary" onclick="testAuth()">Test Auth (User)</button>
            <button class="btn-secondary" onclick="testImpostor()">Test Impostor</button>
            <button class="btn-secondary" onclick="testHealth()">Health Check</button>
            <button class="btn-secondary" onclick="testStop()">Stop Auth</button>
        </div>

        <div id="response" class="response"></div>

        <a href="/" class="link">← Back to Main App</a>
        <a href="https://github.com/vabhinavrao/CortexKey-demo" class="link">View on GitHub</a>
    </div>

    <script>
        const responseDiv = document.getElementById('response');

        function showResponse(data) {
            responseDiv.textContent = JSON.stringify(data, null, 2);
            responseDiv.classList.add('show');
        }

        async function testHealth() {
            try {
                const res = await fetch('/api/health');
                const data = await res.json();
                showResponse(data);
            } catch (err) {
                showResponse({ error: err.message });
            }
        }

        async function testAuth() {
            try {
                responseDiv.textContent = '⏳ Running authentication (6 chunks)...';
                responseDiv.classList.add('show');
                
                const res = await fetch('/api/auth/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: 'auth' })
                });
                const data = await res.json();
                showResponse(data);
            } catch (err) {
                showResponse({ error: err.message });
            }
        }

        async function testImpostor() {
            try {
                responseDiv.textContent = '⏳ Running impostor test (6 chunks)...';
                responseDiv.classList.add('show');
                
                const res = await fetch('/api/auth/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: 'impostor' })
                });
                const data = await res.json();
                showResponse(data);
            } catch (err) {
                showResponse({ error: err.message });
            }
        }

        async function testStop() {
            try {
                const res = await fetch('/api/auth/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();
                showResponse(data);
            } catch (err) {
                showResponse({ error: err.message });
            }
        }

        // Auto-run health check on load
        window.addEventListener('load', testHealth);
    </script>
</body>
</html>
        """
        return html, 200, {'Content-Type': 'text/html'}
    
    # POST request
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
