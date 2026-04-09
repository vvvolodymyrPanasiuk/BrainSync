@echo off
chcp 65001 > nul 2>&1
title BrainSync Bot
cd /d "%~dp0"

uv run python bot_runner.py

echo.
if errorlevel 1 (
    echo  ══════════════════════════════════════════════
    echo  BrainSync crashed. Scroll up to read the error.
    echo  ══════════════════════════════════════════════
) else (
    echo  BrainSync stopped normally.
)
echo.
echo  Press any key to close this window...
pause >nul
