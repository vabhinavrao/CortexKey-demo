"""
CortexKey - Serial Reader

Connects to the ESP32 over a serial port, reads the CSV stream,
and buffers 2-second windows (500 samples @ 250 Hz).

Also exposes a *mock serial* mode that generates data in software
so the backend can run without any hardware attached.

When the BioAmp EXG Pill arrives:
  1. Plug ESP32 via USB.
  2. Call reader.connect() — it auto-detects the port.
  3. OR POST /api/serial/connect {"port": "/dev/tty.usbserial-XXX"}
  4. Everything else (filters, ML, frontend) stays identical.
"""

import os
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FS = 250
WINDOW_SIZE = 500          # 2 seconds
BAUD = 115200

# Env var override: CORTEXKEY_PORT=/dev/ttys003  python backend/app.py
_ENV_PORT = os.environ.get("CORTEXKEY_PORT")

# Keywords that identify an ESP32 / CH340 / CP210x serial port
_ESP32_PORT_HINTS = [
    "usbserial", "usbmodem", "ch340", "cp210",
    "wchusbserial", "ttyusb", "ttyacm",
]


def _find_esp32_port():
    """
    Scan available serial ports and return the first one that looks like
    an ESP32 (CH340 or CP210x USB-serial adaptor).
    Returns None if nothing is found.
    """
    if not HAS_SERIAL:
        return None
    for port in serial.tools.list_ports.comports():
        desc = (port.device + " " + (port.description or "") +
                " " + (port.hwid or "")).lower()
        if any(hint in desc for hint in _ESP32_PORT_HINTS):
            return port.device
    return None


class SerialReader:
    """
    Reads EEG samples from the ESP32 serial port (or generates mock data).
    Thread-safe ring buffer provides the latest 2-second window on demand.
    """

    def __init__(self):
        self._buffer = collections.deque(maxlen=WINDOW_SIZE)
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._serial = None
        self._mock_mode = "auth"      # "auth" | "impostor"
        self._use_mock = True
        self._connected = False
        self._port = None
        self._hardware_mode = False   # True when reading from real sensor
        # Adaptive gain: track recent signal range for auto-scaling
        self._signal_min = -5.0
        self._signal_max = 5.0
        self._gain_samples = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def mock_mode(self) -> str:
        return "hardware" if self._hardware_mode else self._mock_mode

    @property
    def hardware_mode(self) -> bool:
        """True when reading from real BioAmp EXG Pill sensor."""
        return self._hardware_mode

    def list_ports(self):
        """Return available serial ports with descriptions."""
        if not HAS_SERIAL:
            return []
        return [
            {"device": p.device, "description": p.description or ""}
            for p in serial.tools.list_ports.comports()
        ]

    def connect(self, port=None):
        """
        Open a serial connection to the ESP32.

        Priority:
          1. Explicit port argument
          2. Auto-detected ESP32 port (CH340 / CP210x)
          3. Fall back to mock mode
        """
        target_port = port or _ENV_PORT or _find_esp32_port()

        if target_port and HAS_SERIAL:
            try:
                self._serial = serial.Serial(target_port, BAUD, timeout=1)
                self._use_mock = False
                self._hardware_mode = True
                self._port = target_port
                self._connected = True
                print(f"[serial] Connected to ESP32 on {target_port}")
                # Wait for ESP32 startup banner
                time.sleep(0.5)
                self._flush_startup()
                return
            except Exception as e:
                print(f"[serial] Cannot open {target_port}: {e}  → falling back to mock")
                self._hardware_mode = False

        # Mock fallback
        self._use_mock = True
        self._hardware_mode = False
        self._connected = True
        print("[serial] Using software mock data (no hardware detected)")

    def _flush_startup(self):
        """Drain any ESP32 startup banner lines (CMD:... lines)."""
        if not self._serial:
            return
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                raw = self._serial.readline()
                if not raw:
                    time.sleep(0.05)
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    print(f"[serial] ESP32 → {line}")
                if "CORTEXKEY_READY" in line:
                    break
            except Exception:
                break
        # Kick the ESP32 into continuous streaming mode immediately
        try:
            self._serial.write(b"START\n")
        except Exception:
            pass

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
        self._hardware_mode = False

    def set_mock_mode(self, mode: str):
        """
        Switch mock data between 'auth' and 'impostor'.
        Also relays the command to the ESP32 if connected over serial.
        Flushes the signal buffer so stale data doesn't pollute the next scan.
        """
        self._mock_mode = mode
        # Flush buffer so old signal doesn't bleed into next scan
        with self._lock:
            self._buffer.clear()
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

    def get_window(self):
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

    def get_signal_stats(self) -> dict:
        """Return live signal statistics — useful for electrode contact check."""
        with self._lock:
            if not self._buffer:
                return {"min": 0, "max": 0, "rms": 0, "samples": 0}
            data = np.array(list(self._buffer))
        return {
            "min": round(float(data.min()), 3),
            "max": round(float(data.max()), 3),
            "rms": round(float(np.sqrt(np.mean(data ** 2))), 3),
            "samples": len(data),
        }

    def flush_buffer(self):
        """Clear the sample ring buffer (call before each new scan)."""
        with self._lock:
            self._buffer.clear()

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
        """
        Read CSV lines from the ESP32.
        Format: timestamp_ms,raw_adc,millivolts\\n
        Handles disconnects and tries to reconnect automatically.
        """
        consecutive_errors = 0
        while self._running:
            try:
                raw_line = self._serial.readline()
                if not raw_line:
                    # PTY / serial can return empty on no-data; small sleep
                    time.sleep(0.004)
                    consecutive_errors += 1
                    if consecutive_errors > 500:   # ~2s of silence
                        print("[serial] Too many empty reads — reconnecting…")
                        self._reconnect()
                        consecutive_errors = 0
                    continue
                consecutive_errors = 0

                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith("CMD:"):
                    continue

                parts = line.split(",")
                if len(parts) >= 3:
                    mv = float(parts[2])
                    # Adaptive gain: keep track of the real signal range
                    self._update_gain(mv)
                    with self._lock:
                        self._buffer.append(mv)

            except serial.SerialException:
                print("[serial] Disconnected — retrying in 2s…")
                time.sleep(2)
                self._reconnect()
            except (ValueError, UnicodeDecodeError):
                pass  # malformed line — skip it
            except Exception as e:
                print(f"[serial] Unexpected error: {e}")
                time.sleep(0.01)

    def _reconnect(self):
        """Try to re-open the serial port after a disconnect."""
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
        time.sleep(1)
        try:
            self._serial = serial.Serial(self._port, BAUD, timeout=1)
            time.sleep(0.5)
            self._flush_startup()
            print(f"[serial] Reconnected to {self._port}")
        except Exception as e:
            print(f"[serial] Reconnect failed: {e} — falling back to mock")
            self._use_mock = True
            self._hardware_mode = False

    def _update_gain(self, value: float):
        """Track the running min/max of the real signal for auto-gain."""
        self._gain_samples += 1
        if value < self._signal_min:
            self._signal_min = value
        if value > self._signal_max:
            self._signal_max = value

    def _mock_loop(self):
        """Generate synthetic data at 250 Hz."""
        sample_interval = 1.0 / FS
        idx = 0
        while self._running:
            t = idx / FS
            if self._mock_mode == "auth":
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
