"""
CortexKey - EEG Signal Processing Pipeline

Processes raw EEG data through:
  1. 50Hz Notch filter (powerline noise)
  2. 5-30Hz Bandpass filter (Alpha + Beta bands)
  3. Feature extraction (PSD, band powers, ratios)

Output: 6-dimensional feature vector for ML classification.
"""

import numpy as np
from scipy import signal as sig


# ---------------------------------------------------------------------------
# Filter design (computed once at import time)
# ---------------------------------------------------------------------------
FS = 250  # Sample rate in Hz

# 50 Hz notch (Q = 30)
_notch_b, _notch_a = sig.iirnotch(50.0, 30.0, FS)

# 5-30 Hz bandpass (Butterworth 4th order)
_bp_b, _bp_a = sig.butter(4, [5.0, 30.0], btype="band", fs=FS)


def apply_notch(data: np.ndarray) -> np.ndarray:
    """Remove 50 Hz powerline interference."""
    return sig.filtfilt(_notch_b, _notch_a, data)


def apply_bandpass(data: np.ndarray) -> np.ndarray:
    """Keep only 5-30 Hz (Alpha + Beta bands)."""
    return sig.filtfilt(_bp_b, _bp_a, data)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def compute_band_power(psd: np.ndarray, freqs: np.ndarray,
                       low: float, high: float) -> float:
    """Integrate PSD between *low* and *high* Hz."""
    idx = np.logical_and(freqs >= low, freqs <= high)
    if not np.any(idx):
        return 0.0
    return float(np.trapz(psd[idx], freqs[idx]))


def extract_features(raw_window: np.ndarray, fs: int = FS) -> np.ndarray:
    """
    Full processing pipeline for one 2-second window (500 samples).

    Returns a 6-element feature vector:
        [theta_power, alpha_power, beta_power,
         alpha_theta_ratio, alpha_beta_ratio, total_power]
    """
    # --- pre-processing ---------------------------------------------------
    data = apply_notch(raw_window)
    data = apply_bandpass(data)

    # --- PSD via Welch's method -------------------------------------------
    nperseg = min(256, len(data))
    freqs, psd = sig.welch(data, fs=fs, nperseg=nperseg)

    # --- band powers ------------------------------------------------------
    theta = compute_band_power(psd, freqs, 4.0, 8.0)
    alpha = compute_band_power(psd, freqs, 8.0, 13.0)
    beta  = compute_band_power(psd, freqs, 13.0, 30.0)
    total = theta + alpha + beta + 1e-12  # avoid /0

    # --- ratios -----------------------------------------------------------
    alpha_theta = alpha / (theta + 1e-12)
    alpha_beta  = alpha / (beta  + 1e-12)

    return np.array([theta, alpha, beta,
                     alpha_theta, alpha_beta, total], dtype=np.float64)


def process_window(raw_window: np.ndarray, fs: int = FS):
    """
    Convenience wrapper that returns both the filtered signal
    (for the oscilloscope) and the feature vector (for the ML model).
    """
    filtered = apply_bandpass(apply_notch(raw_window))

    # Band powers for the bar chart
    nperseg = min(256, len(filtered))
    freqs, psd = sig.welch(filtered, fs=fs, nperseg=nperseg)
    theta = compute_band_power(psd, freqs, 4.0, 8.0)
    alpha = compute_band_power(psd, freqs, 8.0, 13.0)
    beta  = compute_band_power(psd, freqs, 13.0, 30.0)

    features = extract_features(raw_window, fs)

    return {
        "filtered": filtered.tolist(),
        "features": features.tolist(),
        "band_powers": {
            "theta": round(float(theta), 4),
            "alpha": round(float(alpha), 4),
            "beta":  round(float(beta), 4),
        },
    }


# ---------------------------------------------------------------------------
# Synthetic data generators (mirror the ESP32 mock modes)
# ---------------------------------------------------------------------------

def generate_auth_user(duration: float = 2.0, fs: int = FS) -> np.ndarray:
    """Authenticated user: strong Alpha + moderate Beta + low noise."""
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    return (
        2.5 * np.sin(2 * np.pi * 10 * t)       # Alpha 10 Hz
        + 1.2 * np.sin(2 * np.pi * 20 * t)      # Beta  20 Hz
        + 0.6 * np.sin(2 * np.pi * 6 * t)       # Theta  6 Hz
        + 0.3 * np.random.randn(len(t))          # Noise
    )


def generate_impostor(duration: float = 2.0, fs: int = FS) -> np.ndarray:
    """Impostor: mostly random noise, no coherent peaks."""
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    return 1.5 * np.random.randn(len(t))
