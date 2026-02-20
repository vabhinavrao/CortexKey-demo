"""
CortexKey - Model Training Script

Generates synthetic EEG data (authenticated vs impostor),
extracts features, trains an SVM classifier, and saves to disk.

Run once before starting the backend:
    python train_model.py
"""

import os
import sys
import numpy as np
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import joblib

# Ensure we can import sibling modules when run as a script
sys.path.insert(0, os.path.dirname(__file__))

from eeg_pipeline import extract_features, generate_auth_user, generate_impostor

MODEL_DIR   = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH  = os.path.join(MODEL_DIR, "svm_model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")


def train_and_save(n_samples: int = 300):
    """Generate data, train SVM, save model + scaler."""

    print(f"[train] Generating {n_samples} authenticated samples …")
    X_auth = [extract_features(generate_auth_user()) for _ in range(n_samples)]
    y_auth = [1] * n_samples

    print(f"[train] Generating {n_samples} impostor samples …")
    X_imp = [extract_features(generate_impostor()) for _ in range(n_samples)]
    y_imp = [0] * n_samples

    X = np.array(X_auth + X_imp)
    y = np.array(y_auth + y_imp)

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train
    model = SVC(kernel="rbf", C=1.0, gamma="scale", probability=True)
    model.fit(X_scaled, y)

    # Quick cross-validation sanity check
    scores = cross_val_score(model, X_scaled, y, cv=5)
    print(f"[train] CV accuracy: {scores.mean():.3f} ± {scores.std():.3f}")

    # Save
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"[train] Model saved to {MODEL_PATH}")
    print(f"[train] Scaler saved to {SCALER_PATH}")

    return model, scaler


if __name__ == "__main__":
    train_and_save()
