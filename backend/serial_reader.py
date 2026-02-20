"""
CortexKey - Serial Reader

Connects to the ESP32 over a serial port, reads the CSV stream,
and buffers 2-second windows (500 samples @ 250 Hz).

Also exposes a *mock serial* mode that generates data in software
so the backend can run without any hardware attached.
"""

import threading
import time
import collections
import numpy as np

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

from eeg_pipeline import generate_auth_user, generate_impostor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FS = 250
WINDOW_SIZE = 500          # 2 seconds
BAUD = 115200


class SerialReader:
    """
    Reads EEG samples from the ESP32 serial port (or generates mock data).
    Thread-safe ring buffer provides the latest 2-second window on demand.
    """

    def __init__(self):
        self._buffer = collections.deque(maxlen=WINDOW_SIZE)
        self._raw_buffer = collections.deque(maxlen=WINDOW_SIZE)
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._serial = None
        self._mock_mode = "auth"      # "auth" | "impostor"
        self._use_mock = True
        self._connected = False
        self._port = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def mock_mode(self) -> str:
        return self._mock_mode

    def list_ports(self):
        """Return available serial ports."""
        if not HAS_SERIAL:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port=None):  # type: Optional[str]
        """Open a serial connection (or fall back to mock mode)."""
        if port and HAS_SERIAL:
            try:
                self._serial = serial.Serial(port, BAUD, timeout=1)
                self._use_mock = False
                self._port = port
                self._connected = True
                print(f"[serial] Connected to {port}")
            except Exception as e:
                print(f"[serial] Cannot open {port}: {e}  → using mock mode")
                self._use_mock = True
                self._connected = True
        else:
            self._use_mock = True
            self._connected = True
            print("[serial] Using mock data (no hardware)")

    def start(self):
        """Begin reading (in a background thread)."""
        if self._thread and self._thread.is_alive():
            return
        if not self._connected:
            self.connect()
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop reading."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
        self._connected = False

    def set_mock_mode(self, mode: str):
        """Switch mock data between 'auth' and 'impostor'."""
        self._mock_mode = mode
        # Also tell the ESP32 if connected over serial
        if self._serial and self._serial.is_open:
            cmd = "MOCK_AUTH\n" if mode == "auth" else "MOCK_IMP\n"
            try:
                self._serial.write(cmd.encode())
            except Exception:
                pass

    def send_command(self, cmd: str):
        """Send an arbitrary command to the ESP32."""
        if self._serial and self._serial.is_open:
            try:
                self._serial.write((cmd.strip() + "\n").encode())
            except Exception:
                pass

    def get_window(self):  # -> Optional[np.ndarray]
        """Return the latest 2-second window (500 samples), or None."""
        with self._lock:
            if len(self._buffer) < WINDOW_SIZE:
                return None
            return np.array(list(self._buffer), dtype=np.float64)

    def get_latest(self, n: int = 80) -> list:
        """Return the last *n* samples as a plain list (for the oscilloscope)."""
        with self._lock:
            items = list(self._buffer)
            return items[-n:] if len(items) >= n else items

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_loop(self):
        """Background loop: read serial or generate mock data."""
        if self._use_mock:
            self._mock_loop()
        else:
            self._serial_loop()

    def _serial_loop(self):
        """Read CSV lines from the ESP32."""
        while self._running:
            try:
                line = self._serial.readline().decode("utf-8", errors="replace").strip()
                if not line or line.startswith("CMD:"):
                    continue
                parts = line.split(",")
                if len(parts) >= 3:
                    mv = float(parts[2])
                    with self._lock:
                        self._buffer.append(mv)
            except Exception:
                time.sleep(0.01)

    def _mock_loop(self):
        """Generate synthetic data at 250 Hz."""
        sample_interval = 1.0 / FS
        idx = 0
        while self._running:
            t = idx / FS
            if self._mock_mode == "auth":
                # Strong alpha + beta
                sample = (
                    2.5 * np.sin(2 * np.pi * 10 * t)
                    + 1.2 * np.sin(2 * np.pi * 20 * t)
                    + 0.6 * np.sin(2 * np.pi * 6 * t)
                    + 0.3 * np.random.randn()
                )
            else:
                sample = 1.5 * np.random.randn()

            with self._lock:
                self._buffer.append(float(sample))

            idx += 1
            time.sleep(sample_interval)


# Singleton
reader = SerialReader()
