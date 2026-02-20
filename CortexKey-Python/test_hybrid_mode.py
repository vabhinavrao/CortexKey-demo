#!/usr/bin/env python3
"""
Quick test script to verify brainwave_auth.py hybrid mode works correctly.
"""

import sys
import time
import subprocess
from pathlib import Path

def test_imports():
    """Test that required imports work."""
    print("Testing imports...")
    try:
        import numpy
        print("  ✅ numpy")
    except ImportError:
        print("  ❌ numpy - run: pip install numpy")
        return False
    
    try:
        import scipy
        print("  ✅ scipy")
    except ImportError:
        print("  ❌ scipy - run: pip install scipy")
        return False
    
    try:
        import cryptography
        print("  ✅ cryptography")
    except ImportError:
        print("  ❌ cryptography - run: pip install cryptography")
        return False
    
    try:
        import serial
        print("  ✅ pyserial (optional - for hardware)")
    except ImportError:
        print("  ⚠️  pyserial not installed (mock mode will work)")
    
    return True

def test_mock_mode():
    """Test mock mode runs without errors."""
    print("\nTesting mock mode (5 seconds)...")
    
    script = Path(__file__).parent / "brainwave_auth.py"
    if not script.exists():
        print(f"  ❌ brainwave_auth.py not found at {script}")
        return False
    
    cmd = [
        sys.executable,
        str(script),
        "--mock",
        "--passphrase", "test123",
        "--window", "256",
        "--step", "64",
    ]
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Let it run for 5 seconds
        time.sleep(5)
        proc.terminate()
        
        stdout, stderr = proc.communicate(timeout=2)
        
        # Check for success indicators
        if "MOCK MODE" in stdout and "Signature:" in stdout:
            print("  ✅ Mock mode working - signatures generated")
            return True
        else:
            print("  ❌ Mock mode failed")
            print(f"  STDOUT: {stdout[:200]}")
            print(f"  STDERR: {stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        proc.kill()
        print("  ❌ Process didn't terminate cleanly")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    print("=" * 70)
    print("  🧠 CortexKey Brainwave Auth - Hybrid Mode Test")
    print("=" * 70)
    print()
    
    # Test imports
    if not test_imports():
        print("\n❌ Missing dependencies. Install with:")
        print("   pip install numpy scipy cryptography pyserial")
        sys.exit(1)
    
    # Test mock mode
    if not test_mock_mode():
        print("\n❌ Mock mode test failed")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("  ✅ ALL TESTS PASSED!")
    print("=" * 70)
    print()
    print("Your setup is ready! Try these commands:")
    print()
    print("1. Run mock authenticated mode:")
    print("   python brainwave_auth.py --mock --passphrase demo2024")
    print()
    print("2. Run mock impostor mode:")
    print("   python brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024")
    print()
    print("3. Try auto-detect (falls back to mock if no hardware):")
    print("   python brainwave_auth.py --passphrase demo2024")
    print()
    print("4. Run side-by-side demo:")
    print("   ./demo_both_modes.sh")
    print()

if __name__ == "__main__":
    main()
