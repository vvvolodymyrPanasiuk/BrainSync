@echo off
setlocal
cd /d "%~dp0"

REM ── If already configured, just run ────────────────────────────────────────
if exist config.yaml goto :launch

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

REM ── Interactive setup (creates config.yaml) ────────────────────────────────
echo.
uv run python setup.py
if errorlevel 1 (
    echo.
    echo  Setup did not complete. Run start.bat again to retry.
    pause
    exit /b 1
)

echo.
echo  Setup complete! Launching BrainSync...
echo.

REM ── Launch ─────────────────────────────────────────────────────────────────
:launch
uv run python main.py
if errorlevel 1 (
    echo.
    echo  BrainSync exited with an error.
    echo  Check the output above, then press any key to close.
    pause >nul
)
