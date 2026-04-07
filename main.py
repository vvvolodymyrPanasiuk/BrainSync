"""BrainSync dashboard — manages the bot subprocess.

The bot itself runs in bot_runner.py (separate console window).
The VaultWriter MCP server (vault_writer/server.py) is also a separate process.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Banner ────────────────────────────────────────────────────────────────────

_BRAIN = [
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠀⢀⣀⣀⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⢀⣤⣶⣿⣿⣿⣆⠘⠿⠟⢻⣿⣿⡇⢐⣷⣦⣄⡀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⢸⣿⣿⣿⣧⡄⠙⣿⣷⣶⣶⡿⠿⠿⢃⣼⡟⠻⣿⣿⣶⡄⠀⠀⠀⠀",
    "⠀⠀⢰⣷⣌⠙⠉⣿⣿⡟⢀⣿⣿⡟⢁⣤⣤⣶⣾⣿⡇⠸⢿⣿⠿⢃⣴⡄⠀⠀",
    "⠀⠀⢸⣿⣿⣿⣿⠿⠋⣠⣾⣿⣿⠀⣾⣿⣿⣛⠛⢿⣿⣶⣤⣤⣴⣿⣿⣿⡆⠀",
    "⠀⣴⣤⣄⣀⣠⣤⣴⣾⣿⣿⣿⣿⣆⠘⠿⣿⣿⣷⡄⢹⣿⣿⠿⠟⢿⣿⣿⣿⠀",
    "⠀⢸⣿⣿⡿⠛⠛⣻⣿⣿⣿⣿⣿⣿⣷⣦⣼⣿⣿⠃⣸⣿⠃⢰⣶⣾⣿⣿⡟⠀",
    "⠀⠀⢿⡏⢠⣾⣿⣿⡿⠋⣠⣄⡉⢻⣿⣿⡿⠟⠁⠀⠛⠛⠀⠘⠿⠿⠿⠋⠀⠀",
    "⠀⠀⠀⠁⠘⢿⣿⣿⣷⣤⣿⣿⠗⠀⣉⣥⣴⣶⡶⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⣤⣀⡉⠛⠛⠋⣉⣠⣴⠿⢿⣿⠿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠈⠻⢿⣿⣿⣿⣿⡿⠋⣠⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤⡾⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
]

_TITLE = [
    "",
    "██████╗ ██████╗  █████╗ ██╗███╗  ██╗",
    "██╔══██╗██╔══██╗██╔══██╗██║████╗ ██║",
    "██████╔╝██████╔╝███████║██║██╔██╗██║",
    "██╔══██╗██╔══██╗██╔══██║██║██║╚████║",
    "██████╔╝██║  ██║██║  ██║██║██║ ╚███║",
    "╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚══╝",
    "",
    "███████╗██╗   ██╗███╗  ██╗ ██████╗ ",
    "██╔════╝╚██╗ ██╔╝████╗ ██║██╔════╝ ",
    "███████╗ ╚████╔╝ ██╔██╗██║██║      ",
    "╚════██║  ╚██╔╝  ██║╚████║██║      ",
    "███████║   ██║   ██║ ╚███║╚██████╗ ",
    "╚══════╝   ╚═╝   ╚═╝  ╚══╝ ╚═════╝ ",
    "",
]


def _print_banner() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    for brain_line, title_line in zip(_BRAIN, _TITLE):
        try:
            print(brain_line + "   " + title_line)
        except UnicodeEncodeError:
            print(" " * 30 + "   " + title_line)
    print()


# ── Bot subprocess management ─────────────────────────────────────────────────

def _start_bot() -> subprocess.Popen:
    """Launch bot_runner.py in a new console window."""
    cmd = ["uv", "run", "python", "bot_runner.py"]
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(cmd, creationflags=flags)


def _stop_bot(proc: subprocess.Popen) -> None:
    """Gracefully stop the bot subprocess (CTRL_BREAK → terminate → kill)."""
    if proc.poll() is not None:
        return  # already exited
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=8)
    except (subprocess.TimeoutExpired, OSError):
        proc.kill()
        proc.wait()


# ── Dashboard ─────────────────────────────────────────────────────────────────

def _hr(char: str = "─", width: int = 56) -> None:
    print(char * width)


def _dashboard(config) -> str:
    """Dashboard loop. Manages bot subprocess. Returns 'setup' or 'exit'."""
    bot_proc: subprocess.Popen | None = None

    while True:
        os.system("cls" if sys.platform == "win32" else "clear")
        _print_banner()

        bot_running = bot_proc is not None and bot_proc.poll() is None

        _hr("═")
        print("  Current configuration")
        _hr("═")
        print()
        print(f"  Vault          {config.vault.path}")
        print(f"  AI provider    {config.ai.provider}  ({config.ai.model})")
        print(f"  Embeddings     {config.embedding.backend}  ({config.embedding.model})")
        print(f"  Telegram       {len(config.telegram.allowed_user_ids)} allowed user(s)")
        print(f"  Git sync       {'enabled' if config.git.enabled else 'disabled'}")
        print(f"  Locale         {config.locale}")
        print()

        status_line = "  Status:  🟢 Bot is running" if bot_running else "  Status:  ⚫ Bot is stopped"
        try:
            print(status_line)
        except UnicodeEncodeError:
            print("  Status:  [running]" if bot_running else "  Status:  [stopped]")

        _hr()
        print()
        if bot_running:
            print("  [1]  Stop bot")
        else:
            print("  [1]  Start bot")
        print("  [2]  Edit config  (opens config.yaml)")
        print("  [3]  Full config details")
        print("  [4]  Re-run setup wizard")
        print("  [5]  Exit")
        print()
        _hr()

        choice = input("  Choose [1-5]: ").strip()

        if choice == "1":
            if bot_running:
                print("\n  Stopping bot…")
                _stop_bot(bot_proc)
                bot_proc = None
                print("  Bot stopped.")
                input("  Press Enter to continue…")
            else:
                bot_proc = _start_bot()
                print("\n  Bot started in a new window.")
                input("  Press Enter to continue…")

        elif choice == "2":
            _edit_config()
            from config.loader import load_config
            try:
                config.__dict__.update(load_config("config.yaml").__dict__)
                print("\n  Config reloaded.")
                input("  Press Enter to continue…")
            except Exception as exc:
                print(f"\n  Config error: {exc}")
                input("  Fix config.yaml and press Enter…")

        elif choice == "3":
            _show_full_config(config)

        elif choice == "4":
            if bot_running:
                print("\n  Stopping bot before setup…")
                _stop_bot(bot_proc)
                bot_proc = None
            return "setup"

        elif choice == "5":
            if bot_running:
                print("\n  Stopping bot…")
                _stop_bot(bot_proc)
                bot_proc = None
            return "exit"


def _edit_config() -> None:
    cfg = Path("config.yaml")
    if sys.platform == "win32":
        os.startfile(str(cfg))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(cfg)])
    else:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(cfg)])
    input("\n  Edit config.yaml, save, then press Enter to reload…")


def _show_full_config(config) -> None:
    os.system("cls" if sys.platform == "win32" else "clear")
    _hr("═")
    print("  Full configuration")
    _hr("═")
    print()
    print("  ── AI ──────────────────────────────────────────")
    print(f"  provider          {config.ai.provider}")
    print(f"  model             {config.ai.model}")
    print(f"  ollama_url        {config.ai.ollama_url}")
    print(f"  ollama_vision     {config.ai.ollama_vision_model or '(disabled)'}")
    print(f"  max_context_tok   {config.ai.max_context_tokens}")
    print(f"  api_key           {'***' + config.ai.api_key[-6:] if config.ai.api_key else '(not set)'}")
    print()
    print("  ── Vault ───────────────────────────────────────")
    print(f"  path              {config.vault.path}")
    print(f"  language          {config.vault.language}")
    print()
    print("  ── Embeddings / RAG ────────────────────────────")
    print(f"  backend           {config.embedding.backend}")
    print(f"  model             {config.embedding.model}")
    print(f"  index_path        {config.embedding.index_path}")
    print(f"  top_k_results     {config.embedding.top_k_results}")
    print(f"  dup threshold     {config.embedding.similarity_duplicate_threshold}")
    print(f"  related threshold {config.embedding.similarity_related_threshold}")
    print()
    print("  ── Media ───────────────────────────────────────")
    print(f"  voice max         {config.media.max_voice_duration_seconds}s")
    print(f"  whisper model     {config.media.transcription_model}")
    print(f"  pdf max pages     {config.media.pdf_max_pages}")
    print(f"  max file size     {config.media.max_file_size_mb} MB")
    print()
    print("  ── Telegram ────────────────────────────────────")
    print(f"  allowed_user_ids  {config.telegram.allowed_user_ids}")
    print()
    print("  ── Git sync ────────────────────────────────────")
    print(f"  enabled           {config.git.enabled}")
    print(f"  push_remote       {config.git.push_remote}")
    print(f"  push_interval     {config.git.push_interval_minutes} min")
    print()
    print("  ── Localisation ────────────────────────────────")
    print(f"  locale            {config.locale}")
    print()
    _hr()
    input("  Press Enter to go back…")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    config_path = "config.yaml"

    if not Path(config_path).exists():
        _print_banner()
        print("  config.yaml not found — starting setup wizard.\n")
        subprocess.run([sys.executable, "setup.py"])
        if not Path(config_path).exists():
            print("Setup did not complete. Exiting.")
            sys.exit(1)

    from config.loader import load_config, setup_logging
    config = load_config(config_path)
    setup_logging(config)

    action = _dashboard(config)

    if action == "setup":
        subprocess.run([sys.executable, "setup.py"])
        # Re-enter dashboard with fresh config
        config = load_config(config_path)
        main()
        return

    sys.exit(0)


if __name__ == "__main__":
    main()
