#!/usr/bin/env python3
"""
CortexKey — ESP32 Serial Simulator
====================================
Emulates the exact serial output of the ESP32 firmware (esp32_neural_auth.ino).

Output format:  timestamp_ms,raw_adc,millivolts
Commands in:    MOCK_AUTH | MOCK_IMP | START_AUTH | START | STOP | STATUS | PING

Usage:
    python tools/esp32_simulator.py                   # auto pty mode (Mac/Linux)
    python tools/esp32_simulator.py --port /dev/ttyS1 # specific port

The simulator prints the PTY slave path so you can paste it into
POST /api/serial/connect  or set it as CORTEXKEY_PORT env var.
"""

import os
import sys
import math
import time
import random
import threading
import argparse

# ── Config ─────────────────────────────────────────────────────────────────
SAMPLE_RATE = 250          # Hz
SAMPLE_INTERVAL = 1.0 / SAMPLE_RATE
AUTH_SCAN_SAMPLES = 1500   # 6 seconds @ 250 Hz


# ── Signal generators (mirror the firmware exactly) ─────────────────────────

def gen_auth(t: float) -> float:
    """Strong alpha (10 Hz) + beta (20 Hz) — authenticated user."""
    alpha      = 2.5  * math.sin(2 * math.pi * 10 * t)
    beta       = 1.2  * math.sin(2 * math.pi * 20 * t)
    theta      = 0.6  * math.sin(2 * math.pi * 6  * t)
    noise      = 0.3  * (random.random() * 2 - 1)
    modulation = 1.0  + 0.1 * math.sin(2 * math.pi * 0.3 * t)
    return (alpha + beta + theta) * modulation + noise


def gen_impostor(t: float) -> float:
    """Noisy, incoherent signal — impostor."""
    noise       = 1.5 * (random.random() * 2 - 1)
    weak_signal = 0.3 * math.sin(2 * math.pi * 7.3 * t + random.random() * 6.28)
    muscle      = 2.0 * (random.random() * 2 - 1) if random.random() < 0.05 else 0.0
    return noise + weak_signal + muscle


def mv_to_adc(mv: float) -> int:
    """Convert ±mV back to a 12-bit ADC value (mirrors firmware logic)."""
    raw = int((mv + 3.3) / 6.6 * 4095.0)
    return max(0, min(4095, raw))


# ── Simulator core ──────────────────────────────────────────────────────────

class ESP32Simulator:
    def __init__(self, write_fn, read_fn):
        self._write   = write_fn    # callable(bytes)
        self._read    = read_fn     # callable() -> bytes (non-blocking)
        self._mode    = "idle"      # idle | streaming | auth
        self._mock    = "auth"      # auth | impostor
        self._running = False
        self._count   = 0
        self._start   = 0.0

    def emit(self, text: str):
        self._write((text + "\r\n").encode())

    # ── startup banner ──────────────────────────────────────────────────────
    def send_banner(self):
        time.sleep(0.3)
        self.emit("CMD:CORTEXKEY_READY")
        self.emit("CMD:VERSION:1.0")
        self.emit("CMD:MODE:MOCK")
        self.emit("CMD:COMMANDS:START_AUTH,MOCK_AUTH,MOCK_IMP,STOP,START,STATUS,PING")
        # Auto-start streaming so data flows immediately on connect
        self._mode  = "streaming"
        self._count = 0
        self._start = time.time()

    # ── command handling ─────────────────────────────────────────────────────
    def handle(self, cmd: str):
        cmd = cmd.strip().upper()
        if cmd == "START_AUTH":
            self._mode  = "auth"
            self._count = 0
            self._start = time.time()
            self.emit("CMD:AUTH_STARTED")
        elif cmd == "START":
            self._mode  = "streaming"
            self._count = 0
            self._start = time.time()
            self.emit("CMD:STREAMING_STARTED")
        elif cmd == "STOP":
            self._mode = "idle"
            self.emit("CMD:STOPPED")
        elif cmd == "MOCK_AUTH":
            self._mock = "auth"
            self.emit("CMD:MOCK_AUTH_SET")
        elif cmd == "MOCK_IMP":
            self._mock = "impostor"
            self.emit("CMD:MOCK_IMP_SET")
        elif cmd in ("BTN_A", "BTN_A_PRESS"):
            # GPIO18 — User A (enrolled) pressed
            self._mock  = "auth"
            self._mode  = "auth"
            self._count = 0
            self._start = time.time()
            self.emit("CMD:BTN_A_PRESSED")
            self.emit("CMD:AUTH_STARTED")
        elif cmd in ("BTN_B", "BTN_B_PRESS"):
            # GPIO19 — User B (impostor) pressed
            self._mock  = "impostor"
            self._mode  = "auth"
            self._count = 0
            self._start = time.time()
            self.emit("CMD:BTN_B_PRESSED")
            self.emit("CMD:AUTH_STARTED")
        elif cmd == "STATUS":
            mode_str = {"idle": "IDLE", "streaming": "STREAMING", "auth": "AUTH"}[self._mode]
            mock_str = "AUTH" if self._mock == "auth" else "IMP"
            self.emit(f"CMD:STATUS:{mode_str},MOCK:{mock_str}")
        elif cmd == "PING":
            self.emit("CMD:PONG")

    # ── main loop ────────────────────────────────────────────────────────────
    def run(self):
        self._running = True
        self.send_banner()

        buf = b""
        next_sample_time = time.perf_counter()

        while self._running:
            now = time.perf_counter()

            # ── read incoming commands ──────────────────────────────────────
            try:
                chunk = self._read()
                if chunk:
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        self.handle(line.decode("utf-8", errors="replace"))
            except Exception:
                pass

            # ── emit sample ────────────────────────────────────────────────
            if self._mode != "idle" and now >= next_sample_time:
                t  = self._count / SAMPLE_RATE
                ts = int((time.time() - self._start) * 1000)

                if self._mock == "auth":
                    mv = gen_auth(t)
                else:
                    mv = gen_impostor(t)

                adc = mv_to_adc(mv)
                self.emit(f"{ts},{adc},{mv:.4f}")
                self._count += 1
                next_sample_time += SAMPLE_INTERVAL

                # AUTH mode: auto-stop after 1500 samples then go back to streaming
                if self._mode == "auth" and self._count >= AUTH_SCAN_SAMPLES:
                    self._mode = "streaming"   # keep streaming, don't go idle
                    self.emit("CMD:AUTH_SCAN_COMPLETE")
            else:
                time.sleep(0.0005)   # ~0.5 ms idle sleep

    def stop(self):
        self._running = False


# ── PTY transport (Mac / Linux) ─────────────────────────────────────────────

def run_pty():
    import pty, tty, termios, fcntl

    master_fd, slave_fd = pty.openpty()

    # Make master non-blocking for reads
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    slave_path = os.ttyname(slave_fd)
    print(f"\n{'='*56}")
    print(f"  ESP32 Simulator — PTY mode")
    print(f"  Slave port : {slave_path}")
    print(f"  Baud rate  : 115200 (irrelevant for PTY)")
    print(f"")
    print(f"  Connect backend:")
    print(f"    export CORTEXKEY_PORT={slave_path}")
    print(f"    python backend/app.py")
    print(f"")
    print(f"  Or via API after backend starts:")
    print(f'    curl -X POST http://localhost:5001/api/serial/connect \\')
    print(f'         -H "Content-Type: application/json" \\')
    print(f'         -d \'{{"port":"{slave_path}"}}\'')
    print(f"{'='*56}\n")

    def write_fn(data: bytes):
        try:
            os.write(master_fd, data)
        except OSError:
            pass

    def read_fn() -> bytes:
        try:
            return os.read(master_fd, 256)
        except BlockingIOError:
            return b""
        except OSError:
            return b""

    sim = ESP32Simulator(write_fn, read_fn)
    try:
        sim.run()
    except KeyboardInterrupt:
        print("\n[simulator] Stopped.")
    finally:
        sim.stop()
        os.close(master_fd)
        os.close(slave_fd)


# ── Real serial port transport ───────────────────────────────────────────────

def run_serial(port: str):
    import serial as _serial
    s = _serial.Serial(port, 115200, timeout=0)

    print(f"\n{'='*56}")
    print(f"  ESP32 Simulator — Serial mode")
    print(f"  Port: {port}  Baud: 115200")
    print(f"{'='*56}\n")

    def write_fn(data: bytes):
        try:
            s.write(data)
        except Exception:
            pass

    def read_fn() -> bytes:
        try:
            return s.read(s.in_waiting or 1)
        except Exception:
            return b""

    sim = ESP32Simulator(write_fn, read_fn)
    try:
        sim.run()
    except KeyboardInterrupt:
        print("\n[simulator] Stopped.")
    finally:
        sim.stop()
        s.close()


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CortexKey ESP32 Serial Simulator")
    parser.add_argument("--port", default=None,
                        help="Serial port to use (default: auto PTY)")
    args = parser.parse_args()

    if args.port:
        run_serial(args.port)
    else:
        run_pty()
