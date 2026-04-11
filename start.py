#!/usr/bin/env python3
"""Universal BrainSync launcher — Windows, macOS, Linux."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

PYTHON = sys.executable
IS_WIN = sys.platform == "win32"
NULL = "nul" if IS_WIN else "/dev/null"


def _run(cmd: str, quiet: bool = False) -> int:
    if quiet:
        cmd += f" >{NULL} 2>&1"
    return subprocess.run(cmd, shell=True).returncode


def _step(msg: str) -> None:
    print(f"\n  {msg}")


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _err(msg: str) -> None:
    print(f"\n  ERROR: {msg}", file=sys.stderr)


# ── Ensure uv ────────────────────────────────────────────────────────────────

def _ensure_uv() -> None:
    if _run("uv --version", quiet=True) == 0:
        return
    _step("uv not found — installing...")
    if _run(f'"{PYTHON}" -m pip install uv --quiet') != 0:
        _err("Failed to install uv. Run manually: pip install uv")
        sys.exit(1)
    _ok("uv installed")


# ── Sync dependencies ─────────────────────────────────────────────────────────

def _sync_deps() -> None:
    _step("Checking dependencies...")
    if _run("uv sync --quiet") != 0:
        _err("uv sync failed. Check your internet connection.")
        sys.exit(1)
    _ok("Dependencies ready")


# ── First-time setup ──────────────────────────────────────────────────────────

def _maybe_setup() -> None:
    config = ROOT / "config.yaml"
    if config.exists():
        # Validate existing config
        result = subprocess.run(
            "uv run python -c \"from config.loader import load_config; load_config('config.yaml')\"",
            shell=True, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return
        print("\n  config.yaml has errors:")
        print(result.stderr.strip())
        print("\n  Re-running setup to fix...\n")

    _step("First-time setup")
    if _run("uv run python setup.py") != 0:
        _err("Setup did not complete. Run 'python start.py' again to retry.")
        sys.exit(1)


# ── Launch ────────────────────────────────────────────────────────────────────

def _launch() -> None:
    print("\n  Starting BrainSync...\n")
    print("  " + "─" * 52)
    code = _run("uv run python main.py")
    print("\n  " + "─" * 52)
    if code != 0:
        print(f"\n  BrainSync exited with error (code {code}).")
        print("  Scroll up to read the error message.")
        if IS_WIN:
            input("\n  Press Enter to close...")
    else:
        print("\n  BrainSync stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("  ╔══════════════════════════════════╗")
    print("  ║          BrainSync               ║")
    print("  ╚══════════════════════════════════╝")

    _ensure_uv()
    _sync_deps()
    _maybe_setup()
    _launch()
