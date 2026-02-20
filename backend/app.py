"""
CortexKey - Flask Backend

REST API + WebSocket server for the Neural Authentication System.
Serves the frontend, communicates with the ESP32 (or mock),
runs the EEG processing pipeline, and pushes live updates.
"""

import os
import sys
import time
import threading
import numpy as np

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

# Ensure sibling imports work
sys.path.insert(0, os.path.dirname(__file__))

from serial_reader import reader
from eeg_pipeline import process_window, extract_features, FS
from ml_model import ensure_model, predict

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
auth_state = {
    "status": "idle",        # idle | scanning | authenticated | denied
    "confidence": 0.0,
    "chunks_processed": 0,
    "confidence_history": [],
    "start_time": None,
}

_push_thread = None
_push_running = False


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.route("/api/health")
def health():
    return jsonify({
        "status": "online",
        "serial_connected": reader.connected,
        "mock_mode": reader.mock_mode,
        "auth_status": auth_state["status"],
    })


@app.route("/api/auth/start", methods=["POST"])
def auth_start():
    """Begin an authentication scan."""
    auth_state["status"] = "scanning"
    auth_state["confidence"] = 0.0
    auth_state["chunks_processed"] = 0
    auth_state["confidence_history"] = []
    auth_state["start_time"] = time.time()

    # Make sure serial reader is running
    if not reader.connected:
        reader.connect()
    reader.start()
    # Flush stale buffer and tell ESP32/simulator to start auth scan
    reader.flush_buffer()
    reader.send_command("START_AUTH")

    _start_push_loop()

    return jsonify({"ok": True, "status": "scanning"})


@app.route("/api/auth/status")
def auth_status():
    waveform = reader.get_latest(80)
    return jsonify({
        "status": auth_state["status"],
        "confidence": auth_state["confidence"],
        "chunks": auth_state["chunks_processed"],
        "waveform": waveform,
    })


@app.route("/api/auth/stop", methods=["POST"])
def auth_stop():
    auth_state["status"] = "idle"
    reader.send_command("STOP")
    _stop_push_loop()
    return jsonify({"ok": True, "status": "idle"})


@app.route("/api/enroll", methods=["POST"])
def enroll():
    """Placeholder for user enrollment (nice-to-have)."""
    return jsonify({"ok": True, "message": "Enrollment placeholder"})


@app.route("/api/demo/mode", methods=["POST"])
def demo_mode():
    """Switch mock data mode: { "mode": "auth" | "impostor" }"""
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "auth")
    reader.set_mock_mode(mode)
    return jsonify({"ok": True, "mode": mode})


@app.route("/api/serial/ports")
def serial_ports():
    return jsonify({"ports": reader.list_ports()})


@app.route("/api/serial/connect", methods=["POST"])
def serial_connect():
    data = request.get_json(silent=True) or {}
    port = data.get("port")
    reader.connect(port)
    reader.start()
    return jsonify({"ok": True, "connected": reader.connected})


# ---------------------------------------------------------------------------
# WebSocket push loop
# ---------------------------------------------------------------------------

def _start_push_loop():
    global _push_thread, _push_running
    if _push_running:
        return
    _push_running = True
    _push_thread = threading.Thread(target=_push_loop, daemon=True)
    _push_thread.start()


def _stop_push_loop():
    global _push_running
    _push_running = False


def _push_loop():
    """
    Every ~200 ms, grab the latest window, run the pipeline,
    and push updates to the frontend over WebSocket.
    """
    global _push_running
    chunks_needed = 6  # ~6 chunks × 200ms ≈ 3-5 seconds total

    while _push_running and auth_state["status"] == "scanning":
        time.sleep(0.2)

        window = reader.get_window()
        if window is None or len(window) < 250:
            # Not enough data yet — send waveform only
            waveform = reader.get_latest(80)
            socketio.emit("waveform_update", {"waveform": waveform})
            continue

        # Process
        result = process_window(window)
        features = np.array(result["features"])
        pred = predict(features)

        auth_state["chunks_processed"] += 1
        auth_state["confidence_history"].append(pred["confidence"])

        # Smoothed confidence (exponential moving average)
        history = auth_state["confidence_history"]
        if len(history) >= 3:
            smoothed = 0.5 * history[-1] + 0.3 * history[-2] + 0.2 * history[-3]
        else:
            smoothed = np.mean(history)
        auth_state["confidence"] = round(float(smoothed), 4)

        # Send updates
        waveform = reader.get_latest(80)
        socketio.emit("waveform_update", {"waveform": waveform})
        socketio.emit("confidence_update", {
            "confidence": auth_state["confidence"],
            "band_powers": result["band_powers"],
            "chunk": auth_state["chunks_processed"],
        })

        # Check if we have enough chunks to decide
        if auth_state["chunks_processed"] >= chunks_needed:
            if auth_state["confidence"] >= 0.65:
                auth_state["status"] = "authenticated"
            else:
                auth_state["status"] = "denied"

            socketio.emit("auth_complete", {
                "status": auth_state["status"],
                "confidence": auth_state["confidence"],
            })
            _push_running = False
            break

    _push_running = False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Auto-train model if needed
    ensure_model()

    # Start serial reader in mock mode (no hardware required)
    reader.connect()
    reader.start()

    print("\n" + "=" * 56)
    print("  CortexKey Neural Authentication System")
    print("  Backend running on http://localhost:5001")
    print("=" * 56 + "\n")

    socketio.run(app, host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()
