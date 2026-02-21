#!/usr/bin/env python3
"""
CortexKey: Brainwave Authenticator (ESP32 -> Encrypted Signature)

Collects EEG-like signals from an ESP32 over serial, computes frequency-band
features, and produces an encrypted brainwave signature for authentication.

Features:
- 50Hz Notch Filter & 5Hz-30Hz Bandpass Filter
- Welch's Method for PSD estimation
- Strided sliding window processing
- AES-GCM encryption with HKDF-SHA256 key derivation
- Robust serial handling with reconnection logic
- Comprehensive logging and error handling
- **MOCK MODE**: Auto-fallback to synthetic data when hardware unavailable
- **HYBRID MODE**: Seamlessly switches between mock and real hardware

Dependencies:
    pip install pyserial numpy scipy cryptography
"""

from __future__ import annotations

import argparse
import base64
import logging
import os
import sys
import time
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, List, Optional, Tuple

import numpy as np

try:
    import serial
    HAS_SERIAL = True
except Exception:  # pragma: no cover
    serial = None  # type: ignore
    HAS_SERIAL = False

try:
    from scipy import signal
except Exception:  # pragma: no cover
    signal = None  # Checked at runtime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


DEFAULT_FS = 256.0
DEFAULT_WINDOW = 512
DEFAULT_STEP = 128
DEFAULT_BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 12.0),
    "beta": (12.0, 30.0),
    "gamma": (30.0, 45.0),
}
NOTCH_FREQ = 50.0
NOTCH_Q = 30.0
BANDPASS_LOW = 5.0
BANDPASS_HIGH = 30.0
BUTTERWORTH_ORDER = 4

# Mock data generation constants
MOCK_AUTH_MODE = "authenticated"
MOCK_IMPOSTOR_MODE = "impostor"


def setup_logging(
    log_dir: Path, log_filename: str = "brainwave_auth.log"
) -> logging.Logger:
    """Configure logging to both file and stdout."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_filename

    logger = logging.getLogger("CortexKey.Auth")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s: %(message)s",
        datefmt="%Y%m%d_%H%M%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


@contextmanager
def managed_serial(
    port: str, baud: int, timeout: float = 1.0
) -> Generator[Any, None, None]:
    """Context manager for serial port with automatic cleanup."""
    if not HAS_SERIAL or serial is None:
        raise RuntimeError("pyserial is not installed. Run: pip install pyserial")

    ser = serial.Serial(port, baud, timeout=timeout)
    try:
        yield ser
    finally:
        if ser.is_open:
            ser.close()


@contextmanager
def managed_file(path: Path, mode: str = "a") -> Generator:
    """Context manager for file handles with automatic cleanup."""
    f = open(path, mode, encoding="utf-8")
    try:
        yield f
    finally:
        f.close()


class BrainwaveProcessor:
    """Processes EEG data and generates encrypted signatures."""

    def __init__(
        self,
        fs: float,
        passphrase: str,
        bands: dict[str, tuple[float, float]] = DEFAULT_BANDS,
        notch_freq: float = NOTCH_FREQ,
        notch_q: float = NOTCH_Q,
        bandpass: tuple[float, float] = (BANDPASS_LOW, BANDPASS_HIGH),
        butter_order: int = BUTTERWORTH_ORDER,
    ):
        self._validate_inputs(fs, passphrase, bands)
        self.fs = fs
        self.passphrase = passphrase
        self.bands = bands
        self.notch_freq = notch_freq
        self.notch_q = notch_q
        self.bandpass = bandpass
        self.butter_order = butter_order

        self._notch_coeffs = self._compute_notch_coeffs()
        self._bandpass_coeffs = self._compute_bandpass_coeffs()
        self.key, self.salt = self._derive_key(passphrase)

    def _validate_inputs(self, fs: float, passphrase: str, bands: dict) -> None:
        """Validate processor parameters."""
        if fs <= 0:
            raise ValueError(f"Sampling frequency must be positive, got {fs}")
        if not passphrase or not passphrase.strip():
            raise ValueError("Passphrase cannot be empty")
        if not bands:
            raise ValueError("Frequency bands cannot be empty")
        for name, (low, high) in bands.items():
            if low >= high:
                raise ValueError(
                    f"Band '{name}': low ({low}) must be less than high ({high})"
                )
            if low < 0 or high > fs / 2:
                raise ValueError(f"Band '{name}': frequencies must be in [0, fs/2]")

    def _compute_notch_coeffs(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute IIR notch filter coefficients."""
        if signal is None:
            raise RuntimeError("scipy.signal is required for filtering")
        return signal.iirnotch(self.notch_freq, self.notch_q, self.fs)

    def _compute_bandpass_coeffs(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute IIR bandpass filter coefficients."""
        if signal is None:
            raise RuntimeError("scipy.signal is required for filtering")
        nyquist = self.fs / 2
        low = self.bandpass[0] / nyquist
        high = self.bandpass[1] / nyquist
        return signal.butter(self.butter_order, [low, high], btype="band")

    def _derive_key(self, passphrase: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Derive 32-byte AES key from passphrase using HKDF-SHA256."""
        if salt is None:
            salt = os.urandom(16)
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"brainwave-auth-v1",
            backend=default_backend(),
        )
        return hkdf.derive(passphrase.encode("utf-8")), salt

    def apply_filters(self, data: np.ndarray) -> np.ndarray:
        """Apply Notch (50Hz) and Bandpass (5-30Hz) filters to data."""
        if signal is None:
            raise RuntimeError("scipy.signal is required for filtering")

        b_notch, a_notch = self._notch_coeffs
        data = signal.filtfilt(b_notch, a_notch, data, axis=0)

        b_bp, a_bp = self._bandpass_coeffs
        data = signal.filtfilt(b_bp, a_bp, data, axis=0)

        return data

    def compute_features(self, window_data: np.ndarray) -> np.ndarray:
        """Compute relative band powers using Welch's method."""
        if signal is None:
            raise RuntimeError("scipy.signal is required for PSD estimation")

        if window_data.size == 0:
            return np.zeros(len(self.bands), dtype=np.float32)

        filtered = self.apply_filters(window_data)

        if filtered.ndim > 1:
            filtered = np.mean(filtered, axis=1)

        nperseg = min(len(filtered), 256)
        freqs, psd = signal.welch(filtered, self.fs, nperseg=nperseg)

        feature_vector = []
        for band_name, (low, high) in self.bands.items():
            idx = (freqs >= low) & (freqs <= high)
            if np.any(idx):
                band_power = np.trapz(psd[idx], freqs[idx])
            else:
                band_power = 0.0
            feature_vector.append(band_power)

        return np.array(feature_vector, dtype=np.float32)

    def encrypt_signature(self, features: np.ndarray) -> str:
        """Encrypt feature vector using AES-GCM."""
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, features.tobytes(), None)
        payload = self.salt + nonce + ciphertext
        return base64.urlsafe_b64encode(payload).decode("ascii")

    def verify_signature(self, signature: str, features: np.ndarray) -> bool:
        """Verify that a signature matches the given features."""
        try:
            payload = base64.urlsafe_b64decode(signature.encode("ascii"))
            salt = payload[:16]
            nonce = payload[16:28]
            ciphertext = payload[28:]

            key, _ = self._derive_key(self.passphrase, salt)
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted == features.tobytes()
        except Exception:
            return False


class MockDataGenerator:
    """
    Generates realistic synthetic EEG data based on real brainwave characteristics.
    
    Based on EEG patterns from PhysioNet EEG Motor Movement/Imagery Dataset
    and typical occipital/parietal lobe recordings during rest and cognitive tasks.
    
    Real EEG characteristics:
    - Amplitude: 10-100 µV (microvolts)
    - Slower oscillations with natural drift
    - 1/f noise (pink noise)
    - Irregular phase relationships
    - Occasional artifacts (eye blinks, muscle tension)
    """

    def __init__(self, fs: float, mode: str = MOCK_AUTH_MODE, logger: Optional[logging.Logger] = None):
        """
        Initialize mock data generator with realistic EEG parameters.
        
        Args:
            fs: Sampling frequency in Hz
            mode: 'authenticated' or 'impostor'
            logger: Optional logger instance
        """
        self.fs = fs
        self.mode = mode
        self.logger = logger or logging.getLogger("CortexKey.Mock")
        self._time = 0.0
        self._sample_interval = 1.0 / fs
        
        # Realistic EEG parameters (microvolts scale)
        self._baseline_drift = 0.0
        self._drift_rate = 0.0
        self._last_blink = 0.0
        self._last_artifact = 0.0
        
        # Individual variability (simulates unique brainwave patterns)
        np.random.seed(None)  # Ensure different patterns each run
        self._alpha_freq = np.random.uniform(9.5, 11.5)      # Individual alpha frequency
        self._alpha_amp = np.random.uniform(15, 35)          # Alpha amplitude in µV
        self._theta_freq = np.random.uniform(5.5, 7.5)       # Theta frequency
        self._beta_freq = np.random.uniform(18, 25)          # Beta frequency
        self._phase_offsets = np.random.uniform(0, 2*np.pi, 5)  # Random phase offsets
        
        # 1/f noise generator state
        self._pink_noise_state = np.zeros(10)
        
    def set_mode(self, mode: str) -> None:
        """Switch between authenticated and impostor mock modes."""
        if mode not in [MOCK_AUTH_MODE, MOCK_IMPOSTOR_MODE]:
            raise ValueError(f"Invalid mode: {mode}. Use 'authenticated' or 'impostor'")
        self.mode = mode
        self.logger.info(f"Mock mode switched to: {mode}")
        # Reset variability when changing modes
        self._alpha_freq = np.random.uniform(9.5, 11.5)
        self._alpha_amp = np.random.uniform(15, 35)
    
    def _generate_pink_noise(self) -> float:
        """
        Generate 1/f pink noise (realistic EEG background).
        Uses Paul Kellet's economy method.
        """
        white = np.random.randn() * 0.5
        self._pink_noise_state[0] = 0.99886 * self._pink_noise_state[0] + white * 0.0555179
        self._pink_noise_state[1] = 0.99332 * self._pink_noise_state[1] + white * 0.0750759
        self._pink_noise_state[2] = 0.96900 * self._pink_noise_state[2] + white * 0.1538520
        self._pink_noise_state[3] = 0.86650 * self._pink_noise_state[3] + white * 0.3104856
        self._pink_noise_state[4] = 0.55000 * self._pink_noise_state[4] + white * 0.5329522
        
        pink = (self._pink_noise_state[0] + self._pink_noise_state[1] + 
                self._pink_noise_state[2] + self._pink_noise_state[3] + 
                self._pink_noise_state[4]) * 0.11
        return pink
    
    def _generate_baseline_drift(self) -> float:
        """
        Generate slow baseline drift (realistic DC offset changes).
        Simulates electrode contact changes and physiological drift.
        """
        # Very slow random walk
        self._drift_rate += np.random.randn() * 0.001
        self._drift_rate *= 0.9995  # Decay towards zero
        self._baseline_drift += self._drift_rate
        self._baseline_drift *= 0.9999  # Slowly return to zero
        return self._baseline_drift
    
    def _generate_eye_blink(self, t: float) -> float:
        """
        Generate realistic eye blink artifact (large amplitude, ~200ms duration).
        Blinks occur randomly every 3-8 seconds.
        """
        if t - self._last_blink > np.random.uniform(3, 8):
            self._last_blink = t
        
        # Eye blink shape: rapid rise, slower decay
        time_since_blink = t - self._last_blink
        if time_since_blink < 0.3:  # 300ms blink duration
            blink = 80 * np.exp(-((time_since_blink - 0.05) ** 2) / 0.002)
            return blink
        return 0.0
    
    def _generate_muscle_artifact(self, t: float) -> float:
        """
        Generate occasional muscle tension artifact (high frequency burst).
        Occurs randomly and unpredictably.
        """
        if np.random.rand() < 0.001:  # 0.1% chance per sample
            self._last_artifact = t
        
        time_since_artifact = t - self._last_artifact
        if time_since_artifact < 0.15:  # 150ms artifact duration
            # High-frequency burst (30-60 Hz muscle noise)
            artifact = (15 * np.sin(2 * np.pi * 45 * t) * 
                       np.exp(-time_since_artifact / 0.05))
            return artifact
        return 0.0
    
    def generate_authenticated(self, t: float) -> float:
        """
        Generate authenticated user EEG pattern - realistic, consistent brainwave signature.
        
        Based on relaxed, eyes-closed resting state with dominant alpha rhythm
        (typical of real authentication scenarios where user is focused).
        
        Characteristics:
        - Strong, consistent alpha (8-13 Hz) in occipital regions: ~20-30 µV
        - Moderate theta (4-8 Hz) background: ~10-15 µV
        - Low beta (13-30 Hz) activity: ~5-10 µV
        - Small delta (0.5-4 Hz) component: ~5 µV
        - Pink noise background: ~3-5 µV
        - Occasional artifacts (realistic but not disruptive)
        
        NOTE: Frequencies are divided by 5 for better visualization (slower waves)
        """
        # Core frequency components with individual phase offsets (5x slower for visibility)
        delta = 4.0 * np.sin(2 * np.pi * (2.5 / 5.0) * t + self._phase_offsets[0])
        theta = 12.0 * np.sin(2 * np.pi * (self._theta_freq / 5.0) * t + self._phase_offsets[1])
        alpha = self._alpha_amp * np.sin(2 * np.pi * (self._alpha_freq / 5.0) * t + self._phase_offsets[2])
        beta = 6.0 * np.sin(2 * np.pi * (self._beta_freq / 5.0) * t + self._phase_offsets[3])
        gamma = 2.5 * np.sin(2 * np.pi * (35 / 5.0) * t + self._phase_offsets[4])
        
        # Alpha harmonics (realistic non-sinusoidal waves) - also 5x slower
        alpha_harmonic = 3.0 * np.sin(2 * np.pi * (self._alpha_freq * 2 / 5.0) * t + self._phase_offsets[2])
        
        # Amplitude modulation (alpha blocking/enhancement - realistic variation) - also slower
        alpha_modulation = 1.0 + 0.15 * np.sin(2 * np.pi * (0.1 / 5.0) * t)  # 0.02 Hz modulation (5x slower)
        theta_modulation = 1.0 + 0.1 * np.sin(2 * np.pi * (0.15 / 5.0) * t + 1.2)
        
        # Realistic background noise (pink noise, not white)
        pink_noise = self._generate_pink_noise() * 3.5
        
        # Physiological artifacts (occasional, realistic)
        baseline_drift = self._generate_baseline_drift()
        eye_blink = self._generate_eye_blink(t) * 0.3  # Reduced blink in authenticated state
        muscle_artifact = self._generate_muscle_artifact(t) * 0.5  # Reduced tension
        
        # Combine components (in microvolts)
        signal = (delta + 
                 theta * theta_modulation + 
                 alpha * alpha_modulation + 
                 alpha_harmonic * 0.3 +
                 beta + 
                 gamma +
                 pink_noise +
                 baseline_drift +
                 eye_blink +
                 muscle_artifact)
        
        return signal
    
    def generate_impostor(self, t: float) -> float:
        """
        Generate impostor EEG pattern - inconsistent, noisy, irregular brainwaves.
        
        Simulates either:
        1. Different person (different alpha frequency, irregular patterns)
        2. Poor electrode contact (high noise, weak signals)
        3. Movement/distraction (high beta, muscle artifacts, unstable)
        
        Characteristics:
        - Weak or shifted alpha peak (different frequency)
        - Higher noise floor: ~10-15 µV
        - More muscle artifacts and movement
        - Inconsistent amplitude and frequency
        - Elevated beta (stress/anxiety)
        
        NOTE: Frequencies are divided by 5 for better visualization (slower waves)
        """
        # Different frequency components (different person's brain) - 5x slower
        wrong_alpha_freq = self._alpha_freq + np.random.uniform(-2, 2)  # Shifted alpha
        
        delta = 3.0 * np.sin(2 * np.pi * (2.8 / 5.0) * t + np.random.rand() * 0.5)
        theta = 8.0 * np.sin(2 * np.pi * (6.5 / 5.0) * t + np.random.rand() * 0.5)
        alpha = 10.0 * np.sin(2 * np.pi * (wrong_alpha_freq / 5.0) * t + np.random.rand() * 0.5)  # Weak alpha
        beta = 15.0 * np.sin(2 * np.pi * (22 / 5.0) * t + np.random.rand() * 0.5)  # High beta (stress)
        gamma = 5.0 * np.sin(2 * np.pi * (38 / 5.0) * t + np.random.rand() * 0.5)
        
        # High noise (poor electrode contact or different person)
        pink_noise = self._generate_pink_noise() * 8.0  # Much higher noise
        white_noise = np.random.randn() * 5.0
        
        # Frequent artifacts (movement, poor contact)
        baseline_drift = self._generate_baseline_drift() * 2.0  # Worse contact
        eye_blink = self._generate_eye_blink(t) * 1.5  # More frequent/larger blinks
        muscle_artifact = self._generate_muscle_artifact(t) * 2.5  # More muscle tension
        
        # Random amplitude variations (unstable signal)
        instability = np.random.randn() * 3.0
        
        # Combine components (inconsistent, noisy)
        signal = (delta + 
                 theta + 
                 alpha +  # Weak, wrong frequency alpha
                 beta +   # High beta
                 gamma +
                 pink_noise +
                 white_noise +
                 baseline_drift +
                 eye_blink +
                 muscle_artifact +
                 instability)
        
        return signal
    
    def get_sample(self) -> float:
        """Get next sample based on current mode."""
        sample = (self.generate_authenticated(self._time) if self.mode == MOCK_AUTH_MODE
                  else self.generate_impostor(self._time))
        self._time += self._sample_interval
        return sample
    
    def get_samples(self, n: int) -> List[float]:
        """Get n samples."""
        return [self.get_sample() for _ in range(n)]
    
    def reset(self) -> None:
        """Reset time counter."""
        self._time = 0.0
    
    def get_signal_quality(self, samples: List[float]) -> dict:
        """
        Assess signal quality metrics.
        
        Returns:
            dict with 'rms', 'peak', 'quality' (good/fair/poor)
        """
        if not samples:
            return {"rms": 0.0, "peak": 0.0, "quality": "poor"}
        
        arr = np.array(samples)
        rms = float(np.sqrt(np.mean(arr ** 2)))
        peak = float(np.max(np.abs(arr)))
        
        # Quality assessment based on typical EEG ranges
        if peak > 100 or rms > 50:
            quality = "poor"  # Likely noise/artifact
        elif peak < 0.1 and rms < 0.05:
            quality = "poor"  # Signal too weak
        elif 0.5 <= rms <= 10 and peak <= 50:
            quality = "good"  # Normal EEG range
        else:
            quality = "fair"
        
        return {
            "rms": round(rms, 3),
            "peak": round(peak, 3),
            "quality": quality
        }


class SerialCollector:
    """Collects EEG data from ESP32 over serial connection with mock fallback."""

    def __init__(
        self,
        port: Optional[str],
        baud: int,
        window_size: int,
        step_size: int,
        logger: logging.Logger,
        fs: float = DEFAULT_FS,
        use_mock: bool = False,
        mock_mode: str = MOCK_AUTH_MODE,
    ):
        """
        Initialize serial collector with optional mock mode.
        
        Args:
            port: Serial port (None = auto-detect or use mock)
            baud: Baud rate
            window_size: Window size in samples
            step_size: Step size in samples
            logger: Logger instance
            fs: Sampling frequency
            use_mock: Force mock mode even if hardware available
            mock_mode: 'authenticated' or 'impostor' for mock data
        """
        self._validate_inputs(port, baud, window_size, step_size)
        self.port = port
        self.baud = baud
        self.window_size = window_size
        self.step_size = step_size
        self.logger = logger
        self.fs = fs
        self.ser: Optional[Any] = None  # serial.Serial when connected
        self.use_mock = use_mock
        self.mock_generator = MockDataGenerator(fs, mock_mode, logger)
        self.hardware_available = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._sample_count = 0
        self._quality_check_interval = 250  # Check every 250 samples (~1 sec at 250Hz)

    def _validate_inputs(
        self, port: Optional[str], baud: int, window_size: int, step_size: int
    ) -> None:
        """Validate collector parameters."""
        # Port can be None (will auto-detect or use mock)
        if baud <= 0:
            raise ValueError(f"Baud rate must be positive, got {baud}")
        if window_size <= 0:
            raise ValueError(f"Window size must be positive, got {window_size}")
        if step_size <= 0:
            raise ValueError(f"Step size must be positive, got {step_size}")
        if step_size > window_size:
            raise ValueError(
                f"Step size ({step_size}) cannot exceed window size ({window_size})"
            )
    
    def _auto_detect_port(self) -> Optional[str]:
        """Auto-detect ESP32 serial port."""
        if not HAS_SERIAL or serial is None:
            return None
        
        try:
            import serial.tools.list_ports
            esp32_hints = [
                "usbserial", "usbmodem", "ch340", "cp210",
                "wchusbserial", "ttyusb", "ttyacm", "esp32"
            ]
            
            for port in serial.tools.list_ports.comports():
                desc = (port.device + " " + (port.description or "") +
                        " " + (port.hwid or "")).lower()
                if any(hint in desc for hint in esp32_hints):
                    self.logger.info(f"Auto-detected ESP32 port: {port.device}")
                    return port.device
        except Exception as e:
            self.logger.debug(f"Port auto-detection failed: {e}")
        
        return None

    def connect(self) -> None:
        """
        Establish serial connection with automatic fallback to mock mode.
        
        Priority:
        1. Use mock mode if explicitly requested
        2. Try specified port
        3. Auto-detect ESP32 port
        4. Fall back to mock mode
        """
        # If mock mode is forced, skip hardware detection
        if self.use_mock:
            self.hardware_available = False
            self.logger.info("🎭 Using MOCK mode (forced)")
            self.logger.info(f"   Mode: {self.mock_generator.mode}")
            return
        
        # If pyserial not available, must use mock
        if not HAS_SERIAL or serial is None:
            self.use_mock = True
            self.hardware_available = False
            self.logger.warning("⚠️  pyserial not installed → Using MOCK mode")
            return
        
        # Try to connect to hardware
        target_port = self.port or self._auto_detect_port()
        
        if target_port:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.ser = serial.Serial(
                        target_port,
                        self.baud,
                        timeout=1.0,
                        write_timeout=1.0,
                    )
                    self.hardware_available = True
                    self.port = target_port
                    self.logger.info(f"✅ Connected to HARDWARE: {target_port} @ {self.baud} baud")
                    
                    # Flush startup banner
                    time.sleep(0.5)
                    self._flush_startup()
                    return
                    
                except serial.SerialException as e:
                    self.logger.warning(
                        f"Connection attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(2**attempt)
        
        # Fall back to mock mode
        self.use_mock = True
        self.hardware_available = False
        self.logger.warning("⚠️  No hardware detected → Using MOCK mode")
        self.logger.info(f"   Mode: {self.mock_generator.mode}")
    
    def _flush_startup(self) -> None:
        """Drain ESP32 startup banner lines."""
        if not self.ser:
            return
        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                line = self.ser.readline().decode("utf-8", errors="replace").strip()
                if line:
                    self.logger.debug(f"ESP32: {line}")
                    if "CORTEXKEY_READY" in line or "READY" in line:
                        break
            except Exception:
                break

    def disconnect(self) -> None:
        """Close serial connection if open."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("Serial connection closed")
        if self.use_mock:
            self.logger.info("Mock mode deactivated")
    
    def set_mock_mode(self, mode: str) -> None:
        """Change mock data generation mode (authenticated/impostor)."""
        self.mock_generator.set_mode(mode)
        # If connected to ESP32, also send command
        if self.hardware_available and self.ser and self.ser.is_open:
            cmd = "MOCK_AUTH\n" if mode == MOCK_AUTH_MODE else "MOCK_IMP\n"
            try:
                self.ser.write(cmd.encode())
                self.logger.info(f"Sent mode command to ESP32: {cmd.strip()}")
            except Exception as e:
                self.logger.warning(f"Failed to send mode command: {e}")

    def parse_line(self, line: str) -> Optional[Tuple[float, List[float]]]:
        """Parse a line from ESP32 into timestamp and samples."""
        line = line.strip()
        if not line:
            return None
        
        # Skip command/status lines
        if line.upper().startswith(("CMD:", "STATUS:", "ERROR:", "INFO:")):
            return None

        for prefix in ("DATA:", "DATA|"):
            if line.upper().startswith(prefix):
                line = line[len(prefix) :]
                break

        try:
            parts = [x.strip() for x in line.split(",") if x.strip()]
            if len(parts) < 2:
                return None
            timestamp = float(parts[0])
            samples = [float(x) for x in parts[1:]]
            return timestamp, samples
        except (ValueError, IndexError):
            return None
    
    def _read_mock_samples(self) -> Tuple[float, List[float]]:
        """Generate mock samples at correct timing."""
        timestamp = time.time() * 1000  # ms
        # Generate single sample (ESP32 sends 1 sample per line at 250 Hz)
        sample = self.mock_generator.get_sample()
        return timestamp, [sample]
    
    def _check_signal_quality(self, buffer_data: List[List[float]]) -> None:
        """Periodically check and log signal quality."""
        # Flatten buffer for quality check
        samples = [s[0] if isinstance(s, list) else s for s in buffer_data]
        quality_info = self.mock_generator.get_signal_quality(samples[-min(250, len(samples)):])
        
        mode_str = "🎭 MOCK" if self.use_mock else "🔌 HARDWARE"
        
        if quality_info["quality"] == "poor":
            self.logger.warning(
                f"{mode_str} Signal quality: {quality_info['quality'].upper()} "
                f"(RMS: {quality_info['rms']}, Peak: {quality_info['peak']})"
            )
        else:
            self.logger.debug(
                f"{mode_str} Signal quality: {quality_info['quality']} "
                f"(RMS: {quality_info['rms']}, Peak: {quality_info['peak']})"
            )

    def stream(
        self,
        processor: BrainwaveProcessor,
        output_file: Optional[Path] = None,
    ) -> None:
        """
        Stream EEG data (from hardware or mock), process windows, generate signatures.
        
        Seamlessly handles both real hardware and mock data modes.
        """
        if not self.use_mock and (not self.ser or not self.ser.is_open):
            raise ConnectionError("Not connected. Call connect() first.")

        buffer: deque[List[float]] = deque(maxlen=self.window_size)
        samples_since_last = 0
        out_handle = None
        signatures_generated = 0
        
        # Timing for mock mode (with drift correction)
        start_time = time.time()
        expected_sample_count = 0
        sample_interval = 1.0 / self.fs

        try:
            if output_file:
                out_handle = open(output_file, "a", encoding="utf-8")
                self.logger.info(f"Writing signatures to {output_file}")
            
            mode_str = "MOCK" if self.use_mock else "HARDWARE"
            self.logger.info(f"Streaming started ({mode_str} mode)")

            while True:
                # ============= DATA ACQUISITION =============
                if self.use_mock:
                    # Mock mode: generate data at correct sample rate with drift correction
                    expected_sample_count += 1
                    target_time = start_time + (expected_sample_count * sample_interval)
                    current_time = time.time()
                    
                    if current_time < target_time:
                        # Sleep until next sample is due
                        sleep_time = target_time - current_time
                        if sleep_time > 0.001:  # Only sleep if worthwhile
                            time.sleep(sleep_time)
                        else:
                            time.sleep(0.0001)  # Minimal yield
                        continue
                    
                    timestamp, samples = self._read_mock_samples()
                    self._sample_count += 1
                        
                else:
                    # Hardware mode: read from serial
                    if not self.ser.is_open:
                        self._reconnect_attempts += 1
                        if self._reconnect_attempts >= self._max_reconnect_attempts:
                            self.logger.error(
                                f"Max reconnection attempts ({self._max_reconnect_attempts}) reached. "
                                "Switching to mock mode."
                            )
                            self.use_mock = True
                            self.hardware_available = False
                            start_time = time.time()  # Reset mock timing
                            expected_sample_count = 0
                            continue
                        
                        self.logger.warning(
                            f"Serial port closed. Reconnect attempt {self._reconnect_attempts}/"
                            f"{self._max_reconnect_attempts}..."
                        )
                        time.sleep(min(2 ** self._reconnect_attempts, 30))  # Exponential backoff, max 30s
                        self.connect()
                        continue

                    try:
                        line = self.ser.readline()
                        self._reconnect_attempts = 0  # Reset on successful read
                    except serial.SerialException as e:
                        self.logger.error(f"Read error: {e}")
                        self.logger.warning("Attempting reconnect...")
                        self.connect()
                        continue

                    if not line:
                        continue

                    parsed = self.parse_line(line.decode("ascii", errors="ignore"))
                    if parsed is None:
                        continue
                    
                    timestamp, samples = parsed
                    self._sample_count += 1
                
                # ============= BUFFER & PROCESS =============
                buffer.append(samples)
                samples_since_last += 1
                
                # Periodic signal quality check
                if self._sample_count % self._quality_check_interval == 0:
                    self._check_signal_quality(list(buffer))

                ready = (
                    len(buffer) == self.window_size
                    and samples_since_last >= self.step_size
                )

                if ready:
                    try:
                        data = np.array(buffer)
                        features = processor.compute_features(data)
                        signature = processor.encrypt_signature(features)
                        signatures_generated += 1

                        ts = int(time.time())
                        mode_indicator = "🎭" if self.use_mock else "🔌"
                        self.logger.info(
                            f"{mode_indicator} Signature #{signatures_generated}: {signature[:32]}..."
                        )
                        print(f"[{ts}] {mode_indicator} {signature}")

                        if out_handle:
                            out_handle.write(f"{ts},{signature},{mode_str}\n")
                            out_handle.flush()

                        samples_since_last = 0
                        
                    except Exception as e:
                        self.logger.error(f"Error processing window: {e}")
                        # Continue streaming even if one window fails
                        samples_since_last = 0
                        continue

        except KeyboardInterrupt:
            self.logger.info("\n👋 Streaming stopped by user")
        finally:
            # Graceful shutdown
            mode_str = "MOCK" if self.use_mock else "HARDWARE"
            self.logger.info(
                f"\n📊 Session Summary ({mode_str} mode):\n"
                f"   Samples processed: {self._sample_count}\n"
                f"   Signatures generated: {signatures_generated}\n"
                f"   Duration: {time.time() - start_time:.1f}s"
            )
            
            self.disconnect()
            if out_handle:
                out_handle.close()
                self.logger.info(f"   Output saved to: {output_file}")


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments."""
    if args.window <= 0:
        raise argparse.ArgumentTypeError(
            f"--window must be positive, got {args.window}"
        )
    if args.step <= 0:
        raise argparse.ArgumentTypeError(f"--step must be positive, got {args.step}")
    if args.step > args.window:
        raise argparse.ArgumentTypeError(
            f"--step ({args.step}) cannot exceed --window ({args.window})"
        )
    if args.fs <= 0:
        raise argparse.ArgumentTypeError(f"--fs must be positive, got {args.fs}")
    if not args.passphrase or not args.passphrase.strip():
        raise argparse.ArgumentTypeError("--passphrase cannot be empty")
    if args.mock_mode and args.mock_mode not in [MOCK_AUTH_MODE, MOCK_IMPOSTOR_MODE]:
        raise argparse.ArgumentTypeError(
            f"--mock-mode must be '{MOCK_AUTH_MODE}' or '{MOCK_IMPOSTOR_MODE}'"
        )


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="CortexKey Brainwave Authenticator - Collect EEG from ESP32 "
        "(or mock data), compute features, generate encrypted signatures. "
        "Automatically falls back to mock mode if hardware is unavailable.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Examples:\n"
        "  # Try hardware (auto-detect), fall back to mock if unavailable:\n"
        "  %(prog)s --passphrase mykey\n\n"
        "  # Explicit port:\n"
        "  %(prog)s --port /dev/ttyUSB0 --passphrase mykey\n\n"
        "  # Force mock mode (authenticated):\n"
        "  %(prog)s --mock --passphrase mykey\n\n"
        "  # Force mock mode (impostor):\n"
        "  %(prog)s --mock --mock-mode impostor --passphrase mykey\n",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port (e.g., COM3, /dev/ttyUSB0). If omitted, auto-detects or uses mock.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Serial baud rate",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=DEFAULT_WINDOW,
        help="Window size in samples for feature extraction",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=DEFAULT_STEP,
        help="Step size in samples for sliding window",
    )
    parser.add_argument(
        "--fs",
        type=float,
        default=DEFAULT_FS,
        help="Sampling frequency in Hz",
    )
    parser.add_argument(
        "--passphrase",
        required=True,
        help="Passphrase for key derivation",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="File to append signatures (optional)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Directory for log files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging to console",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force mock mode (ignore hardware even if available)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Auto-stop after N seconds (optional, for testing)",
    )
    parser.add_argument(
        "--mock-mode",
        default=MOCK_AUTH_MODE,
        choices=[MOCK_AUTH_MODE, MOCK_IMPOSTOR_MODE],
        help="Mock data mode: 'authenticated' (high confidence) or 'impostor' (low confidence)",
    )
    return parser


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        validate_args(args)
    except argparse.ArgumentTypeError as e:
        parser.print_usage()
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    logger = setup_logging(args.log_dir)
    
    # Set verbose level
    if args.verbose:
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)
    
    # Print banner
    print("\n" + "=" * 70)
    print("  🧠 CortexKey Brainwave Authenticator")
    print("=" * 70)

    # Check dependencies (warn but don't fail - mock mode can still work)
    if not HAS_SERIAL or serial is None:
        logger.warning("⚠️  pyserial not installed. Hardware mode unavailable.")
        logger.warning("   Run: pip install pyserial")
        args.mock = True  # Force mock mode
    if signal is None:
        logger.error("❌ scipy not installed. Cannot continue.")
        logger.error("   Run: pip install scipy")
        sys.exit(1)

    try:
        processor = BrainwaveProcessor(
            fs=args.fs,
            passphrase=args.passphrase,
        )
        
        collector = SerialCollector(
            port=args.port,
            baud=args.baud,
            window_size=args.window,
            step_size=args.step,
            logger=logger,
            fs=args.fs,
            use_mock=args.mock,
            mock_mode=args.mock_mode,
        )
        
        collector.connect()
        
        # Print status
        print()
        if collector.hardware_available:
            print(f"✅ HARDWARE MODE: Connected to {collector.port}")
        else:
            print(f"🎭 MOCK MODE: Using synthetic {args.mock_mode} EEG data")
        print(f"📊 Window: {args.window} samples, Step: {args.step}, Fs: {args.fs} Hz")
        if args.output:
            print(f"💾 Output: {args.output}")
        print("\n🚀 Streaming started... (Press Ctrl+C to stop)\n")
        print("-" * 70)
        
        # Auto-stop for testing
        if args.duration:
            import threading
            stop_event = threading.Event()
            
            def auto_stop():
                stop_event.wait(args.duration)
                logger.info(f"\n⏰ Auto-stopping after {args.duration} seconds")
                import signal as sig
                sig.raise_signal(sig.SIGINT)
            
            threading.Thread(target=auto_stop, daemon=True).start()
        
        collector.stream(processor, args.output)

    except KeyboardInterrupt:
        logger.info("\n👋 Interrupted by user")
        print("\n" + "=" * 70)
        print("  Session ended. Thanks for using CortexKey!")
        print("=" * 70 + "\n")
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
