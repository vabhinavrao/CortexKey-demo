# Quick ESP32 Upload Guide

## 🚀 Step-by-Step Instructions

### Step 1: Install Arduino IDE (if not already installed)
1. Download from: https://www.arduino.cc/en/software
2. Install and open Arduino IDE

### Step 2: Install ESP32 Board Support
1. Open Arduino IDE
2. Go to **File → Preferences**
3. In "Additional Board Manager URLs", paste:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Click **OK**
5. Go to **Tools → Board → Boards Manager**
6. Search for **"ESP32"**
7. Click **Install** on "ESP32 by Espressif Systems"
8. Wait for installation to complete

### Step 3: Open the Firmware File
1. In Arduino IDE, go to **File → Open**
2. Navigate to your project folder:
   ```
   /Users/abhinavrao/coding/hackathon/demo/cortexkey/firmware/
   ```
3. Open **`esp32_neural_auth_v2.ino`**

### Step 4: Configure Board Settings
1. Go to **Tools → Board → ESP32 Arduino**
2. Select **"ESP32 Dev Module"** (or your specific board model)
3. Configure these settings:
   - **Upload Speed**: 115200
   - **CPU Frequency**: 240MHz
   - **Flash Frequency**: 80MHz
   - **Flash Mode**: QIO
   - **Flash Size**: 4MB (or match your board)
   - **Partition Scheme**: Default
   - **Core Debug Level**: None

### Step 5: Select the Correct Port
1. Connect your ESP32 via USB-C cable
2. Go to **Tools → Port**
3. Select the port that appears (usually):
   - macOS: `/dev/cu.usbserial-XXXX` or `/dev/cu.SLAB_USBtoUART`
   - If multiple ports, try each one

**Can't find port?** Install CP2102 drivers:
- Download: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
- Install and restart Arduino IDE

### Step 6: Upload the Firmware
1. Click the **Upload** button (→ arrow icon) in Arduino IDE
2. Wait for compilation (may take 1-2 minutes first time)
3. Watch for upload progress:
   ```
   Connecting........_____....._____
   Writing at 0x00010000... (10%)
   Writing at 0x00020000... (20%)
   ...
   Hash of data verified.
   Leaving...
   Hard resetting via RTS pin...
   ```
4. When you see **"Done uploading"**, the firmware is on your ESP32! ✅

### Step 7: Open Serial Monitor
1. Click **Tools → Serial Monitor** (or press `Ctrl+Shift+M` / `Cmd+Shift+M`)
2. Set baud rate to **115200** (bottom right dropdown)
3. Set line ending to **"Newline"** or **"Both NL & CR"**
4. Press the **EN** button on ESP32 to restart

### Step 8: Verify Startup
You should see this banner:
```
========================================
  CortexKey ESP32 Authentication v2.0
  with Button-Triggered Testing
========================================
Hardware:
  GPIO34: EEG Input (ADC)
  GPIO18: Valid User Button
  GPIO19: Invalid User Button

Mock Mode: ENABLED
Sample Rate: 250 Hz

Button Controls:
  Press GPIO18 → Start VALID user test
  Press GPIO19 → Start INVALID user test
  Hold 2s → Stop and return to idle

Serial Commands:
  START, STOP, MOCK_AUTH, MOCK_IMP, STATUS
========================================
CORTEXKEY_READY
```

### Step 9: Test Buttons! 🎮

#### Test 1: Valid User (Button on GPIO18)
1. **Press Button 1** (connected to GPIO18)
2. **Watch Serial Monitor**:
   ```
   ========== VALID USER TEST STARTED ==========
   STATUS:Button 18 pressed - Starting valid user authentication
   DATA,0,24.531
   DATA,4,26.872
   DATA,8,23.145
   ...
   ```
3. **LED should blink** on ESP32
4. After **10 seconds**, test auto-completes:
   ```
   ========== TEST COMPLETE (10s) ==========
   STATUS:Completed VALID user test - 2500 samples collected
   ```

#### Test 2: Invalid User (Button on GPIO19)
1. **Press Button 2** (connected to GPIO19)
2. **Watch Serial Monitor**:
   ```
   ========== INVALID USER TEST STARTED ==========
   STATUS:Button 19 pressed - Starting invalid user authentication
   DATA,0,48.234
   DATA,4,-12.543
   DATA,8,62.187
   ...
   ```
3. After **10 seconds**:
   ```
   ========== TEST COMPLETE (10s) ==========
   STATUS:Completed INVALID user test - 2500 samples collected
   ```

#### Stop Test (Long Press)
1. **Hold either button for 2 seconds**
2. **Watch Serial Monitor**:
   ```
   ========== TEST STOPPED ==========
   STATUS:Long press detected - Returned to idle
   ```

---

## 🐛 Troubleshooting

### Error: "Port not found"
```bash
# macOS: Check available ports
ls /dev/cu.* | grep usb

# If no ports found, install CP2102 driver:
# https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
```

### Error: "Failed to connect"
1. Hold **BOOT** button on ESP32
2. Click **Upload** in Arduino IDE
3. Release **BOOT** when you see "Connecting..."

### Error: "Compilation error"
1. Make sure ESP32 board support is installed
2. Select correct board: "ESP32 Dev Module"
3. Close and reopen Arduino IDE

### Serial Monitor shows garbage characters
1. Check baud rate is **115200**
2. Press **EN** button on ESP32 to restart
3. Try different USB cable (some are power-only)

### Buttons not responding
1. Verify wiring:
   - GPIO18 → Button → GND
   - GPIO19 → Button → GND
2. Test with multimeter (button should show continuity when pressed)
3. Try sending serial command: Type `STATUS` and press Enter

---

## 📊 What You Should See

### Valid User Button (GPIO18):
- **Clean, slow alpha waves**: ~2 Hz oscillation visible
- **Consistent amplitude**: ~20-30 µV
- **Low noise**: Smooth waveform
- **Occasional blinks**: Realistic artifacts

### Invalid User Button (GPIO19):
- **Noisy, irregular waves**: High frequency noise
- **Unstable amplitude**: Random spikes
- **High noise**: ~12-15 µV background
- **Frequent artifacts**: Muscle tension, movement

---

## 🎯 Next Steps After Upload

Once firmware is uploaded and buttons work:

### Option 1: Just View Serial Output
- Keep Serial Monitor open
- Press buttons to see data streaming
- Observe the different patterns between valid/invalid

### Option 2: Connect to Python Backend
```bash
# Find your ESP32 port
ls /dev/cu.* | grep usb

# Run Python authentication script
cd /Users/abhinavrao/coding/hackathon/demo/cortexkey/CortexKey-Python
python brainwave_auth.py --port /dev/cu.usbserial-XXXX --passphrase mykey

# Now press buttons on ESP32!
# - GPIO18 = Should authenticate (high confidence)
# - GPIO19 = Should reject (low confidence)
```

### Option 3: Use Web Interface
1. Start backend server (if configured)
2. Open web interface
3. Press hardware buttons to trigger tests
4. See real-time results in browser

---

## ✅ Success Checklist

- [ ] Arduino IDE installed
- [ ] ESP32 board support installed
- [ ] Correct port selected
- [ ] Firmware uploaded successfully
- [ ] Serial Monitor shows startup banner
- [ ] Button 1 (GPIO18) triggers valid user test
- [ ] Button 2 (GPIO19) triggers invalid user test
- [ ] Long press stops test
- [ ] LED blinks during data collection
- [ ] Data appears in serial monitor

---

## 📞 Need Help?

If you encounter issues:
1. Check troubleshooting section above
2. Verify all hardware connections
3. Try different USB port/cable
4. Reset ESP32 with EN button
5. Re-upload firmware

**Your firmware is ready to flash!** 🚀
