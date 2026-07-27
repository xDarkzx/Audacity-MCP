@echo off
setlocal enabledelayedexpansion

echo.
echo  ============================================
echo   AudacityMCP - Transcription GPU Setup
echo  ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found on PATH.
    echo  Install AudacityMCP first - see install.bat or the installation guide.
    echo.
    pause
    exit /b 1
)

python -m audacity_mcp.setup_transcription
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo  If you saw "No module named audacity_mcp" above, AudacityMCP isn't
    echo  installed in this Python yet - run install.bat first, or:
    echo    python -m pip install audacity-mcp
    echo.
)

pause
exit /b %EXIT_CODE%
