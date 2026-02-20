# 🚀 CortexKey Quick Start Guide

## Choose Your Demo Mode

### 🎯 Option 1: Web Dashboard (Recommended for Demos)

**Best for:** Live visualization, hackathon presentations

```bash
cd cortexkey
pip install -r requirements.txt
python backend/app.py
```

Open **http://localhost:5001** in your browser

**Features:**
- 📊 Real-time oscilloscope
- 📈 Band power bars (theta/alpha/beta)
- 🎯 Confidence gauge
- 🎭 Mock mode switcher (authenticated/impostor)
- ⚡ WebSocket live updates

**Demo Flow (90 seconds):**
1. Click "Mock Authenticated" button
2. Click "Start Authentication"
3. Watch confidence rise to ~85% → ✅ **ACCESS GRANTED**
4. Click "Mock Impostor" button  
5. Click "Start Authentication"
6. Watch confidence stay at ~30% → ❌ **ACCESS DENIED**

---

### 🔐 Option 2: Command-Line Signature Generator

**Best for:** Understanding the crypto pipeline, batch processing

```bash
cd CortexKey-Python
pip install numpy scipy cryptography pyserial

# Authenticated user
python brainwave_auth.py --mock --passphrase demo2024

# Impostor
python brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024
```

**Features:**
- 🔒 AES-256-GCM encryption
- 🔑 HKDF-SHA256 key derivation
- 📝 Base64 signature output
- 💾 Optional CSV export

**Side-by-side demo:**
```bash
./demo_both_modes.sh
```

---

## 🔌 Real Hardware Mode

### When BioAmp EXG Arrives

**1. Flash ESP32 Firmware:**
```cpp
// In firmware/esp32_neural_auth.ino
#define USE_MOCK_DATA false  // ← Change this
```

Upload to ESP32 via Arduino IDE.

**2. Wire Electrodes:**
```
Fp1 (forehead left)  ──┐
Fp2 (forehead right) ──┤──> BioAmp EXG ──> ESP32 GPIO34 ──> USB
REF (mastoid/ear)    ──┘
```

**3. Run System:**

**Web Dashboard:**
```bash
python backend/app.py
# Auto-detects ESP32, falls back to mock if not found
```

**Command-Line:**
```bash
# Auto-detect port
python CortexKey-Python/brainwave_auth.py --passphrase mykey

# Or specify port
python CortexKey-Python/brainwave_auth.py --port /dev/ttyUSB0 --passphrase mykey
```

---

## 📊 What Each Demo Shows

### Web Dashboard Demo
- **Visual:** Live EEG waveform on oscilloscope
- **Analytics:** Real-time frequency band decomposition
- **ML:** SVM classifier confidence score
- **Result:** Authenticated/Denied decision

### Command-Line Demo
- **Crypto:** Encrypted signature generation
- **Pipeline:** Signal processing steps
- **Comparison:** Authenticated vs Impostor patterns
- **Output:** Base64 encrypted signatures

---

## 🎬 Hackathon Presentation Flow

**Opening (30 seconds):**
```
"Passwords are insecure. Biometrics can be spoofed. 
But your brainwaves? They're unique, dynamic, and impossible to steal.
Let me show you CortexKey."
```

**Demo (60 seconds):**
1. Open web dashboard
2. Click "Mock Authenticated" → Start
3. Point to oscilloscope: "These are brainwave patterns"
4. Point to confidence: "ML model analyzing in real-time"
5. **Access Granted** at 85%
6. Click "Mock Impostor" → Start  
7. Point to noisy waveform: "Different brain signature"
8. **Access Denied** at 30%

**Technical Deep-Dive (30 seconds):**
```bash
# Open terminal, run command-line version
python brainwave_auth.py --mock --passphrase demo
```
"Behind the scenes: 50Hz notch filter, 5-30Hz bandpass, 
PSD extraction, SVM classification, AES-256 encryption."

**Hardware Path (30 seconds):**
- Show BioAmp EXG Pill + ESP32
- "Currently mock data, but this connects in minutes"
- Show firmware: `USE_MOCK_DATA` flag
- "Same code, real brainwaves"

**Closing (30 seconds):**
```
"Why CortexKey?
- Impossible to steal or forge
- No passwords to remember
- Dynamic - changes with your mental state
- Works hands-free

Built in 24 hours. Ready for tomorrow's security."
```

---

## 🏆 Key Differentiators

### vs Passwords
❌ Passwords: Can be stolen, forgotten, phished  
✅ CortexKey: Unique to you, always with you, unforgeable

### vs Fingerprints
❌ Fingerprints: Static, can be lifted, easily copied  
✅ CortexKey: Dynamic, changes with mental state, impossible to replicate

### vs Face ID
❌ Face ID: Can be spoofed with photos/masks  
✅ CortexKey: Live brain activity, not just appearance

---

## 📦 All-in-One Demo Commands

### Quick Test (No Setup)
```bash
# Web dashboard
python backend/app.py

# Command-line
python CortexKey-Python/brainwave_auth.py --mock --passphrase demo
```

### Full Demo (Side-by-Side)
```bash
# Terminal 1: Web dashboard
python backend/app.py

# Terminal 2: Authenticated signatures
python CortexKey-Python/brainwave_auth.py --mock --passphrase demo

# Terminal 3: Impostor signatures  
python CortexKey-Python/brainwave_auth.py --mock --mock-mode impostor --passphrase demo
```

### Hardware Ready
```bash
# Just plug in ESP32 and run - auto-detects!
python backend/app.py
```

---

## 🐛 Troubleshooting

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Port 5001 already in use"
```bash
# Change port in backend/app.py
socketio.run(app, host="0.0.0.0", port=5002)
```

### "No hardware detected"
**This is normal!** System falls back to mock mode automatically.

To force mock mode:
```bash
python backend/app.py  # Already does this
python CortexKey-Python/brainwave_auth.py --mock --passphrase demo
```

---

## 📚 Next Steps

1. ✅ Run web dashboard demo
2. ✅ Run command-line demo
3. ✅ Read `ARCHITECTURE_ANALYSIS.md` for technical details
4. ⏳ Wait for BioAmp EXG hardware
5. 🔌 Connect hardware and watch it work with real brainwaves!

---

**You're ready!** 🎉

Pick your demo mode and start showing off CortexKey's mind-reading authentication!
