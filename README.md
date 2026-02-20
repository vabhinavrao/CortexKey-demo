# 🧠 CortexKey — Neural Authentication System

> Authenticate users by their unique brainwave (EEG) patterns.  
> Built for a 24-hour hackathon. Works with mock data today, real BioAmp EXG Pill sensor tomorrow.

---

## Quick Start (3 commands)

```bash
cd cortexkey
pip install -r requirements.txt
python backend/app.py
```

Open **http://localhost:5001** in Chrome/Edge.

---

## Architecture

```
ESP32 + BioAmp EXG Pill  →  Python Flask Backend  →  Web Dashboard
       (sensor layer)          (ML pipeline)          (live UI)
```

| Layer | Tech | Status |
|-------|------|--------|
| Firmware | C++ / Arduino (ESP32) | ✅ Mock data mode |
| Backend | Python, Flask, scikit-learn | ✅ Full pipeline |
| Frontend | Vanilla JS, Canvas, WebSocket | ✅ Live dashboard |

---

## Demo Flow (90 seconds)

1. Open `http://localhost:5000`
2. Click **Mock Authenticated** → Click **Start Authentication**
3. Watch the oscilloscope + confidence meter → **ACCESS GRANTED** at ~85%
4. Click **Mock Impostor** → Click **Start Authentication**
5. Watch confidence stay low → **ACCESS DENIED** at ~30%
6. _"Tomorrow we swap mock data for real brainwaves — one line change."_

---

## How It Works

### Signal Processing Pipeline
```
Raw EEG (250 Hz) → 50 Hz Notch Filter → 5-30 Hz Bandpass → Welch PSD → Feature Extraction
```

### Features (6D vector)
| # | Feature | Description |
|---|---------|-------------|
| 1 | Theta power | 4-8 Hz band energy |
| 2 | Alpha power | 8-13 Hz band energy |
| 3 | Beta power | 13-30 Hz band energy |
| 4 | Alpha/Theta | Focus indicator |
| 5 | Alpha/Beta | Relaxation ratio |
| 6 | Total power | Overall signal energy |

### ML Classifier
- SVM with RBF kernel (scikit-learn)
- Auto-trains on first launch (300 auth + 300 impostor synthetic samples)
- Threshold: 65% confidence for access

---

## Project Structure

```
cortexkey/
├── firmware/
│   └── esp32_neural_auth.ino    # ESP32 firmware (mock + real sensor)
├── backend/
│   ├── app.py                   # Flask server + WebSocket + API
│   ├── eeg_pipeline.py          # Signal processing + feature extraction
│   ├── ml_model.py              # SVM classifier wrapper
│   ├── serial_reader.py         # ESP32 serial / mock data reader
│   ├── train_model.py           # Model training script
│   └── models/                  # Saved model + scaler (.pkl)
├── frontend/
│   ├── index.html               # Dashboard UI
│   ├── css/style.css            # Dark sci-fi theme
│   └── js/app.js                # Oscilloscope, gauge, WebSocket
├── requirements.txt
└── README.md
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | System status |
| `POST` | `/api/auth/start` | Begin authentication scan |
| `GET` | `/api/auth/status` | Current confidence + waveform |
| `POST` | `/api/auth/stop` | Cancel scan |
| `POST` | `/api/demo/mode` | Switch mock mode `{ "mode": "auth" \| "impostor" }` |
| `POST` | `/api/enroll` | Enroll new user (placeholder) |
| `GET` | `/api/serial/ports` | List serial ports |
| `POST` | `/api/serial/connect` | Connect to ESP32 `{ "port": "/dev/ttyUSB0" }` |

### WebSocket Events (from server)
| Event | Payload |
|-------|---------|
| `waveform_update` | `{ waveform: float[] }` |
| `confidence_update` | `{ confidence, band_powers, chunk }` |
| `auth_complete` | `{ status, confidence }` |

---

## Switching to Real Sensor

When the BioAmp EXG Pill arrives, make **one change** in the firmware:

```cpp
// firmware/esp32_neural_auth.ino, line 27
#define USE_MOCK_DATA    false   // ← Change true to false
```

Flash the ESP32, connect via USB, and run the backend with:
```python
# The backend auto-detects serial ports, or specify manually:
POST /api/serial/connect  { "port": "/dev/tty.usbserial-XXX" }
```

Everything else (filters, ML model, frontend) stays identical.

---

## Hardware Wiring (for tomorrow)

```
BioAmp EXG Pill:
  OUT → ESP32 GPIO34
  VCC → 3.3V
  GND → GND

Electrodes:
  Fp1 (left forehead)   → BioAmp IN+
  Fp2 (right forehead)  → BioAmp IN-
  Mastoid (behind ear)   → BioAmp REF
```

---

## License

MIT — Built for learning and hackathons.
