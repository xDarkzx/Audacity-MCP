@echo off
setlocal enabledelayedexpansion

set "DRY_RUN=0"
if /i "%~1"=="--dry-run" set "DRY_RUN=1"
if /i "%~1"=="/dry-run" set "DRY_RUN=1"

echo.
echo  ============================================
echo   AudacityMCP - One-Click Installer
echo   AI-powered audio editing in Audacity
echo  ============================================
echo.
if "%DRY_RUN%"=="1" (
    echo  DRY RUN MODE - printing what would happen, changing nothing.
    echo.
)

:: -- Check Python --------------------------------------------
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
    echo   Found Python !PYVER! - already installed, skipping.
    goto :python_ready
)

echo.
echo  Python is not installed or not in PATH.
echo.
if "%DRY_RUN%"=="1" (
    echo  [dry-run] Would offer to install Python via winget. Can't preview
    echo  the remaining steps without Python already installed - install it,
    echo  then re-run with --dry-run to see the rest.
    exit /b 0
)
set /p INSTALL_PY="  Would you like to install Python via winget? (y/n): "
if /i "!INSTALL_PY!"=="y" (
    echo.
    echo  Installing Python 3.12 via winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if !errorlevel! neq 0 (
        echo.
        echo  ERROR: winget install failed.
        echo  Download manually from: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    echo.
    echo  Python installed! You need to CLOSE and REOPEN this terminal,
    echo  then run install.bat again so Python is in your PATH.
    echo.
    pause
    exit /b 0
) else (
    echo.
    echo  AudacityMCP requires Python 3.10+ to run.
    echo  Install it and come back - we'll be here!
    echo.
    echo  Download from: https://www.python.org/downloads/
    echo  IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

:python_ready

:: Verify Python >= 3.10
for /f %%m in ('python -c "import sys; print(sys.version_info.minor)"') do set PY_MINOR=%%m
for /f %%M in ('python -c "import sys; print(sys.version_info.major)"') do set PY_MAJOR=%%M
if !PY_MAJOR! lss 3 (
    echo.
    echo  ERROR: Python 3.10+ is required, but you have Python %PYVER%
    echo  Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
if !PY_MAJOR! equ 3 if !PY_MINOR! lss 10 (
    echo.
    echo  ERROR: Python 3.10+ is required, but you have Python %PYVER%
    echo  Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: -- Install audacity-mcp -------------------------------------
:: Warn if running inside a virtual environment
if defined VIRTUAL_ENV (
    echo.
    echo  WARNING: You are inside a virtual environment.
    echo  audacity-mcp should be installed globally so Claude Desktop can find it.
    echo  Deactivate your venv first, or run this installer outside of it.
    echo.
    pause
    exit /b 1
)

:: This script only makes sense run from inside an already-downloaded
:: copy of the repo (pyproject.toml sitting next to it) - that's the
:: only way you'd have install.bat in the first place. Install that
:: local copy directly; never re-fetch the source from anywhere.
set "SCRIPT_DIR=%~dp0"
if not exist "%SCRIPT_DIR%pyproject.toml" (
    echo.
    echo  ERROR: pyproject.toml not found next to install.bat.
    echo  This script must be run from inside the AudacityMCP repo folder
    echo  you downloaded/cloned it with - not moved out on its own.
    echo.
    pause
    exit /b 1
)

echo.
echo [2/5] Installing audacity-mcp from this local repo copy...

if "%DRY_RUN%"=="1" (
    echo   [dry-run] Would run: python -m pip install --upgrade pip
    echo   [dry-run] Would run: python -m pip install "%SCRIPT_DIR%."
) else (
    :: Check if pip is available
    python -m pip --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo   pip not found, installing pip...
        python -m ensurepip --upgrade >nul 2>&1
        if !errorlevel! neq 0 (
            echo.
            echo  ERROR: pip is not installed and ensurepip failed.
            echo  Try reinstalling Python with pip enabled.
            echo.
            pause
            exit /b 1
        )
    )
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install "%SCRIPT_DIR%."
    if !errorlevel! neq 0 (
        echo.
        echo  ERROR: pip install failed. Try running as administrator, or run manually:
        echo    python -m pip install "%SCRIPT_DIR%."
        echo.
        pause
        exit /b 1
    )
    echo   audacity-mcp installed successfully!
)

:: -- Enable mod-script-pipe in Audacity ------------------------
echo.
echo [3/5] Enabling mod-script-pipe in Audacity...

set "AUD_CFG=%APPDATA%\audacity\audacity.cfg"

if not exist "%AUD_CFG%" (
    echo   Audacity config not found at: %AUD_CFG%
    echo   You may need to open Audacity once first to generate the config,
    echo   then run this installer again.
    echo.
    echo   Or enable it manually: Edit ^> Preferences ^> Modules ^> mod-script-pipe ^> Enabled
    goto :skip_audacity
)

:: Check if already enabled
findstr /c:"mod-script-pipe=1" "%AUD_CFG%" >nul 2>&1
if !errorlevel! equ 0 (
    echo   mod-script-pipe is already enabled - skipping.
    goto :skip_audacity
)

if "%DRY_RUN%"=="1" (
    echo   [dry-run] Would prompt to modify: %AUD_CFG%
    echo   [dry-run] Would back it up to: %AUD_CFG%.bak first
    echo   [dry-run] Would set mod-script-pipe=1
    goto :skip_audacity
)

:: Ask permission before modifying Audacity config
echo.
echo   AudacityMCP needs mod-script-pipe enabled to control Audacity.
set /p ENABLE_PIPE="  Would you like to modify the Audacity config to allow MCP access? (y/n): "
if /i not "!ENABLE_PIPE!"=="y" (
    echo.
    echo   Skipped. You can enable it manually:
    echo   Edit ^> Preferences ^> Modules ^> mod-script-pipe ^> Enabled
    goto :skip_audacity
)

:: Back up Audacity config
copy "%AUD_CFG%" "%AUD_CFG%.bak" >nul 2>&1

:: Check if the setting exists but is disabled (0 or 2)
findstr /c:"mod-script-pipe=" "%AUD_CFG%" >nul 2>&1
if !errorlevel! equ 0 (
    :: Replace existing setting with enabled
    python -c "p='%AUD_CFG%'.replace('\\','\\\\'); f=open(p,'r'); t=f.read(); f.close(); t=t.replace('mod-script-pipe=0','mod-script-pipe=1').replace('mod-script-pipe=2','mod-script-pipe=1'); f=open(p,'w'); f.write(t); f.close(); print('  mod-script-pipe enabled!')"
) else (
    :: Setting doesn't exist - need to add it in the right section
    python -c "import re; p='%AUD_CFG%'.replace('\\','\\\\'); f=open(p,'r'); t=f.read(); f.close(); t=re.sub(r'(\[ModulePath\])', r'mod-script-pipe=1\n\1', t, count=1) if '[ModulePath]' in t else t+'\nmod-script-pipe=1\n'; f=open(p,'w'); f.write(t); f.close(); print('  mod-script-pipe enabled!')"
)

echo   NOTE: Restart Audacity for this to take effect.

:skip_audacity

:: -- Configure Claude Desktop ----------------------------------
echo.
echo [4/5] Configuring Claude Desktop...
echo.
echo   This step can add an "audacity" entry to Claude Desktop's config file(s)
echo   so it launches audacity-mcp automatically - no manual JSON editing needed.
echo   What it does, exactly:
echo     - Backs up any existing config file before touching it (a .bak copy)
echo     - If no config exists yet, creates one with just the audacity entry
echo     - If a config already exists, only ADDS the audacity entry - it never
echo       removes or changes any other MCP server you already have configured
echo.

if "%DRY_RUN%"=="1" (
    echo   [dry-run] Would ask to configure Claude Desktop here.
) else (
    set /p CONFIGURE_CLAUDE="  Configure Claude Desktop now? (y/n): "
    if /i not "!CONFIGURE_CLAUDE!"=="y" (
        echo.
        echo   Skipped. To add it yourself later: open Claude Desktop -^> Settings -^>
        echo   Developer tab -^> Edit Config, then add the audacity entry shown in
        echo   the installation guide.
        goto :skip_config
    )
)

call :configure_claude_config "%APPDATA%\Claude"

:: The Microsoft Store / MSIX build of Claude Desktop redirects its AppData
:: writes into an isolated per-package folder - %APPDATA%\Claude is a dead
:: file it never reads, even though it looks like the normal location.
if exist "%LOCALAPPDATA%\Packages" (
    for /d %%D in ("%LOCALAPPDATA%\Packages\Claude_*") do (
        call :configure_claude_config "%%~D\LocalCache\Roaming\Claude"
    )
)

goto :skip_config

:configure_claude_config
set "CONFIG_DIR=%~1"
set "CONFIG_FILE=%CONFIG_DIR%\claude_desktop_config.json"

if "%DRY_RUN%"=="1" (
    if exist "%CONFIG_FILE%" (
        findstr /c:"\"audacity\"" "%CONFIG_FILE%" >nul 2>&1
        if !errorlevel! equ 0 (
            echo   %CONFIG_FILE%
            echo   already has an audacity entry - skipping.
        ) else (
            echo   [dry-run] Would back up: %CONFIG_FILE%
            echo   [dry-run] to: %CONFIG_FILE%.bak
            echo   [dry-run] Would show you the audacity entry to add manually
            echo   (existing config has other content - never auto-merged^)
        )
    ) else (
        echo   [dry-run] Would create: %CONFIG_FILE%
        echo   [dry-run] with a fresh mcpServers block containing the audacity entry
    )
    exit /b
)

if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%" >nul 2>&1

if exist "%CONFIG_FILE%" (
    findstr /c:"\"audacity\"" "%CONFIG_FILE%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   %CONFIG_FILE%
        echo   already has an audacity entry - skipping.
        exit /b
    )
    copy "%CONFIG_FILE%" "%CONFIG_FILE%.bak" >nul 2>&1
    echo   Backed up existing config to: %CONFIG_FILE%.bak
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
    exit /b
)

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
exit /b

:skip_config

:: -- Done -------------------------------------------------------
echo.
if "%DRY_RUN%"=="1" (
    echo [5/5] Dry run complete - nothing was changed.
    echo.
    echo  Re-run without --dry-run to actually apply these steps.
    echo.
    exit /b 0
)
echo [5/5] Done!
echo.
echo  ============================================
echo   SETUP COMPLETE!
echo  ============================================
echo.
echo  Next steps:
echo.
echo   1. Restart Audacity (if it's open)
echo   2. Restart Claude Desktop (if it's open)
echo   3. Ask Claude: "Get info about the current Audacity project"
echo.
echo  If you see project info, you're all set!
echo.
echo  Using Transcription? Have an NVIDIA GPU? Run setup_gpu.bat for 10-20x faster transcription.
echo.
echo  Docs: https://github.com/xDarkzx/Audacity-MCP
echo  If this is useful to you, a star on GitHub helps other people find it!
echo  ============================================
echo.
pause
