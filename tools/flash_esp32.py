#!/usr/bin/env python3
"""
ESP32 Firmware Flasher for CortexKey
Compiles and flashes firmware to ESP32 using esptool
"""

import subprocess
import sys
import os
from pathlib import Path

# Configuration
ESP32_PORT = "/dev/cu.usbserial-0001"
BAUD_RATE = 115200
CHIP_TYPE = "esp32"
FIRMWARE_SRC = "firmware/esp32_neural_auth_v2/esp32_neural_auth_v2.ino"

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def check_port():
    """Check if ESP32 is connected"""
    print_header("Checking ESP32 Connection")
    try:
        result = subprocess.run(
            ["esptool.py", "--port", ESP32_PORT, "chip_id"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "ESP32" in result.stdout:
            print("✅ ESP32 detected successfully!")
            print(f"   Port: {ESP32_PORT}")
            # Extract chip info
            for line in result.stdout.split('\n'):
                if "Chip is" in line or "Features" in line or "MAC" in line:
                    print(f"   {line.strip()}")
            return True
        else:
            print(f"❌ No ESP32 found on {ESP32_PORT}")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout connecting to {ESP32_PORT}")
        return False
    except FileNotFoundError:
        print("❌ esptool.py not found. Install with: pip3 install esptool")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def erase_flash():
    """Erase ESP32 flash (optional, for clean install)"""
    print_header("Erasing Flash (Optional)")
    response = input("Do you want to erase flash before uploading? (y/N): ")
    if response.lower() == 'y':
        print("Erasing flash...")
        try:
            subprocess.run(
                ["esptool.py", "--port", ESP32_PORT, "erase_flash"],
                check=True
            )
            print("✅ Flash erased successfully!")
            return True
        except subprocess.CalledProcessError:
            print("❌ Flash erase failed")
            return False
    else:
        print("Skipping flash erase")
        return True

def flash_with_arduino_cli():
    """Flash using Arduino CLI if available"""
    print_header("Flashing with Arduino CLI")
    
    # Check if arduino-cli is available
    try:
        subprocess.run(["arduino-cli", "version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("❌ Arduino CLI not found")
        return False
    
    print("Compiling firmware...")
    compile_cmd = [
        "arduino-cli", "compile",
        "--fqbn", "esp32:esp32:esp32",
        FIRMWARE_SRC
    ]
    
    try:
        subprocess.run(compile_cmd, check=True)
        print("✅ Compilation successful!")
    except subprocess.CalledProcessError:
        print("❌ Compilation failed")
        return False
    
    print(f"Uploading to {ESP32_PORT}...")
    upload_cmd = [
        "arduino-cli", "upload",
        "--fqbn", "esp32:esp32:esp32",
        "--port", ESP32_PORT,
        FIRMWARE_SRC
    ]
    
    try:
        subprocess.run(upload_cmd, check=True)
        print("✅ Upload successful!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Upload failed")
        return False

def open_serial_monitor():
    """Open serial monitor after flashing"""
    print_header("Serial Monitor")
    print(f"Opening serial monitor on {ESP32_PORT} at {BAUD_RATE} baud...")
    print("Press Ctrl+C to exit\n")
    
    try:
        # Use screen command for serial monitor
        subprocess.run([
            "screen", ESP32_PORT, str(BAUD_RATE)
        ])
    except KeyboardInterrupt:
        print("\n\nSerial monitor closed")
    except FileNotFoundError:
        print("Note: 'screen' not found. Use: python tools/esp32_monitor.py")

def main():
    """Main flasher function"""
    print_header("CortexKey ESP32 Firmware Flasher")
    print(f"Target: {CHIP_TYPE}")
    print(f"Port: {ESP32_PORT}")
    print(f"Baud: {BAUD_RATE}")
    print(f"Firmware: {FIRMWARE_SRC}")
    
    # Step 1: Check connection
    if not check_port():
        print("\n❌ Cannot proceed without ESP32 connection")
        print("\nTroubleshooting:")
        print("  1. Check USB cable is connected")
        print("  2. Verify port with: ls /dev/cu.* | grep usb")
        print("  3. Install CP2102 drivers if needed")
        sys.exit(1)
    
    # Step 2: Optional flash erase
    if not erase_flash():
        print("\n⚠️  Flash erase failed, but continuing...")
    
    # Step 3: Flash firmware
    print_header("Flashing Firmware")
    print("⚠️  IMPORTANT: This requires Arduino IDE or Arduino CLI")
    print("\nOptions:")
    print("  1. Use Arduino IDE (recommended)")
    print("     - Open: firmware/esp32_neural_auth_v2/esp32_neural_auth_v2.ino")
    print("     - Board: ESP32 Dev Module")
    print(f"     - Port: {ESP32_PORT}")
    print("     - Click Upload")
    print("\n  2. Use PlatformIO in VS Code")
    print("     - Open PlatformIO")
    print("     - Click 'Upload' button")
    print("\n  3. Try Arduino CLI (if installed)")
    
    response = input("\nTry Arduino CLI now? (y/N): ")
    if response.lower() == 'y':
        if flash_with_arduino_cli():
            # Open serial monitor
            response = input("\nOpen serial monitor? (Y/n): ")
            if response.lower() != 'n':
                open_serial_monitor()
        else:
            print("\n❌ Please use Arduino IDE or PlatformIO to flash")
            print(f"\nQuick Arduino IDE steps:")
            print(f"  1. Open: {FIRMWARE_SRC}")
            print(f"  2. Tools → Board → ESP32 Dev Module")
            print(f"  3. Tools → Port → {ESP32_PORT}")
            print(f"  4. Click Upload (→)")
    else:
        print("\n📋 Next Steps:")
        print(f"  1. Open Arduino IDE")
        print(f"  2. File → Open → {os.path.abspath(FIRMWARE_SRC)}")
        print(f"  3. Tools → Board → ESP32 Dev Module")
        print(f"  4. Tools → Port → {ESP32_PORT}")
        print(f"  5. Click Upload (→) button")
        print(f"\n  After upload, run: python tools/esp32_monitor.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Flasher interrupted by user")
        sys.exit(0)
