#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo ""
echo " BrainSync Installer"
echo " ==================="
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo " ERROR: Python 3 not found."
    echo " Install Python 3.12+ from https://python.org/downloads"
    exit 1
fi

# ── Install uv if missing ──────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo " Installing uv package manager..."
    pip3 install uv --quiet
    echo " uv installed."
fi

# ── Install dependencies ───────────────────────────────────────────────────────
echo " Installing dependencies..."
uv sync --quiet
echo " Dependencies ready."

# ── Run interactive setup ──────────────────────────────────────────────────────
echo ""
uv run python setup.py

echo ""
echo " Done! Run ./start.sh to launch BrainSync."
echo ""
