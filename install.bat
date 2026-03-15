@echo off
setlocal enabledelayedexpansion

echo.
echo  ============================================
echo   AudacityMCP - One-Click Installer
echo   AI-powered audio editing in Audacity
echo  ============================================
echo.

:: ── Check Python ──────────────────────────────────────────
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo.
    echo  Download Python 3.10+ from: https://www.python.org/downloads/
    echo  IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Found Python %PYVER%

:: ── Install audacity-mcp from PyPI ────────────────────────
echo.
echo [2/4] Installing audacity-mcp from PyPI...
pip install audacity-mcp
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: pip install failed. Try running as administrator,
    echo  or run manually: pip install audacity-mcp
    echo.
    pause
    exit /b 1
)
echo   audacity-mcp installed successfully!

:: ── Configure Claude Desktop ──────────────────────────────
echo.
echo [3/4] Configuring Claude Desktop...

set CONFIG_DIR=%APPDATA%\Claude
set CONFIG_FILE=%CONFIG_DIR%\claude_desktop_config.json

:: Create directory if it doesn't exist
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

:: Check if config already exists
if exist "%CONFIG_FILE%" (
    :: Check if audacity is already configured
    findstr /c:"audacity" "%CONFIG_FILE%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   Claude Desktop config already has audacity entry - skipping.
        goto :skip_config
    )
    echo.
    echo   Found existing Claude Desktop config at:
    echo   %CONFIG_FILE%
    echo.
    echo   You need to MANUALLY add this inside your "mcpServers" block:
    echo.
    echo     "audacity": {
    echo       "command": "audacity-mcp"
    echo     }
    echo.
    echo   Opening the config file for you...
    notepad "%CONFIG_FILE%"
    goto :skip_config
)

:: No config exists - create fresh one
(
echo {
echo   "mcpServers": {
echo     "audacity": {
echo       "command": "audacity-mcp"
echo     }
echo   }
echo }
) > "%CONFIG_FILE%"
echo   Created Claude Desktop config at:
echo   %CONFIG_FILE%

:skip_config

:: ── Done ──────────────────────────────────────────────────
echo.
echo [4/4] Almost done!
echo.
echo  ============================================
echo   SETUP COMPLETE!
echo  ============================================
echo.
echo  Before you start, enable Audacity's scripting plugin:
echo.
echo   1. Open Audacity
echo   2. Edit ^> Preferences ^> Modules
echo   3. Set mod-script-pipe to "Enabled"
echo   4. Click OK and RESTART Audacity
echo.
echo  Then:
echo   1. Open Audacity (with mod-script-pipe enabled)
echo   2. Open Claude Desktop (restart it if already open)
echo   3. Ask: "Get info about the current Audacity project"
echo.
echo  If you see project info, you're all set!
echo.
echo  Docs: https://github.com/xDarkzx/Audacity-MCP
echo  ============================================
echo.
pause
