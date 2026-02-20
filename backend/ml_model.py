"""
CortexKey - ML Classification Module

Uses a pre-trained SVM (RBF kernel) to classify EEG feature vectors
as *authenticated* (1) or *impostor* (0).

The model and scaler are loaded from disk.  If they don't exist yet,
call `train_model.py` first (or use `ensure_model()` which auto-trains).
"""

import os
import joblib
import numpy as np

MODEL_DIR   = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH  = os.path.join(MODEL_DIR, "svm_model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")

_model  = None
_scaler = None


def _load():
    """Load model + scaler from disk (lazy, once)."""
    global _model, _scaler
    if _model is None or _scaler is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run train_model.py first."
            )
        _model  = joblib.load(MODEL_PATH)
        _scaler = joblib.load(SCALER_PATH)


def ensure_model():
    """If no model on disk, train one automatically."""
    if not os.path.exists(MODEL_PATH):
        print("[ml_model] No model found — training now …")
        from train_model import train_and_save
        train_and_save()
    _load()


def predict(features: np.ndarray) -> dict:
    """
    Classify a single 6D feature vector.

    Returns
    -------
    dict  with keys:
        label       : int   (1 = authenticated, 0 = impostor)
        confidence  : float (0.0 – 1.0)
    """
    _load()
    X = np.array(features).reshape(1, -1)
    X_scaled = _scaler.transform(X)
    proba = _model.predict_proba(X_scaled)[0]   # [p_impostor, p_auth]
    label = int(np.argmax(proba))
    confidence = float(proba[1])                 # probability of "authenticated"
    return {"label": label, "confidence": round(confidence, 4)}
