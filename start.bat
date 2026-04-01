@echo off
setlocal
cd /d "%~dp0"

REM ── Quick-launch: config exists + uv available → validate then run ─────────
if not exist config.yaml goto :full_setup

uv --version >nul 2>&1
if errorlevel 1 goto :full_setup

echo  Checking config...
uv run python -c "from config.loader import load_config; load_config('config.yaml')" 2>&1
if not errorlevel 1 goto :run

echo.
echo  config.yaml is incomplete or contains errors (see above).
echo  Re-running setup to fix it...
echo.
goto :do_setup

REM ── Full setup (first time or uv missing) ──────────────────────────────────
:full_setup
echo.
echo  BrainSync — First-time Setup
echo  =============================
echo.

REM ── Find Python ────────────────────────────────────────────────────────────
set PYTHON=

python --version >nul 2>&1
if not errorlevel 1 (set PYTHON=python& goto :found_python)

py --version >nul 2>&1
if not errorlevel 1 (set PYTHON=py& goto :found_python)

python3 --version >nul 2>&1
if not errorlevel 1 (set PYTHON=python3& goto :found_python)

echo  ERROR: Python not found.
echo.
echo  Please install Python 3.12+ from: https://python.org/downloads
echo  During installation, check "Add Python to PATH".
echo.
echo  After installing, close this window and run start.bat again.
pause
exit /b 1

:found_python
for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do set PY_VER=%%v
echo  Found: %PY_VER%

REM ── Install uv ─────────────────────────────────────────────────────────────
uv --version >nul 2>&1
if not errorlevel 1 goto :found_uv

echo  Installing uv package manager...
%PYTHON% -m pip install uv --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install uv.
    echo  Try running manually: %PYTHON% -m pip install uv
    pause
    exit /b 1
)
echo  uv installed.

:found_uv
REM ── Install dependencies ───────────────────────────────────────────────────
echo  Installing dependencies...
uv sync
if errorlevel 1 (
    echo.
    echo  ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo  Dependencies ready.
echo.

REM ── Interactive setup (creates config.yaml) ────────────────────────────────
:do_setup
uv run python setup.py
if errorlevel 1 (
    echo.
    echo  Setup did not complete. Run start.bat again to retry,
    echo  or edit config.yaml manually.
    pause
    exit /b 1
)

echo.
echo  Setup complete! Launching BrainSync...
echo.

REM ── Launch ─────────────────────────────────────────────────────────────────
:run
uv run python main.py
if errorlevel 1 (
    echo.
    echo  BrainSync exited with an error.
    echo  Check the output above, then press any key to close.
    pause >nul
)
