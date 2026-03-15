#!/bin/bash

echo ""
echo " ============================================"
echo "  AudacityMCP - One-Click Installer"
echo "  AI-powered audio editing in Audacity"
echo " ============================================"
echo ""

# ── Check Python ──────────────────────────────────────────
echo "[1/4] Checking Python..."
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo ""
        echo " ERROR: Python is not installed."
        echo ""
        echo " Install Python 3.10+:"
        echo "   macOS:  brew install python3"
        echo "   Ubuntu: sudo apt install python3 python3-pip"
        echo ""
        exit 1
    fi
    PYTHON=python
else
    PYTHON=python3
fi
PYVER=$($PYTHON --version 2>&1)
echo "  Found $PYVER"

# ── Install audacity-mcp from PyPI ────────────────────────
echo ""
echo "[2/4] Installing audacity-mcp from PyPI..."
$PYTHON -m pip install audacity-mcp
if [ $? -ne 0 ]; then
    echo ""
    echo " ERROR: pip install failed."
    echo " Try: $PYTHON -m pip install --user audacity-mcp"
    echo ""
    exit 1
fi
echo "  audacity-mcp installed successfully!"

# ── Configure Claude Desktop ──────────────────────────────
echo ""
echo "[3/4] Configuring Claude Desktop..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
else
    CONFIG_DIR="$HOME/.config/Claude"
fi
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    if grep -q "audacity" "$CONFIG_FILE" 2>/dev/null; then
        echo "  Claude Desktop config already has audacity entry - skipping."
    else
        echo ""
        echo "  Found existing Claude Desktop config at:"
        echo "  $CONFIG_FILE"
        echo ""
        echo "  Add this inside your \"mcpServers\" block:"
        echo ""
        echo '    "audacity": {'
        echo '      "command": "audacity-mcp"'
        echo '    }'
        echo ""
    fi
else
    cat > "$CONFIG_FILE" << 'EOF'
{
  "mcpServers": {
    "audacity": {
      "command": "audacity-mcp"
    }
  }
}
EOF
    echo "  Created Claude Desktop config at:"
    echo "  $CONFIG_FILE"
fi

# ── Done ──────────────────────────────────────────────────
echo ""
echo "[4/4] Almost done!"
echo ""
echo " ============================================"
echo "  SETUP COMPLETE!"
echo " ============================================"
echo ""
echo " Before you start, enable Audacity's scripting plugin:"
echo ""
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  1. Open Audacity"
    echo "  2. Audacity > Preferences > Modules"
else
    echo "  1. Open Audacity"
    echo "  2. Edit > Preferences > Modules"
fi
echo "  3. Set mod-script-pipe to \"Enabled\""
echo "  4. Click OK and RESTART Audacity"
echo ""
echo " Then:"
echo "  1. Open Audacity (with mod-script-pipe enabled)"
echo "  2. Open Claude Desktop (restart if already open)"
echo "  3. Ask: \"Get info about the current Audacity project\""
echo ""
echo " Docs: https://github.com/xDarkzx/Audacity-MCP"
echo " ============================================"
echo ""
