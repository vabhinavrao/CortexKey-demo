# ESP32 Chip Information

## Detected ESP32 Model

**Chip Type**: ESP32-D0WD-V3 (revision v3.1)

**Key Specifications**:
- **Model**: ESP32-D0WD-V3 (Classic ESP32, NOT ESP32-S2 or S3)
- **Revision**: v3.1 (latest ESP32 revision)
- **Cores**: Dual Core (Xtensa LX6)
- **Clock Speed**: 240MHz
- **Features**: WiFi, Bluetooth Classic + BLE
- **Flash**: External SPI flash
- **Crystal**: 40MHz
- **MAC Address**: c0:cd:d6:85:22:a0
- **USB Bridge**: CP2102 (Silicon Labs)

## Configuration for Arduino IDE

```
Board: "ESP32 Dev Module"
Upload Speed: 115200
CPU Frequency: 240MHz (WiFi/BT)
Flash Frequency: 80MHz
Flash Mode: DIO
Flash Size: 4MB (32Mb)
Partition Scheme: Default 4MB with spiffs
Core Debug Level: None
PSRAM: Disabled
```

## Configuration for PlatformIO

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
board_build.mcu = esp32
board_build.f_cpu = 240000000L
upload_speed = 115200
monitor_speed = 115200
```

## Important Notes

1. **NOT ESP32-S2 or S3**: Your board is the original ESP32 (D0WD variant)
   - ESP32-S2: Single core, no Bluetooth, USB OTG
   - ESP32-S3: Dual core, BLE only, USB OTG
   - **Your ESP32-D0WD**: Dual core, BT Classic + BLE, best for general use

2. **V3 Revision**: This is the latest revision with improved stability

3. **CP2102 Bridge**: Your board uses Silicon Labs CP2102 USB-to-UART
   - Reliable and widely supported
   - Drivers usually pre-installed on macOS
   - Port: /dev/cu.usbserial-0001

## Flashing Methods

### Method 1: Using esptool (Command line)
```bash
esptool.py --port /dev/cu.usbserial-0001 write_flash 0x1000 firmware.bin
```

### Method 2: Using PlatformIO
```bash
pio run --target upload --environment esp32dev
```

### Method 3: Using Arduino IDE
- Board: ESP32 Dev Module
- Port: /dev/cu.usbserial-0001
- Click Upload

## Verified Configuration
✅ Chip detected successfully
✅ USB-to-UART bridge working
✅ Port available: /dev/cu.usbserial-0001
✅ Ready for firmware upload
