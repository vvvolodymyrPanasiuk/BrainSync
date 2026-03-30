@echo off
cd /d "%~dp0"

uv run python main.py
if errorlevel 1 (
    echo.
    echo  BrainSync exited with an error.
    echo  Check the output above, then press any key to close.
    pause >nul
)
