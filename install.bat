@echo off
setlocal
cd /d "%~dp0"

echo.
echo  BrainSync Installer
echo  ===================
echo.

REM ── Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found.
    echo  Install Python 3.12+ from https://python.org/downloads
    echo  Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM ── Install uv if missing ──────────────────────────────────────────────────
uv --version >nul 2>&1
if errorlevel 1 (
    echo  Installing uv package manager...
    pip install uv --quiet
    if errorlevel 1 (
        echo  ERROR: Failed to install uv. Check your internet connection.
        pause
        exit /b 1
    )
    echo  uv installed.
)

REM ── Install dependencies ───────────────────────────────────────────────────
echo  Installing dependencies...
uv sync --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo  Dependencies ready.

REM ── Run interactive setup ──────────────────────────────────────────────────
echo.
uv run python setup.py
if errorlevel 1 (
    echo.
    echo  Setup did not complete. Run install.bat again or edit config.yaml manually.
    pause
    exit /b 1
)

echo.
echo  Done! Run start.bat to launch BrainSync.
echo.
pause
