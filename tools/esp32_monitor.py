#!/usr/bin/env python3
"""
ESP32 Serial Monitor for CortexKey
Connects to ESP32 and displays serial output with color coding
"""

import serial
import sys
import time
from datetime import datetime

# Configuration
PORT = "/dev/cu.usbserial-0001"  # Detected ESP32 port
BAUD = 115200

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

def colorize_line(line):
    """Add color coding based on line content"""
    line_upper = line.upper()
    
    if "ERROR" in line_upper:
        return f"{Colors.RED}{line}{Colors.RESET}"
    elif "STATUS:" in line_upper:
        return f"{Colors.CYAN}{line}{Colors.RESET}"
    elif "VALID USER TEST STARTED" in line_upper:
        return f"{Colors.GREEN}{Colors.BOLD}{line}{Colors.RESET}"
    elif "INVALID USER TEST STARTED" in line_upper:
        return f"{Colors.RED}{Colors.BOLD}{line}{Colors.RESET}"
    elif "TEST COMPLETE" in line_upper or "TEST STOPPED" in line_upper:
        return f"{Colors.YELLOW}{Colors.BOLD}{line}{Colors.RESET}"
    elif "DATA," in line_upper:
        return f"{Colors.WHITE}{line}{Colors.RESET}"
    elif "CORTEXKEY_READY" in line_upper:
        return f"{Colors.GREEN}{Colors.BOLD}{line}{Colors.RESET}"
    elif "========" in line:
        return f"{Colors.MAGENTA}{line}{Colors.RESET}"
    elif "Button" in line:
        return f"{Colors.YELLOW}{line}{Colors.RESET}"
    else:
        return line

def main():
    """Connect to ESP32 and monitor serial output"""
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 60)
    print("  CortexKey ESP32 Serial Monitor")
    print("=" * 60)
    print(f"{Colors.RESET}")
    print(f"Port: {PORT}")
    print(f"Baud: {BAUD}")
    print(f"\nConnecting to ESP32...")
    
    try:
        # Open serial connection
        ser = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)  # Wait for connection to stabilize
        
        print(f"{Colors.GREEN}✅ Connected!{Colors.RESET}")
        print(f"\n{Colors.YELLOW}Waiting for ESP32 data...{Colors.RESET}")
        print(f"{Colors.CYAN}Press buttons on ESP32 to test:{Colors.RESET}")
        print(f"  • GPIO18 = Valid User Test (should authenticate)")
        print(f"  • GPIO19 = Invalid User Test (should reject)")
        print(f"  • Hold 2s = Stop test")
        print(f"\n{Colors.YELLOW}Press Ctrl+C to exit{Colors.RESET}\n")
        print("=" * 60 + "\n")
        
        # Statistics
        data_count = 0
        valid_tests = 0
        invalid_tests = 0
        
        # Read and display serial output
        while True:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        # Update statistics
                        if "DATA," in line:
                            data_count += 1
                        elif "VALID USER TEST STARTED" in line:
                            valid_tests += 1
                        elif "INVALID USER TEST STARTED" in line:
                            invalid_tests += 1
                        
                        # Display with timestamp and color
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        colored_line = colorize_line(line)
                        print(f"[{timestamp}] {colored_line}")
                        
                        # Show stats periodically
                        if data_count > 0 and data_count % 100 == 0:
                            print(f"{Colors.BLUE}📊 Stats: {data_count} samples | "
                                  f"{valid_tests} valid tests | {invalid_tests} invalid tests{Colors.RESET}")
                
                except UnicodeDecodeError:
                    continue
            
            time.sleep(0.001)  # Small delay to prevent CPU spinning
    
    except serial.SerialException as e:
        print(f"\n{Colors.RED}❌ Error: {e}{Colors.RESET}")
        print(f"\n{Colors.YELLOW}Troubleshooting:{Colors.RESET}")
        print("1. Make sure ESP32 is connected via USB")
        print("2. Check that firmware is uploaded")
        print("3. Try unplugging and reconnecting ESP32")
        print("4. Check available ports with: ls /dev/cu.*")
        sys.exit(1)
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}🛑 Monitoring stopped by user{Colors.RESET}")
        print(f"\n{Colors.CYAN}📊 Final Statistics:{Colors.RESET}")
        print(f"  • Total samples: {data_count}")
        print(f"  • Valid user tests: {valid_tests}")
        print(f"  • Invalid user tests: {invalid_tests}")
        print(f"\n{Colors.GREEN}Goodbye!{Colors.RESET}\n")
        ser.close()
        sys.exit(0)
    
    except Exception as e:
        print(f"\n{Colors.RED}❌ Unexpected error: {e}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
