#!/usr/bin/env bash
# BrainSync launcher — macOS / Linux
set -euo pipefail
cd "$(dirname "$0")"

_hr()  { printf '%0.s─' {1..54}; echo; }
_ok()  { echo "  ✓ $1"; }
_err() { echo "  ERROR: $1" >&2; exit 1; }

echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║          BrainSync               ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# ── Python ────────────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1)
        PYTHON="$cmd"
        _ok "Found: $ver"
        break
    fi
done
[ -z "$PYTHON" ] && _err "Python 3.12+ not found. Install from https://python.org/downloads"

# ── uv ────────────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "  Installing uv..."
    "$PYTHON" -m pip install uv --quiet || _err "Failed to install uv. Run: pip install uv"
    _ok "uv installed"
fi

# ── Dependencies ──────────────────────────────────────────────────────────────
echo "  Checking dependencies..."
uv sync --quiet || _err "uv sync failed. Check your internet connection."
_ok "Dependencies ready"

# ── First-time setup or config validation ─────────────────────────────────────
if [ ! -f config.yaml ]; then
    echo ""
    echo "  First-time setup"
    _hr
    uv run python setup.py || _err "Setup did not complete. Run ./start.sh again to retry."
else
    if ! uv run python -c "from config.loader import load_config; load_config('config.yaml')" 2>/dev/null; then
        echo "  config.yaml has errors — re-running setup..."
        uv run python setup.py || _err "Setup did not complete."
    fi
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""
echo "  Starting BrainSync..."
echo ""
_hr
uv run python main.py
EXIT=$?
_hr
if [ $EXIT -ne 0 ]; then
    echo "  BrainSync exited with error (code $EXIT)."
    echo "  Scroll up to read the error message."
    exit $EXIT
else
    echo "  BrainSync stopped."
fi
