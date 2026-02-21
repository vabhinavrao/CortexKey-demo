# ESP32 Button-Triggered Authentication Testing Guide

## 🎯 Overview

This guide explains how to use **physical buttons on ESP32** to trigger authentication tests with **valid** and **invalid** user data.

---

## 🔧 Hardware Setup

### Required Components
- **ESP32 DevKit V1** (or compatible)
- **2x Push Buttons** (momentary switches)
- **2x 10kΩ Resistors** (pull-up, optional if using internal pull-ups)
- **Breadboard and jumper wires**
- **USB-C cable** for ESP32
- **(Optional) BioAmp EXG Pill** for real EEG sensor

### Wiring Diagram

```
ESP32 Pin Connections:
┌─────────────────────────────────────┐
│  GPIO34  →  EEG Sensor (ADC Input)  │
│  GPIO18  →  Button 1 (VALID User)   │
│  GPIO19  →  Button 2 (INVALID User) │
│  GPIO2   →  Built-in LED (Status)   │
│  GND     →  Common Ground            │
└─────────────────────────────────────┘

Button Wiring (with internal pull-up):
┌────────┐
│ ESP32  │
├────────┤
│ GPIO18 ├───┐
│        │   ├─── [Button 1] ─── GND
│ GPIO19 ├───┤
│        │   └─── [Button 2] ─── GND
│  GND   ├───────────────────── GND
└────────┘

Button 1 (GPIO18): Press to test VALID user
Button 2 (GPIO19): Press to test INVALID user
```

### Alternative: External Pull-Up Resistors
```
     3.3V
       │
    [10kΩ]
       │
       ├────── GPIO18 ──── [Button] ──── GND
       │
    [10kΩ]
       │
       └────── GPIO19 ──── [Button] ──── GND
```

---

## 📝 Firmware Installation

### Step 1: Open Arduino IDE
1. Install **ESP32 board support** in Arduino IDE
   - Go to **File → Preferences**
   - Add to "Additional Board Manager URLs":
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Go to **Tools → Board → Boards Manager**
   - Search "ESP32" and install

### Step 2: Upload Firmware
1. Open `firmware/esp32_neural_auth_v2.ino`
2. Select **Board**: "ESP32 Dev Module"
3. Select **Port**: Your ESP32's COM port
4. Click **Upload** (➡️ arrow button)
5. Wait for "Done uploading"

### Step 3: Open Serial Monitor
1. Go to **Tools → Serial Monitor**
2. Set baud rate to **115200**
3. You should see the startup banner:
   ```
   ========================================
     CortexKey ESP32 Authentication v2.0
     with Button-Triggered Testing
   ========================================
   CORTEXKEY_READY
   ```

---

## 🎮 How to Use Buttons

### Button Functions

| Button | Pin | Function | Expected Result |
|--------|-----|----------|----------------|
| **Button 1** | GPIO18 | Test VALID user | High confidence (≥65%), AUTHENTICATED |
| **Button 2** | GPIO19 | Test INVALID user | Low confidence (<65%), DENIED |
| **Long Press** | Either | Stop test | Returns to IDLE state |

### Test Procedure

#### Test 1: Valid User (Should Pass ✅)
1. **Press Button 1 (GPIO18)** briefly
2. **Observe Serial Monitor**:
   ```
   ========== VALID USER TEST STARTED ==========
   STATUS:Button 18 pressed - Starting valid user authentication
   DATA,0,24.531
   DATA,4,26.872
   DATA,8,23.145
   ...
   ```
3. **Python script** receives data and computes confidence
4. **Expected**: Confidence ≥ 65% → **AUTHENTICATED** ✅
5. Test **auto-stops after 10 seconds**
6. **LED blinks** during data collection

#### Test 2: Invalid User (Should Fail ❌)
1. **Press Button 2 (GPIO19)** briefly
2. **Observe Serial Monitor**:
   ```
   ========== INVALID USER TEST STARTED ==========
   STATUS:Button 19 pressed - Starting invalid user authentication
   DATA,0,48.234
   DATA,4,-12.543
   DATA,8,62.187
   ...
   ```
3. **Python script** receives noisy, inconsistent data
4. **Expected**: Confidence < 65% → **DENIED** ❌
5. Test **auto-stops after 10 seconds**

#### Stop Test (Long Press)
1. **Hold either button for 2 seconds**
2. **Observe**:
   ```
   ========== TEST STOPPED ==========
   STATUS:Long press detected - Returned to idle
   ```
3. **LED turns off**

---

## 🖥️ Python Script Integration

### Run Authentication Test from Python

```bash
# Terminal 1: Run Python script (connects to ESP32)
cd CortexKey-Python
python brainwave_auth.py --port /dev/ttyUSB0 --passphrase mykey --verbose

# Terminal 2: Press buttons on ESP32
# - Press GPIO18 for valid user test
# - Press GPIO19 for invalid user test
```

### Expected Output (Valid User - Button 1)
```
🔌 HARDWARE MODE: Connected to /dev/ttyUSB0
📊 Window: 512 samples, Step: 128, Fs: 256.0 Hz

🚀 Streaming started...

🔌 Signature #1: xK7vZ9pQ2... (Confidence: 0.82)
🔌 Signature #2: aB3cD4eF5... (Confidence: 0.79)
🔌 Signature #3: gH6iJ7kL8... (Confidence: 0.85)

✅ AUTHENTICATED (Average: 0.82 ≥ 0.65 threshold)
```

### Expected Output (Invalid User - Button 2)
```
🔌 HARDWARE MODE: Connected to /dev/ttyUSB0
📊 Window: 512 samples, Step: 128, Fs: 256.0 Hz

🚀 Streaming started...

🔌 Signature #1: mN9oP0qR1... (Confidence: 0.34)
🔌 Signature #2: sT2uV3wX4... (Confidence: 0.41)
🔌 Signature #3: yZ5aB6cD7... (Confidence: 0.29)

❌ DENIED (Average: 0.35 < 0.65 threshold)
```

---

## 🔍 Understanding the EEG Patterns

### Valid User (GPIO18) - Strong Alpha Waves
```
Characteristics:
✅ Strong, slow alpha waves (~2 Hz visible on screen)
✅ Consistent amplitude and frequency
✅ Low noise (~3 µV)
✅ Occasional eye blinks (realistic)
✅ Smooth, regular oscillations

Waveform (ASCII art):
     ╱╲      ╱╲      ╱╲      ╱╲
    ╱  ╲    ╱  ╲    ╱  ╲    ╱  ╲
___╱    ╲__╱    ╲__╱    ╲__╱    ╲___
```

### Invalid User (GPIO19) - Noisy, Irregular
```
Characteristics:
❌ Weak, shifted alpha (~1.5 Hz, wrong frequency)
❌ High noise (~12-15 µV)
❌ Frequent artifacts (muscle tension)
❌ Random spikes and instability
❌ Irregular, chaotic oscillations

Waveform (ASCII art):
   ╱╲╱  ╱╲   ╱╲╱╲  ╱
  ╱  ╲╱   ╲╱    ╲╱ ╲╱╲
_╱              ╲    ╲___
```

---

## 📊 Serial Commands (Alternative to Buttons)

You can also control the ESP32 via serial commands:

| Command | Function |
|---------|----------|
| `START` | Start streaming (authenticated mode) |
| `STOP` | Stop streaming |
| `MOCK_AUTH` | Switch to authenticated mock data |
| `MOCK_IMP` | Switch to impostor mock data |
| `STATUS` | Get current status |

### Example:
```
Send: MOCK_AUTH
Receive: STATUS:Switched to authenticated mock data

Send: START
Receive: STATUS:Started streaming (authenticated mode)
```

---

## 🐛 Troubleshooting

### Button Not Working
- **Check wiring**: GPIO18/19 to button, button to GND
- **Test button**: Use multimeter to verify button closes circuit
- **Check Serial Monitor**: Should see "Button X pressed" message
- **Try internal pull-up**: Code uses `INPUT_PULLUP`, no external resistor needed

### No Data on Serial
- **Baud rate**: Must be **115200**
- **Port**: Select correct COM port
- **Firmware**: Re-upload `esp32_neural_auth_v2.ino`
- **Reset**: Press ESP32 **EN** button to restart

### Wrong Authentication Result
- **Button 1 (GPIO18)**: Should generate STRONG, consistent alpha waves → HIGH confidence
- **Button 2 (GPIO19)**: Should generate NOISY, weak signals → LOW confidence
- **Check thresholds**: Adjust in Python script if needed
- **Collect more samples**: Increase window size for better accuracy

### LED Not Blinking
- **Normal**: LED blinks once per second during data collection
- **Steady on**: Test is running
- **Off**: Idle state
- **Check pin**: Built-in LED on GPIO2 (most ESP32 boards)

---

## 🎨 Visual Feedback

### LED Status Indicators

| LED State | Meaning |
|-----------|---------|
| **Off** | Idle, waiting for button press |
| **Steady On** | Button pressed, test starting |
| **Blinking (1 Hz)** | Collecting data, test in progress |
| **Off after 10s** | Test completed, returned to idle |

### Serial Monitor Output

```
Example Session:

1. Press Button 1 (GPIO18):
   ========== VALID USER TEST STARTED ==========
   STATUS:Button 18 pressed - Starting valid user authentication
   DATA,0,24.531
   DATA,4,26.872
   ...
   (10 seconds of data)
   ========== TEST COMPLETE (10s) ==========
   STATUS:Completed VALID user test - 2500 samples collected

2. Press Button 2 (GPIO19):
   ========== INVALID USER TEST STARTED ==========
   STATUS:Button 19 pressed - Starting invalid user authentication
   DATA,0,48.234
   DATA,4,-12.543
   ...
   (10 seconds of data)
   ========== TEST COMPLETE (10s) ==========
   STATUS:Completed INVALID user test - 2500 samples collected
```

---

## 📚 Next Steps

1. **Wire up buttons** to GPIO18 and GPIO19
2. **Upload firmware** `esp32_neural_auth_v2.ino`
3. **Test buttons** in Serial Monitor
4. **Run Python script** to process data and authenticate
5. **Connect real sensor** when available (set `USE_MOCK_DATA = false`)

---

## 🎯 Summary

- **GPIO18** = Valid user button → Clean, strong brainwaves → **PASS** ✅
- **GPIO19** = Invalid user button → Noisy, weak signals → **FAIL** ❌
- **Long press** = Stop test → Return to idle
- **Auto-stop** = 10 seconds → Automatic test completion
- **LED feedback** = Visual confirmation of test state

**The system now supports hardware-triggered testing for rapid validation!** 🚀
