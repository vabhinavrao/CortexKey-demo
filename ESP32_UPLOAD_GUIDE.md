# 🎯 ESP32 Upload Instructions - COMPLETE GUIDE

## ✅ Your ESP32 Information

**Detected Successfully!**
- **Model**: ESP32-D0WD-V3 (Classic ESP32, NOT S2 or S3)
- **Revision**: v3.1 (Latest)
- **Cores**: Dual Core (240MHz)
- **Features**: WiFi + Bluetooth Classic + BLE
- **Port**: `/dev/cu.usbserial-0001`
- **MAC**: c0:cd:d6:85:22:a0
- **USB Bridge**: CP2102 (Silicon Labs)

---

## 🚀 METHOD 1: Upload Using PlatformIO (EASIEST - VS Code)

### Step 1: Open PlatformIO
1. Look at the **left sidebar** in VS Code
2. Click the **PlatformIO icon** (looks like an alien head 👾)
3. Or press `Cmd+Shift+P` and type "PlatformIO"

### Step 2: Open Project
1. In PlatformIO sidebar, click "**Open**"
2. Select folder: `/Users/abhinavrao/coding/hackathon/demo/cortexkey`
3. PlatformIO will detect the `platformio.ini` file

### Step 3: Upload Firmware
1. In PlatformIO toolbar (bottom of VS Code):
   - Click the **"Upload"** button (→ arrow icon)
   - Or click "PlatformIO: Upload" in the toolbar
2. Wait for compilation and upload (1-2 minutes)
3. You'll see progress in the terminal

### Step 4: Monitor Serial Output
1. After upload, click **"Serial Monitor"** button in PlatformIO toolbar
2. Or run: `python tools/esp32_monitor.py`

---

## 🛠️ METHOD 2: Upload Using Arduino IDE (TRADITIONAL)

### Step 1: Open Firmware
```bash
# Option A: Open from Finder
open /Users/abhinavrao/coding/hackathon/demo/cortexkey/firmware/esp32_neural_auth_v2/esp32_neural_auth_v2.ino

# Option B: Open Arduino IDE, then File → Open
```

### Step 2: Configure Board
1. **Tools → Board → ESP32 Arduino → "ESP32 Dev Module"**
2. **Tools → Port → "/dev/cu.usbserial-0001"**
3. **Tools → Upload Speed → "115200"**
4. **Tools → CPU Frequency → "240MHz (WiFi/BT)"**
5. **Tools → Flash Size → "4MB (32Mb)"**

### Step 3: Upload
1. Click the **Upload button** (→ arrow icon)
2. Wait for "Done uploading" message
3. Look for "Hard resetting via RTS pin..."

### Step 4: Open Serial Monitor
1. **Tools → Serial Monitor**
2. Set baud rate to **115200** (bottom right)
3. Press **EN** button on ESP32 to restart

---

## 💻 METHOD 3: Command Line (Advanced)

### Using esptool directly (requires compiled binary)
```bash
# This requires Arduino IDE or PlatformIO to compile first
# Then use esptool to flash the compiled .bin file
```

---

## 📊 Expected Output After Upload

### Startup Banner
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

---

## 🎮 Test Buttons After Upload

### Test 1: Press GPIO18 Button (Valid User)
Expected:
```
========== VALID USER TEST STARTED ==========
STATUS:Button 18 pressed - Starting valid user authentication
DATA,0,24.531
DATA,4,26.872
...
========== TEST COMPLETE (10s) ==========
```

### Test 2: Press GPIO19 Button (Invalid User)
Expected:
```
========== INVALID USER TEST STARTED ==========
STATUS:Button 19 pressed - Starting invalid user authentication
DATA,0,48.234
DATA,4,-12.543
...
========== TEST COMPLETE (10s) ==========
```

---

## 🐛 Troubleshooting

### Error: "Port not found" or "Permission denied"
```bash
# Check if port exists
ls /dev/cu.* | grep usb

# Should show: /dev/cu.usbserial-0001

# If not found, reconnect ESP32 USB cable
```

### Error: "Failed to connect" during upload
**Solution 1: Hold BOOT button**
1. Hold **BOOT** button on ESP32
2. Click **Upload** in Arduino IDE/PlatformIO
3. Release **BOOT** when you see "Connecting..."

**Solution 2: Reset ESP32**
1. Press **EN** button on ESP32
2. Immediately try upload again

### Error: "Compilation failed"
1. Make sure ESP32 board support is installed
2. In Arduino IDE: Tools → Board → Boards Manager → Search "ESP32" → Install
3. In PlatformIO: Should auto-install dependencies

### Serial Monitor shows garbage
1. Check baud rate is **115200**
2. Press **EN** button on ESP32 to restart
3. Try different line ending settings

---

## 📁 Project Files

```
cortexkey/
├── platformio.ini              ← PlatformIO configuration
├── src/
│   └── main.cpp               ← Firmware (copied from .ino)
├── firmware/
│   └── esp32_neural_auth_v2/
│       └── esp32_neural_auth_v2.ino  ← Original Arduino firmware
├── tools/
│   ├── esp32_monitor.py       ← Colored serial monitor
│   └── flash_esp32.py         ← Flash helper script
└── ESP32_CHIP_INFO.md         ← Your chip specifications
```

---

## ✅ Quick Start (Recommended)

### Option A: PlatformIO in VS Code (Fastest)
```
1. Open VS Code
2. Click PlatformIO icon (left sidebar)
3. Click "Upload" button
4. Wait for "SUCCESS"
5. Click "Serial Monitor"
6. Press buttons on ESP32!
```

### Option B: Arduino IDE
```
1. Open firmware/esp32_neural_auth_v2/esp32_neural_auth_v2.ino
2. Select board: ESP32 Dev Module
3. Select port: /dev/cu.usbserial-0001
4. Click Upload
5. Open Serial Monitor (115200 baud)
6. Press buttons on ESP32!
```

---

## 🎯 After Upload Checklist

- [ ] Startup banner appears in Serial Monitor
- [ ] Shows "CORTEXKEY_READY"
- [ ] GPIO18 button triggers valid user test
- [ ] GPIO19 button triggers invalid user test
- [ ] LED blinks during data collection
- [ ] DATA messages stream at 250 Hz
- [ ] Tests auto-complete after 10 seconds

---

## 🆘 Need Help?

### Can't upload?
1. Check USB cable (must support data, not just power)
2. Verify port: `ls /dev/cu.usbserial-0001`
3. Try different USB port on computer
4. Hold BOOT button during upload

### Buttons don't work?
1. Verify wiring: GPIO18/19 to button to GND
2. Test with multimeter
3. Send serial command: type `STATUS` in Serial Monitor

### No serial output?
1. Baud rate must be 115200
2. Press EN button on ESP32
3. Check line ending settings (Newline or Both NL & CR)

---

## 📞 Support Scripts

```bash
# Detect ESP32 and show instructions
python3 tools/flash_esp32.py

# Monitor serial output with colors
python3 tools/esp32_monitor.py

# View chip information
cat ESP32_CHIP_INFO.md
```

---

## ✨ Summary

**Your ESP32 is ready!**
- ✅ Model identified: ESP32-D0WD-V3
- ✅ Port detected: /dev/cu.usbserial-0001
- ✅ Firmware ready: esp32_neural_auth_v2.ino
- ✅ PlatformIO configured
- ✅ Arduino IDE configuration provided
- ✅ Upload scripts created

**Next Step**: Choose upload method above and flash your ESP32! 🚀
