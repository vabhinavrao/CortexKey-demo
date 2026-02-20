"""
CortexKey — Shared EEG pipeline for Vercel serverless functions.
Mirrors backend/eeg_pipeline.py but is self-contained (no disk model).
"""

import numpy as np
from scipy import signal as sig
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Filter design
# ---------------------------------------------------------------------------
FS = 250

_notch_b, _notch_a = sig.iirnotch(50.0, 30.0, FS)
_bp_b, _bp_a = sig.butter(4, [5.0, 30.0], btype="band", fs=FS)


def apply_notch(data):
    return sig.filtfilt(_notch_b, _notch_a, data)


def apply_bandpass(data):
    return sig.filtfilt(_bp_b, _bp_a, data)


def compute_band_power(psd, freqs, low, high):
    idx = np.logical_and(freqs >= low, freqs <= high)
    if not np.any(idx):
        return 0.0
    return float(np.trapz(psd[idx], freqs[idx]))


def extract_features(raw_window, fs=FS):
    data = apply_notch(raw_window)
    data = apply_bandpass(data)
    nperseg = min(256, len(data))
    freqs, psd = sig.welch(data, fs=fs, nperseg=nperseg)

    theta = compute_band_power(psd, freqs, 4.0, 8.0)
    alpha = compute_band_power(psd, freqs, 8.0, 13.0)
    beta = compute_band_power(psd, freqs, 13.0, 30.0)
    total = theta + alpha + beta + 1e-12

    alpha_theta = alpha / (theta + 1e-12)
    alpha_beta = alpha / (beta + 1e-12)

    return np.array([theta, alpha, beta, alpha_theta, alpha_beta, total])


def process_window(raw_window, fs=FS):
    filtered = apply_bandpass(apply_notch(raw_window))
    nperseg = min(256, len(filtered))
    freqs, psd = sig.welch(filtered, fs=fs, nperseg=nperseg)
    theta = compute_band_power(psd, freqs, 4.0, 8.0)
    alpha = compute_band_power(psd, freqs, 8.0, 13.0)
    beta = compute_band_power(psd, freqs, 13.0, 30.0)
    features = extract_features(raw_window, fs)
    return {
        "filtered": filtered.tolist(),
        "features": features.tolist(),
        "band_powers": {
            "theta": round(float(theta), 4),
            "alpha": round(float(alpha), 4),
            "beta": round(float(beta), 4),
        },
    }


# ---------------------------------------------------------------------------
# Mock data generators
# ---------------------------------------------------------------------------

def generate_auth_user(duration=2.0, fs=FS):
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    return (
        2.5 * np.sin(2 * np.pi * 10 * t)
        + 1.2 * np.sin(2 * np.pi * 20 * t)
        + 0.6 * np.sin(2 * np.pi * 6 * t)
        + 0.3 * np.random.randn(len(t))
    )


def generate_impostor(duration=2.0, fs=FS):
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    return 1.5 * np.random.randn(len(t))


# ---------------------------------------------------------------------------
# In-memory model (trained on first import — no .pkl files needed)
# ---------------------------------------------------------------------------
_model = None
_scaler = None


def _train_model():
    global _model, _scaler
    np.random.seed(42)
    X_auth = [extract_features(generate_auth_user()) for _ in range(200)]
    X_imp = [extract_features(generate_impostor()) for _ in range(200)]
    X = np.array(X_auth + X_imp)
    y = np.array([1] * 200 + [0] * 200)
    _scaler = StandardScaler()
    X_scaled = _scaler.fit_transform(X)
    _model = SVC(kernel="rbf", C=1.0, gamma="scale", probability=True)
    _model.fit(X_scaled, y)


def predict(features):
    global _model, _scaler
    if _model is None:
        _train_model()
    X = np.array(features).reshape(1, -1)
    X_scaled = _scaler.transform(X)
    proba = _model.predict_proba(X_scaled)[0]
    label = int(np.argmax(proba))
    confidence = float(proba[1])
    return {"label": label, "confidence": round(confidence, 4)}
