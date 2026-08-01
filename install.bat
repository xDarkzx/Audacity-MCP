@echo off
setlocal enabledelayedexpansion

set "DRY_RUN=0"
if /i "%~1"=="--dry-run" set "DRY_RUN=1"
if /i "%~1"=="/dry-run" set "DRY_RUN=1"

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%install-log.txt"
(
echo AudacityMCP installer log
echo Started: %DATE% %TIME%
echo DRY_RUN=%DRY_RUN%
) > "%LOG_FILE%" 2>nul

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
    >>"%LOG_FILE%" echo Python: !PYVER!
    goto :python_ready
)

>>"%LOG_FILE%" echo Python: NOT FOUND
echo.
echo  Python is not installed or not in PATH.
echo.
if "%DRY_RUN%"=="1" (
    echo  [dry-run] Would offer to install Python via winget. Can't preview
    echo  the remaining steps without Python already installed - install it,
    echo  then re-run with --dry-run to see the rest.
    exit /b 0
)
:: NOTE: goto cannot safely jump out of the middle of an if()/else()
:: compound statement - cmd.exe parses the whole if/else as one unit and
:: a goto escaping mid-way corrupts its parse state, causing lines after
:: the block to be silently skipped or duplicated. Every branch below
:: that needs to reach :fail_exit sets a flag instead and the actual
:: goto happens in a plain, unnested statement after the block closes.
set "WINGET_FAILED=0"
set /p INSTALL_PY="  Would you like to install Python via winget? (y/n): "
if /i "!INSTALL_PY!"=="y" (
    echo.
    echo  Installing Python 3.12 via winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if !errorlevel! neq 0 (
        echo.
        echo  ERROR: winget install failed.
        echo  Download manually from: https://www.python.org/downloads/
        set "WINGET_FAILED=1"
    ) else (
        echo.
        echo  Python installed! You need to CLOSE and REOPEN this terminal,
        echo  then run install.bat again so Python is in your PATH.
        echo.
        pause
        exit /b 0
    )
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
if "%WINGET_FAILED%"=="1" goto :fail_exit

:python_ready

:: Verify Python >= 3.10
for /f %%m in ('python -c "import sys; print(sys.version_info.minor)"') do set PY_MINOR=%%m
for /f %%M in ('python -c "import sys; print(sys.version_info.major)"') do set PY_MAJOR=%%M
if !PY_MAJOR! lss 3 (
    echo.
    echo  ERROR: Python 3.10+ is required, but you have Python %PYVER%
    echo  Download from: https://www.python.org/downloads/
    goto :fail_exit
)
if !PY_MAJOR! equ 3 if !PY_MINOR! lss 10 (
    echo.
    echo  ERROR: Python 3.10+ is required, but you have Python %PYVER%
    echo  Download from: https://www.python.org/downloads/
    goto :fail_exit
)

>>"%LOG_FILE%" echo Python version OK: %PY_MAJOR%.%PY_MINOR%

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
if not exist "%SCRIPT_DIR%pyproject.toml" (
    echo.
    echo  ERROR: pyproject.toml not found next to install.bat.
    echo  This script must be run from inside the AudacityMCP repo folder
    echo  you downloaded/cloned it with - not moved out on its own.
    goto :fail_exit
)

echo.
echo [2/5] Installing audacity-mcp from this local repo copy...
>>"%LOG_FILE%" echo [2/5] Installing audacity-mcp from this local repo copy...

set "STEP2_FAILED=0"
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
            set "STEP2_FAILED=1"
        )
    )
    if not "!STEP2_FAILED!"=="1" (
        python -m pip install --upgrade pip >nul 2>&1
        python -m pip install "%SCRIPT_DIR%."
        if !errorlevel! neq 0 (
            echo.
            echo  ERROR: pip install failed. Try running as administrator, or run manually:
            echo    python -m pip install "%SCRIPT_DIR%."
            set "STEP2_FAILED=1"
        ) else (
            echo   audacity-mcp installed successfully!
            >>"%LOG_FILE%" echo audacity-mcp installed successfully
        )
    )
)
if "%STEP2_FAILED%"=="1" goto :fail_exit

:: Resolve the actual installed script path instead of trusting PATH.
:: python.exe being on PATH doesn't guarantee its Scripts folder is too,
:: and Claude Desktop (a GUI app) can be running with a stale PATH even
:: when a freshly opened terminal already sees an updated one - so a
:: bare "audacity-mcp" command can work fine when you test it yourself
:: and still fail silently for Claude Desktop. sysconfig.get_path finds
:: the Scripts folder for the exact Python that pip just installed into,
:: regardless of what's on PATH.
set "AUDACITY_MCP_CMD=audacity-mcp"
set "PY_SCRIPTS_DIR="
for /f "delims=" %%p in ('python -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2^>nul') do set "PY_SCRIPTS_DIR=%%p"
if defined PY_SCRIPTS_DIR if exist "%PY_SCRIPTS_DIR%\audacity-mcp.exe" set "AUDACITY_MCP_CMD=%PY_SCRIPTS_DIR%\audacity-mcp.exe"
>>"%LOG_FILE%" echo Resolved audacity-mcp command: %AUDACITY_MCP_CMD%

:: -- Enable mod-script-pipe in Audacity ------------------------
echo.
echo [3/5] Enabling mod-script-pipe in Audacity...
>>"%LOG_FILE%" echo [3/5] Enabling mod-script-pipe in Audacity...

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
>>"%LOG_FILE%" echo [4/5] Configuring Claude Desktop...
echo.
echo   This step can add an "audacity" entry to Claude Desktop's config file(s)
echo   so it launches audacity-mcp automatically - no manual JSON editing needed.
echo   What it does, exactly:
echo     - Backs up any existing config file before touching it (a .bak copy)
echo     - If no config exists yet, creates one with just the audacity entry
echo     - If a config already exists, only adds or fixes the audacity entry -
echo       it never removes or changes any other MCP server you already have
echo.

set "SKIP_CLAUDE_CONFIG=0"
if "%DRY_RUN%"=="1" (
    echo   [dry-run] Would ask to configure Claude Desktop here.
) else (
    set /p CONFIGURE_CLAUDE="  Configure Claude Desktop now? (y/n): "
    if /i not "!CONFIGURE_CLAUDE!"=="y" (
        echo.
        echo   Skipped. To add it yourself later: open Claude Desktop -^> Settings -^>
        echo   Developer tab -^> Edit Config, then add the audacity entry shown in
        echo   the installation guide.
        set "SKIP_CLAUDE_CONFIG=1"
    )
)
if "%SKIP_CLAUDE_CONFIG%"=="1" goto :skip_config

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
        echo   [dry-run] Would back up: %CONFIG_FILE%
        echo   [dry-run] to: %CONFIG_FILE%.bak if a change is needed, then add or
        echo   [dry-run] fix only the "audacity" entry - every other server already
        echo   [dry-run] in the file is left untouched. Also fixes an old broken
        echo   [dry-run] "audacity-mcp" bare-command entry from a previous install.
    ) else (
        echo   [dry-run] Would create: %CONFIG_FILE%
        echo   [dry-run] with a fresh mcpServers block containing the audacity entry
    )
    exit /b
)

if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%" >nul 2>&1

if exist "%CONFIG_FILE%" copy "%CONFIG_FILE%" "%CONFIG_FILE%.bak" >nul 2>&1

:: Use Python for a real JSON parse/merge instead of text-scanning with
:: findstr - this correctly adds or fixes ONLY the "audacity" entry
:: (including upgrading an old broken bare "audacity-mcp" command left
:: over from a previous install, which can't be found if Claude Desktop's
:: process doesn't have the same PATH as a terminal) while leaving every
:: other configured MCP server completely untouched.
set "CFG_FILE=%CONFIG_FILE%"
set "AUD_CMD=%AUDACITY_MCP_CMD%"
set "MERGE_RESULT="
for /f "delims=" %%r in ('python -c "import json,os; p=os.environ['CFG_FILE']; cmd=os.environ['AUD_CMD']; data=json.load(open(p,encoding='utf-8')) if os.path.exists(p) else {}; servers=data.setdefault('mcpServers',{}); aud=servers.get('audacity'); changed = aud is None or (aud.get('command')=='audacity-mcp' and cmd!='audacity-mcp'); servers.__setitem__('audacity', {**(aud or {}),'command':cmd}) if changed else None; (changed and json.dump(data, open(p,'w',encoding='utf-8'), indent=2)); print('WROTE' if changed else 'SKIP')" 2^>nul') do set "MERGE_RESULT=%%r"

>>"%LOG_FILE%" echo %CONFIG_FILE%: %MERGE_RESULT%

if "!MERGE_RESULT!"=="WROTE" (
    echo   Configured Claude Desktop at: %CONFIG_FILE%
) else if "!MERGE_RESULT!"=="SKIP" (
    if exist "%CONFIG_FILE%.bak" del "%CONFIG_FILE%.bak" >nul 2>&1
    echo   %CONFIG_FILE%
    echo   already correctly configured - skipping.
) else (
    echo   WARNING: could not update %CONFIG_FILE% automatically.
    echo   Add this inside your "mcpServers" block by hand:
    echo.
    echo     "audacity": {
    echo       "command": "audacity-mcp"
    echo     }
    echo.
    notepad "%CONFIG_FILE%"
)
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
>>"%LOG_FILE%" echo [5/5] Done - setup complete
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
exit /b 0

:fail_exit
>>"%LOG_FILE%" echo INSTALL FAILED
echo.
echo  Full log saved to: %LOG_FILE%
echo  If this keeps happening, please report it at:
echo  https://github.com/xDarkzx/Audacity-MCP/issues
echo  (attach install-log.txt from this folder so we can see exactly what happened^)
echo.
pause
exit /b 1
