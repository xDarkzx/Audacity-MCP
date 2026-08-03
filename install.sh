#!/bin/bash
set -euo pipefail

DRY_RUN=0
for arg in "$@"; do
    if [ "$arg" = "--dry-run" ] || [ "$arg" = "-n" ]; then
        DRY_RUN=1
    fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/install-log.txt"
{
    echo "AudacityMCP installer log"
    echo "Started: $(date)"
    echo "DRY_RUN=$DRY_RUN"
} > "$LOG_FILE" 2>/dev/null || true

fail_exit() {
    { echo ""; echo "INSTALL FAILED"; } >> "$LOG_FILE" 2>/dev/null || true
    echo ""
    echo " Full log saved to: $LOG_FILE"
    echo " If this keeps happening, please report it at:"
    echo " https://github.com/xDarkzx/Audacity-MCP/issues"
    echo " (attach install-log.txt from this folder so we can see exactly what happened)"
    echo ""
    exit 1
}

echo ""
echo " ============================================"
echo "  AudacityMCP - One-Click Installer"
echo "  AI-powered audio editing in Audacity"
echo " ============================================"
echo ""
if [ "$DRY_RUN" = "1" ]; then
    echo " DRY RUN MODE - printing what would happen, changing nothing."
    echo ""
fi

# -- Check Python --------------------------------------------
echo "[1/5] Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
    PYVER=$($PYTHON --version 2>&1)
    echo "  Found $PYVER - already installed, skipping."
    echo "Python: $PYVER" >> "$LOG_FILE" 2>/dev/null || true
elif command -v python &> /dev/null; then
    PYTHON=python
    PYVER=$($PYTHON --version 2>&1)
    echo "  Found $PYVER - already installed, skipping."
    echo "Python: $PYVER" >> "$LOG_FILE" 2>/dev/null || true
else
    echo "Python: NOT FOUND" >> "$LOG_FILE" 2>/dev/null || true
    echo ""
    echo " Python is not installed."
    echo ""
    if [ "$DRY_RUN" = "1" ]; then
        echo " [dry-run] Would offer to install Python via Homebrew (macOS) or"
        echo " apt/dnf/pacman (Linux). Can't preview the remaining steps without"
        echo " Python already installed - install it, then re-run with --dry-run."
        exit 0
    fi
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
                fail_exit
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
                fail_exit
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
            fail_exit
        fi
        PYVER=$($PYTHON --version 2>&1)
        echo "  Found $PYVER"
    else
        echo ""
        echo " AudacityMCP requires Python 3.10+ to run."
        echo " Install it and come back - we'll be here!"
        echo ""
        echo "   macOS:  brew install python3"
        echo "   Ubuntu: sudo apt install python3 python3-pip"
        echo "   Or:     https://www.python.org/downloads/"
        echo ""
        exit 1
    fi
fi

# Verify Python >= 3.10
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo ""
    echo " ERROR: Python 3.10+ is required, but you have $PYVER"
    echo " Please upgrade Python: https://www.python.org/downloads/"
    fail_exit
fi
echo "Python version OK: $PY_MAJOR.$PY_MINOR" >> "$LOG_FILE" 2>/dev/null || true

# Warn if running inside a virtual environment
if [ -n "${VIRTUAL_ENV:-}" ]; then
    echo ""
    echo " WARNING: You are inside a virtual environment."
    echo " audacity-mcp should be installed globally so Claude Desktop can find it."
    echo " Deactivate your venv first: deactivate"
    echo ""
    exit 1
fi

# -- Install audacity-mcp --------------------------------------
# This script only makes sense run from inside an already-downloaded
# copy of the repo (pyproject.toml next to it) - that's the only way
# you'd have install.sh in the first place. Install that local copy
# directly; never re-fetch the source from anywhere.
if [ ! -f "$SCRIPT_DIR/pyproject.toml" ]; then
    echo ""
    echo " ERROR: pyproject.toml not found next to install.sh."
    echo " This script must be run from inside the AudacityMCP repo folder"
    echo " you downloaded/cloned it with - not moved out on its own."
    fail_exit
fi

echo ""
echo "[2/5] Installing audacity-mcp from this local repo copy..."
echo "[2/5] Installing audacity-mcp from this local repo copy..." >> "$LOG_FILE" 2>/dev/null || true

if [ "$DRY_RUN" = "1" ]; then
    echo "  [dry-run] Would run: $PYTHON -m pip install --upgrade pip"
    echo "  [dry-run] Would run: $PYTHON -m pip install \"$SCRIPT_DIR\""
else
    # Check if pip is available
    if ! $PYTHON -m pip --version &> /dev/null; then
        echo "  pip not found, installing pip..."
        if ! $PYTHON -m ensurepip --upgrade &> /dev/null; then
            echo ""
            echo " ERROR: pip is not installed and ensurepip failed."
            echo " Try: $PYTHON -m ensurepip --upgrade"
            echo " Or reinstall Python with pip enabled."
            fail_exit
        fi
    fi

    $PYTHON -m pip install --upgrade pip >/dev/null 2>&1
    if ! $PYTHON -m pip install "$SCRIPT_DIR"; then
        echo ""
        echo " ERROR: pip install failed."
        echo " Try: $PYTHON -m pip install --user \"$SCRIPT_DIR\""
        fail_exit
    fi
    echo "  audacity-mcp installed successfully!"
    echo "audacity-mcp installed successfully" >> "$LOG_FILE" 2>/dev/null || true
fi

# Resolve the actual installed script path instead of trusting PATH.
# Python being on PATH doesn't guarantee its scripts folder is too, and
# a GUI app like Claude Desktop can be running with a different PATH
# than a terminal (e.g. ~/.local/bin is commonly missing from a
# GUI-launched app's PATH on Linux even when a shell sees it fine) - so
# a bare "audacity-mcp" command can work when you test it yourself and
# still fail silently for Claude Desktop. sysconfig.get_path finds the
# scripts folder for the exact Python that pip just installed into,
# regardless of what's on PATH.
AUDACITY_MCP_CMD="audacity-mcp"
SCRIPTS_DIR=$($PYTHON -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null) || SCRIPTS_DIR=""
if [ -n "$SCRIPTS_DIR" ] && [ -x "$SCRIPTS_DIR/audacity-mcp" ]; then
    AUDACITY_MCP_CMD="$SCRIPTS_DIR/audacity-mcp"
fi
echo "Resolved audacity-mcp command: $AUDACITY_MCP_CMD" >> "$LOG_FILE" 2>/dev/null || true

# -- Enable mod-script-pipe in Audacity ------------------------
echo ""
echo "[3/5] Enabling mod-script-pipe in Audacity..."
echo "[3/5] Enabling mod-script-pipe in Audacity..." >> "$LOG_FILE" 2>/dev/null || true

if [[ "$OSTYPE" == "darwin"* ]]; then
    AUD_CFG="$HOME/Library/Application Support/audacity/audacity.cfg"
else
    AUD_CFG="${XDG_CONFIG_HOME:-$HOME/.config}/audacity/audacity.cfg"
    SNAP_CFG="$HOME/snap/audacity/current/.config/audacity/audacity.cfg"
    FLATPAK_CFG="$HOME/.var/app/org.audacityteam.Audacity/config/audacity/audacity.cfg"
    if [ ! -f "$AUD_CFG" ] && [ -f "$SNAP_CFG" ]; then
        AUD_CFG="$SNAP_CFG"
    elif [ ! -f "$AUD_CFG" ] && [ -f "$FLATPAK_CFG" ]; then
        AUD_CFG="$FLATPAK_CFG"
    fi
fi

if [ ! -f "$AUD_CFG" ]; then
    echo "  Audacity config not found at: $AUD_CFG"
    echo "  You may need to open Audacity once first to generate the config,"
    echo "  then run this installer again."
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  Or enable it manually: Audacity > Preferences > Modules > mod-script-pipe > Enabled"
    else
        echo "  Or enable it manually: Edit > Preferences > Modules > mod-script-pipe > Enabled"
    fi
elif grep -q "mod-script-pipe=1" "$AUD_CFG" 2>/dev/null; then
    echo "  mod-script-pipe is already enabled - skipping."
elif [ "$DRY_RUN" = "1" ]; then
    echo "  [dry-run] Would prompt to modify: $AUD_CFG"
    echo "  [dry-run] Would back it up to: $AUD_CFG.bak first"
    echo "  [dry-run] Would set mod-script-pipe=1"
else
    echo ""
    echo "  AudacityMCP needs mod-script-pipe enabled to control Audacity."
    read -rp "  Would you like to modify the Audacity config to allow MCP access? (y/n): " ENABLE_PIPE
    if [[ ! "$ENABLE_PIPE" =~ ^[Yy]$ ]]; then
        echo ""
        echo "  Skipped. You can enable it manually:"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "  Audacity > Preferences > Modules > mod-script-pipe > Enabled"
        else
            echo "  Edit > Preferences > Modules > mod-script-pipe > Enabled"
        fi
    else
        # Back up Audacity config
        cp "$AUD_CFG" "$AUD_CFG.bak"

        if grep -q "mod-script-pipe=" "$AUD_CFG" 2>/dev/null; then
            # Replace existing setting
            sed -i.tmp 's/mod-script-pipe=[02]/mod-script-pipe=1/' "$AUD_CFG"
            rm -f "$AUD_CFG.tmp"
        elif grep -q '\[ModulePath\]' "$AUD_CFG" 2>/dev/null; then
            # Add before [ModulePath] section
            sed -i.tmp 's/\[ModulePath\]/mod-script-pipe=1\n[ModulePath]/' "$AUD_CFG"
            rm -f "$AUD_CFG.tmp"
        else
            # Append to end
            echo "mod-script-pipe=1" >> "$AUD_CFG"
        fi
        echo "  mod-script-pipe enabled!"
        echo "  NOTE: Restart Audacity for this to take effect."
    fi
fi

# -- Configure Claude Desktop ----------------------------------
echo ""
echo "[4/5] Configuring Claude Desktop..."
echo "[4/5] Configuring Claude Desktop..." >> "$LOG_FILE" 2>/dev/null || true
echo ""
echo "  This step can add an \"audacity\" entry to Claude Desktop's config file"
echo "  so it launches audacity-mcp automatically - no manual JSON editing needed."
echo "  What it does, exactly:"
echo "    - Backs up any existing config file before touching it (a .bak copy)"
echo "    - If no config exists yet, creates one with just the audacity entry"
echo "    - If a config already exists, only adds or fixes the audacity entry -"
echo "      it never removes or changes any other MCP server you already have"
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
else
    CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Claude"
fi
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

if [ "$DRY_RUN" = "1" ]; then
    echo "  [dry-run] Would ask to configure Claude Desktop here."
    if [ -f "$CONFIG_FILE" ]; then
        echo "  [dry-run] Would back up: $CONFIG_FILE -> $CONFIG_FILE.bak if a change is"
        echo "  [dry-run] needed, then add or fix only the audacity entry - every other"
        echo "  [dry-run] server already in the file is left untouched. Also fixes an old"
        echo "  [dry-run] broken bare \"audacity-mcp\" command left from a previous install."
    else
        echo "  [dry-run] Would create: $CONFIG_FILE"
        echo "  [dry-run] with a fresh mcpServers block containing the audacity entry"
    fi
else
    read -rp "  Configure Claude Desktop now? (y/n): " CONFIGURE_CLAUDE
    if [[ ! "$CONFIGURE_CLAUDE" =~ ^[Yy]$ ]]; then
        echo ""
        echo "  Skipped. To add it yourself later: open Claude Desktop -> Settings ->"
        echo "  Developer tab -> Edit Config, then add the audacity entry shown in"
        echo "  the installation guide."
    else
        mkdir -p "$CONFIG_DIR"
        [ -f "$CONFIG_FILE" ] && cp "$CONFIG_FILE" "$CONFIG_FILE.bak"

        # Use Python for a real JSON parse/merge instead of text-scanning
        # with grep - this correctly adds or fixes ONLY the "audacity"
        # entry (including upgrading an old broken bare "audacity-mcp"
        # command left over from a previous install) while leaving every
        # other configured MCP server completely untouched.
        MERGE_RESULT=$(CFG_FILE="$CONFIG_FILE" AUD_CMD="$AUDACITY_MCP_CMD" $PYTHON -c "import json,os; p=os.environ['CFG_FILE']; cmd=os.environ['AUD_CMD']; data=json.load(open(p,encoding='utf-8')) if os.path.exists(p) else {}; servers=data.setdefault('mcpServers',{}); aud=servers.get('audacity'); changed = aud is None or (aud.get('command')=='audacity-mcp' and cmd!='audacity-mcp'); servers.__setitem__('audacity', {**(aud or {}),'command':cmd}) if changed else None; (changed and json.dump(data, open(p,'w',encoding='utf-8'), indent=2)); print('WROTE' if changed else 'SKIP')" 2>/dev/null) || MERGE_RESULT="ERROR"
        echo "$CONFIG_FILE: $MERGE_RESULT" >> "$LOG_FILE" 2>/dev/null || true

        if [ "$MERGE_RESULT" = "WROTE" ]; then
            chmod 600 "$CONFIG_FILE"
            echo "  Configured Claude Desktop at: $CONFIG_FILE"
        elif [ "$MERGE_RESULT" = "SKIP" ]; then
            [ -f "$CONFIG_FILE.bak" ] && rm -f "$CONFIG_FILE.bak"
            echo "  $CONFIG_FILE"
            echo "  already correctly configured - skipping."
        else
            echo "  WARNING: could not update $CONFIG_FILE automatically."
            echo "  Add this inside your \"mcpServers\" block by hand:"
            echo ""
            echo '    "audacity": {'
            echo "      \"command\": \"$AUDACITY_MCP_CMD\""
            echo '    }'
        fi
    fi
fi

# -- Done -------------------------------------------------------
echo ""
if [ "$DRY_RUN" = "1" ]; then
    echo "[5/5] Dry run complete - nothing was changed."
    echo ""
    echo " Re-run without --dry-run to actually apply these steps."
    echo ""
    exit 0
fi
echo "[5/5] Done!"
echo "[5/5] Done - setup complete" >> "$LOG_FILE" 2>/dev/null || true
echo ""
echo " ============================================"
echo "  SETUP COMPLETE!"
echo " ============================================"
echo ""
echo " Next steps:"
echo ""
echo "  1. Restart Audacity (if it's open)"
echo "  2. Restart Claude Desktop (if it's open)"
echo "  3. Ask Claude: \"Get info about the current Audacity project\""
echo ""
echo " If you see project info, you're all set!"
echo ""
echo " Using Transcription? Have an NVIDIA GPU? Run ./setup_gpu.sh for 10-20x faster transcription."
echo ""
echo " Docs: https://github.com/xDarkzx/Audacity-MCP"
echo " If this is useful to you, a star on GitHub helps other people find it!"
echo " ============================================"
echo ""
