# 🧠 CortexKey Brainwave Authenticator - Hybrid Mode

## Overview

This enhanced version of `brainwave_auth.py` supports **both real hardware and mock data** with automatic fallback, making it perfect for development, demos, and production use.

## 🌟 Key Features

### ✅ **Automatic Hardware Detection**
- Tries to connect to ESP32 hardware
- Auto-detects serial ports (CH340, CP210x, etc.)
- Falls back to mock mode if hardware unavailable
- **Zero configuration needed for demos**

### 🎭 **Mock Data Modes**
1. **Authenticated User** - Strong alpha/beta waves → High confidence signatures
2. **Impostor** - Random noise → Low confidence signatures

### 🔌 **Real Hardware Support**
- BioAmp EXG Pill + ESP32
- Serial communication at 115200 baud
- Identical processing pipeline as mock mode
- Seamless transition when hardware available

## 📦 Installation

```bash
# Core dependencies
pip install numpy scipy cryptography

# Hardware support (optional - mock mode works without this)
pip install pyserial
```

## 🚀 Usage Examples

### 1. **Demo Mode (No Hardware Required)**

```bash
# Authenticated user pattern
python brainwave_auth.py --mock --passphrase demo2024

# Impostor pattern (low confidence)
python brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024
```

### 2. **Auto-Detect Hardware (Try Real, Fall Back to Mock)**

```bash
# Will use hardware if available, mock if not
python brainwave_auth.py --passphrase mykey
```

### 3. **Explicit Port (Real Hardware)**

```bash
# macOS/Linux
python brainwave_auth.py --port /dev/ttyUSB0 --passphrase mykey

# Windows
python brainwave_auth.py --port COM3 --passphrase mykey
```

### 4. **Save Signatures to File**

```bash
python brainwave_auth.py --mock --passphrase demo --output signatures.csv
```

### 5. **Custom Parameters**

```bash
python brainwave_auth.py \
    --mock \
    --passphrase mykey \
    --window 512 \
    --step 128 \
    --fs 256 \
    --output results.csv
```

## 📊 Output Format

### Console Output
```
======================================================================
  🧠 CortexKey Brainwave Authenticator
======================================================================

🎭 MOCK MODE: Using synthetic authenticated EEG data
📊 Window: 512 samples, Step: 128, Fs: 256.0 Hz

🚀 Streaming started... (Press Ctrl+C to stop)

----------------------------------------------------------------------
[1708534562] 🎭 aGt2cFl1MnJ0M3RqN3RqN3RqN3RqN3Rq...
[1708534564] 🎭 bHp3cFp1M3J1M3VrN3VrN3VrN3VrN3Vr...
```

### CSV Output (if --output specified)
```
timestamp,signature,mode
1708534562,aGt2cFl1MnJ0M3RqN3RqN3RqN3RqN3Rq...,MOCK
1708534564,bHp3cFp1M3J1M3VrN3VrN3VrN3VrN3Vr...,MOCK
```

## 🎯 Mode Indicators

- **🎭** = Mock mode (synthetic data)
- **🔌** = Hardware mode (real BioAmp EXG)

## 🔬 How It Works

### Mock Data Generation

**Authenticated User:**
```python
# Strong 10Hz alpha (relaxed state)
alpha = 2.5 * sin(2π * 10 * t)
# Moderate 20Hz beta (cognitive activity)  
beta = 1.2 * sin(2π * 20 * t)
# Low noise
noise = 0.3 * random()
```

**Impostor:**
```python
# High noise
noise = 1.5 * random()
# Weak, inconsistent signals
# Random muscle artifacts
```

### Signal Processing Pipeline

```
Raw EEG (256 Hz)
    ↓
50 Hz Notch Filter (powerline noise)
    ↓
5-30 Hz Bandpass (alpha + beta bands)
    ↓
Welch PSD Estimation
    ↓
Band Power Extraction (delta/theta/alpha/beta/gamma)
    ↓
AES-GCM Encryption with HKDF-SHA256
    ↓
Base64 Signature
```

## 🛠️ Hardware Setup (When Available)

### Wiring
```
Forehead Electrode (Fp1) ──┐
Forehead Electrode (Fp2) ──┤──> BioAmp EXG Pill ──> ESP32 GPIO34
Reference (Mastoid/Ear) ───┘
                                        ↓
                                    USB Serial
                                        ↓
                                    Computer
```

### ESP32 Firmware
Upload `firmware/esp32_neural_auth.ino` with:
```cpp
#define USE_MOCK_DATA false  // For real sensor
```

### Connect
```bash
# Auto-detect and connect
python brainwave_auth.py --passphrase mykey

# Or specify port
python brainwave_auth.py --port /dev/ttyUSB0 --passphrase mykey
```

## 🔐 Security Features

- **AES-256-GCM** encryption
- **HKDF-SHA256** key derivation
- **Unique salt** per signature (16 bytes)
- **Nonce** for replay protection (12 bytes)
- **Authenticated encryption** (tamper-proof)

## 📈 Performance

- **Sample Rate:** 256 Hz (configurable)
- **Window Size:** 512 samples (~2 seconds)
- **Step Size:** 128 samples (~0.5 second stride)
- **Processing Time:** <10ms per window (Python)

## 🐛 Troubleshooting

### "pyserial not installed"
```bash
pip install pyserial
```
*(Mock mode still works without this)*

### "No hardware detected"
- Check USB connection
- Verify ESP32 is powered
- Try explicit port: `--port /dev/ttyUSB0`
- Use `--mock` flag for demo mode

### Port Permission Denied (Linux)
```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

### Windows COM Port Issues
- Check Device Manager for port number
- Install CH340 drivers if using clone ESP32

## 🎬 Demo Script

Perfect for hackathon presentations:

```bash
# Terminal 1: Authenticated user
python brainwave_auth.py --mock --passphrase demo2024

# Terminal 2: Impostor (compare signatures)
python brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024
```

Watch the encrypted signatures - authenticated user produces consistent patterns, impostor shows noisy variations.

## 🔄 Migration from Old Version

**Old (hardware required):**
```bash
python brainwave_auth.py --port /dev/ttyUSB0 --passphrase key
```

**New (works without hardware):**
```bash
python brainwave_auth.py --passphrase key
# Tries hardware first, falls back to mock
```

**Force mock (for demos):**
```bash
python brainwave_auth.py --mock --passphrase key
```

## 🏆 Best Practices

1. **Development:** Use `--mock` for fast iteration
2. **Testing:** Use `--mock-mode impostor` to test rejection
3. **Demo:** Use `--mock` with live switching between modes
4. **Production:** Let auto-detect handle hardware availability
5. **Logging:** Check `logs/brainwave_auth.log` for details

## 📝 Command Reference

```
--port PORT           Serial port (auto-detect if omitted)
--baud BAUD           Baud rate (default: 115200)
--window SIZE         Window size in samples (default: 512)
--step SIZE           Step size in samples (default: 128)
--fs FREQ             Sample frequency Hz (default: 256.0)
--passphrase PASS     Encryption passphrase (required)
--output FILE         CSV output file (optional)
--log-dir DIR         Log directory (default: logs/)
--mock                Force mock mode
--mock-mode MODE      'authenticated' or 'impostor' (default: authenticated)
--verbose             Enable debug logging
```

## 🌐 Integration with Main System

This script can work alongside the Flask backend:

- **Flask Backend:** Real-time web dashboard with ML classification
- **This Script:** Command-line signature generation with encryption
- **Shared Pipeline:** Both use identical signal processing

Use this script for:
- Raw signature generation
- Batch processing
- Command-line tools
- Enrollment data collection

Use Flask backend for:
- Real-time visualization
- Web-based authentication
- Dashboard interface
- ML-based classification

## 📚 Additional Resources

- Main README: `../README.md`
- Architecture Analysis: `../ARCHITECTURE_ANALYSIS.md`
- ESP32 Firmware: `../firmware/esp32_neural_auth.ino`
- Flask Backend: `../backend/app.py`

---

**Ready for your hackathon demo!** 🚀

Run `python brainwave_auth.py --mock --passphrase demo2024` and watch the signatures flow!
