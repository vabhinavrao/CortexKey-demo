#!/bin/bash
# CortexKey Demo Script - Compare Authenticated vs Impostor

echo "========================================================================"
echo "  🧠 CortexKey Brainwave Authentication Demo"
echo "========================================================================"
echo ""
echo "This demo compares encrypted signatures from:"
echo "  1. Authenticated User (strong alpha/beta waves)"
echo "  2. Impostor (random noise)"
echo ""
echo "Press Ctrl+C in each window to stop."
echo ""
echo "========================================================================"

# Check if script exists
if [ ! -f "brainwave_auth.py" ]; then
    echo "❌ Error: brainwave_auth.py not found in current directory"
    exit 1
fi

# Check Python and dependencies
python3 -c "import numpy, scipy, cryptography" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Please run:"
    echo "   pip install numpy scipy cryptography"
    exit 1
fi

echo ""
echo "Opening two terminals..."
echo ""

# Detect OS and open terminals
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    osascript <<EOF
tell application "Terminal"
    do script "cd \"$PWD\" && echo '🎭 AUTHENTICATED USER MODE' && echo '========================' && echo '' && python3 brainwave_auth.py --mock --passphrase demo2024"
    do script "cd \"$PWD\" && echo '🚫 IMPOSTOR MODE' && echo '================' && echo '' && python3 brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024"
    activate
end tell
EOF
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c "echo '🎭 AUTHENTICATED USER MODE' && echo '========================' && echo '' && python3 brainwave_auth.py --mock --passphrase demo2024; exec bash"
        gnome-terminal -- bash -c "echo '🚫 IMPOSTOR MODE' && echo '================' && echo '' && python3 brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024; exec bash"
    elif command -v xterm &> /dev/null; then
        xterm -e "echo '🎭 AUTHENTICATED USER MODE' && echo '========================' && echo '' && python3 brainwave_auth.py --mock --passphrase demo2024; exec bash" &
        xterm -e "echo '🚫 IMPOSTOR MODE' && echo '================' && echo '' && python3 brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024; exec bash" &
    else
        echo "⚠️  No supported terminal emulator found (gnome-terminal or xterm)"
        echo "Run these commands manually in separate terminals:"
        echo ""
        echo "Terminal 1 (Authenticated):"
        echo "  python3 brainwave_auth.py --mock --passphrase demo2024"
        echo ""
        echo "Terminal 2 (Impostor):"
        echo "  python3 brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024"
        exit 1
    fi
else
    # Windows or other
    echo "⚠️  Auto-launch not supported on this OS"
    echo "Run these commands manually in separate terminals:"
    echo ""
    echo "Terminal 1 (Authenticated):"
    echo "  python brainwave_auth.py --mock --passphrase demo2024"
    echo ""
    echo "Terminal 2 (Impostor):"
    echo "  python brainwave_auth.py --mock --mock-mode impostor --passphrase demo2024"
    exit 1
fi

echo "✅ Demo launched!"
echo ""
echo "Compare the signatures:"
echo "  - Authenticated user: Consistent, strong patterns"
echo "  - Impostor: Noisy, inconsistent patterns"
echo ""
echo "Press Ctrl+C in each terminal window to stop."
