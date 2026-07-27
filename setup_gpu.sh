#!/bin/bash
set -uo pipefail

echo ""
echo " ============================================"
echo "  AudacityMCP - Transcription GPU Setup"
echo " ============================================"
echo ""

if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo " ERROR: Python not found on PATH."
    echo " Install AudacityMCP first - see install.sh or the installation guide."
    exit 1
fi

$PYTHON -m audacity_mcp.setup_transcription
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo " If you saw \"No module named audacity_mcp\" above, AudacityMCP isn't"
    echo " installed yet - run install.sh first, or:"
    echo "   $PYTHON -m pip install audacity-mcp"
    echo ""
fi

exit $EXIT_CODE
