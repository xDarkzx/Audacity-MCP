#!/bin/bash
set -euo pipefail

echo ""
echo " ============================================"
echo "  AudacityMCP - One-Click Installer"
echo "  AI-powered audio editing in Audacity"
echo " ============================================"
echo ""

# ── Check Python ──────────────────────────────────────────
echo "[1/4] Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo ""
    echo " Python is not installed."
    echo ""
    read -rp " Would you like to install Python now? (y/n): " INSTALL_PY
    if [[ "$INSTALL_PY" =~ ^[Yy]$ ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                echo " Installing Python via Homebrew..."
                brew install python3
            else
                echo " Homebrew not found. Install it first:"
                echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                echo " Then run this installer again."
                exit 1
            fi
        else
            if command -v apt &> /dev/null; then
                echo " Installing Python via apt..."
                sudo apt update && sudo apt install -y python3 python3-pip
            elif command -v dnf &> /dev/null; then
                echo " Installing Python via dnf..."
                sudo dnf install -y python3 python3-pip
            elif command -v pacman &> /dev/null; then
                echo " Installing Python via pacman..."
                sudo pacman -S --noconfirm python python-pip
            else
                echo " Could not detect your package manager."
                echo " Install Python 3.10+ manually: https://www.python.org/downloads/"
                exit 1
            fi
        fi
        # Re-detect after install
        if command -v python3 &> /dev/null; then
            PYTHON=python3
        elif command -v python &> /dev/null; then
            PYTHON=python
        else
            echo ""
            echo " ERROR: Python install succeeded but python3 not found in PATH."
            echo " Close and reopen your terminal, then run this installer again."
            exit 1
        fi
    else
        echo ""
        echo " AudacityMCP requires Python 3.10+ to run."
        echo " Install it and come back — we'll be here!"
        echo ""
        echo "   macOS:  brew install python3"
        echo "   Ubuntu: sudo apt install python3 python3-pip"
        echo "   Or:     https://www.python.org/downloads/"
        echo ""
        exit 1
    fi
fi

PYVER=$($PYTHON --version 2>&1)
echo "  Found $PYVER"

# Verify Python >= 3.10
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo ""
    echo " ERROR: Python 3.10+ is required, but you have $PYVER"
    echo " Please upgrade Python: https://www.python.org/downloads/"
    echo ""
    exit 1
fi

# Warn if running inside a virtual environment
if [ -n "${VIRTUAL_ENV:-}" ]; then
    echo ""
    echo " WARNING: You are inside a virtual environment."
    echo " audacity-mcp should be installed globally so Claude Desktop can find it."
    echo " Deactivate your venv first: deactivate"
    echo ""
    exit 1
fi

# ── Install audacity-mcp from PyPI ────────────────────────
echo ""
echo "[2/4] Installing audacity-mcp from PyPI..."

# Check if pip is available
if ! $PYTHON -m pip --version &> /dev/null; then
    echo "  pip not found, installing pip..."
    if ! $PYTHON -m ensurepip --upgrade &> /dev/null; then
        echo ""
        echo " ERROR: pip is not installed and ensurepip failed."
        echo " Try: $PYTHON -m ensurepip --upgrade"
        echo " Or reinstall Python with pip enabled."
        echo ""
        exit 1
    fi
fi

if ! $PYTHON -m pip install audacity-mcp; then
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
    CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Claude"
fi
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    if grep -q '"audacity"' "$CONFIG_FILE" 2>/dev/null; then
        echo "  Claude Desktop config already has audacity entry - skipping."
    else
        # Back up existing config
        cp "$CONFIG_FILE" "$CONFIG_FILE.bak"
        echo "  Backed up existing config to: $CONFIG_FILE.bak"
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
    chmod 600 "$CONFIG_FILE"
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
