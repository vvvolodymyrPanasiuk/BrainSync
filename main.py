"""BrainSync entry point: load config → build vault index → start Telegram bot.

NOTE: The VaultWriter MCP server (vault_writer/server.py) is a SEPARATE process.
It is started by external callers (e.g. Claude Code via mcp_servers.json).
MCP stdio transport owns stdin/stdout — incompatible with PTB run_polling() in the same process.
"""
from __future__ import annotations

import logging
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
    for brain_line, title_line in zip(_BRAIN, _TITLE):
        print(brain_line + "   " + title_line)
    print()


async def _ensure_infrastructure_ready(app) -> None:
    """Post-init hook: ensure Whisper model is cached; blocks until download completes."""
    import telegram.handlers.media as _media_mod

    config = app.bot_data["config"]
    model_size = config.media.transcription_model
    allowed_ids = config.telegram.allowed_user_ids

    # Check if model already cached (huggingface hub directory)
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    model_cached = any(
        p.is_dir()
        for p in cache_root.glob("*")
        if model_size in p.name
    ) if cache_root.exists() else False

    if not model_cached and allowed_ids:
        logger.info("Whisper model '%s' not found — downloading…", model_size)
        try:
            from telegram.formatter import format_model_downloading
            await app.bot.send_message(chat_id=allowed_ids[0], text=format_model_downloading())
        except Exception as exc:
            logger.warning("Could not send download notification: %s", exc)

    # Instantiate Transcriber (triggers model download if not cached — blocking I/O)
    from vault_writer.ai.transcriber import Transcriber
    import asyncio as _asyncio
    transcriber = Transcriber(model_size=model_size)
    loop = _asyncio.get_running_loop()
    await loop.run_in_executor(None, transcriber._load)  # offload blocking download

    app.bot_data["transcriber"] = transcriber
    _media_mod._READY = True
    logger.info("Whisper model ready: %s", model_size)

    if allowed_ids:
        try:
            from telegram.formatter import format_model_ready
            await app.bot.send_message(chat_id=allowed_ids[0], text=format_model_ready())
        except Exception as exc:
            logger.warning("Could not send ready notification: %s", exc)

    # Start background vault indexing (non-blocking)
    vector_store = app.bot_data.get("vector_store")
    if vector_store is not None:
        import threading
        def _build_index_background():
            try:
                count = vector_store.build_from_vault(config.vault.path, config.embedding)
                logger.info("Background vault indexing complete: %d notes", count)
            except Exception as exc:
                logger.warning("Background vault indexing failed: %s", exc)
        t = threading.Thread(target=_build_index_background, daemon=True, name="vault-indexer")
        t.start()
        logger.info("Background vault indexing started")


# ── Dashboard ─────────────────────────────────────────────────────────────────

def _hr(char: str = "─", width: int = 56) -> None:
    print(char * width)


def _dashboard(config) -> str:
    """Show status screen. Returns 'start' | 'edit' | 'details' | 'setup' | 'exit'."""
    import os

    while True:
        # Clear screen
        os.system("cls" if sys.platform == "win32" else "clear")
        _print_banner()

        _hr("═")
        print("  Current configuration")
        _hr("═")
        print()
        print(f"  Vault          {config.vault.path}")
        print(f"  AI provider    {config.ai.provider}  ({config.ai.model})")
        print(f"  Mode           {config.ai.processing_mode}")
        print(f"  Embeddings     {config.embedding.backend}  ({config.embedding.model})")
        print(f"  Telegram       {len(config.telegram.allowed_user_ids)} allowed user(s)")
        print(f"  Git sync       {'enabled' if config.git.enabled else 'disabled'}")
        print()
        _hr()
        print()
        print("  [1]  Start bot")
        print("  [2]  Edit config  (opens config.yaml)")
        print("  [3]  Full config details")
        print("  [4]  Re-run setup wizard")
        print("  [5]  Exit")
        print()
        _hr()

        choice = input("  Choose [1-5]: ").strip()
        if choice == "1":
            return "start"
        if choice == "2":
            _edit_config()
            # reload config after edit
            from config.loader import load_config
            try:
                config.__dict__.update(load_config("config.yaml").__dict__)
                print("\n  ✓ Config reloaded.")
                input("  Press Enter to continue…")
            except Exception as exc:
                print(f"\n  ❌ Config error: {exc}")
                input("  Fix config.yaml and press Enter…")
        elif choice == "3":
            _show_full_config(config)
        elif choice == "4":
            return "setup"
        elif choice == "5":
            return "exit"


def _edit_config() -> None:
    import subprocess, os
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
    import os
    os.system("cls" if sys.platform == "win32" else "clear")
    _hr("═")
    print("  Full configuration")
    _hr("═")
    print()
    # AI
    print("  ── AI ──────────────────────────────────────────")
    print(f"  provider          {config.ai.provider}")
    print(f"  model             {config.ai.model}")
    print(f"  processing_mode   {config.ai.processing_mode}")
    print(f"  ollama_url        {config.ai.ollama_url}")
    print(f"  ollama_vision     {config.ai.ollama_vision_model or '(disabled)'}")
    print(f"  max_context_tok   {config.ai.max_context_tokens}")
    print(f"  api_key           {'***' + config.ai.api_key[-6:] if config.ai.api_key else '(not set)'}")
    print()
    # Vault
    print("  ── Vault ───────────────────────────────────────")
    print(f"  path              {config.vault.path}")
    print(f"  language          {config.vault.language}")
    print()
    # Embeddings
    print("  ── Embeddings / RAG ────────────────────────────")
    print(f"  backend           {config.embedding.backend}")
    print(f"  model             {config.embedding.model}")
    print(f"  index_path        {config.embedding.index_path}")
    print(f"  top_k_results     {config.embedding.top_k_results}")
    print(f"  dup threshold     {config.embedding.similarity_duplicate_threshold}")
    print(f"  related threshold {config.embedding.similarity_related_threshold}")
    print()
    # Media
    print("  ── Media ───────────────────────────────────────")
    print(f"  voice max         {config.media.max_voice_duration_seconds}s")
    print(f"  whisper model     {config.media.transcription_model}")
    print(f"  pdf max pages     {config.media.pdf_max_pages}")
    print(f"  max file size     {config.media.max_file_size_mb} MB")
    print()
    # Telegram
    print("  ── Telegram ────────────────────────────────────")
    print(f"  allowed_user_ids  {config.telegram.allowed_user_ids}")
    print()
    # Git
    print("  ── Git sync ────────────────────────────────────")
    print(f"  enabled           {config.git.enabled}")
    print(f"  push_remote       {config.git.push_remote}")
    print(f"  push_interval     {config.git.push_interval_minutes} min")
    print()
    _hr()
    input("  Press Enter to go back…")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    config_path = "config.yaml"

    if not Path(config_path).exists():
        _print_banner()
        print("  config.yaml not found — starting setup wizard.\n")
        import subprocess
        subprocess.run([sys.executable, "setup.py"])
        if not Path(config_path).exists():
            print("Setup did not complete. Exiting.")
            sys.exit(1)

    from config.loader import SessionStats, get_ai_provider, get_embedding_provider, load_config, setup_logging
    config = load_config(config_path)

    # Dashboard loop
    action = _dashboard(config)
    if action == "exit":
        sys.exit(0)
    if action == "setup":
        import subprocess
        subprocess.run([sys.executable, "setup.py"])
        config = load_config(config_path)

    # ── Bot startup ───────────────────────────────────────────────────────────
    import os
    os.system("cls" if sys.platform == "win32" else "clear")
    _print_banner()

    setup_logging(config)
    logger.info("BrainSync starting — mode=%s provider=%s", config.ai.processing_mode, config.ai.provider)

    # Build vault index
    from vault_writer.vault.indexer import build_index
    index = build_index(config.vault.path)
    logger.info("Vault index built: %d notes, %d topics", index.total_notes, len(index.topics))

    # Init session stats
    stats = SessionStats(vault_notes_total=index.total_notes)

    # Init AI provider
    try:
        provider = get_ai_provider(config)
        logger.info("AI provider ready: %s", config.ai.provider)
    except Exception as exc:
        logger.warning("AI provider init failed: %s — running in minimal mode", exc)
        provider = None

    # Init embedding provider + vector store
    from vault_writer.rag.vector_store import VectorStore
    try:
        embedder = get_embedding_provider(config)
        vector_store = VectorStore(config.embedding.index_path, embedder)
        logger.info("VectorStore initialised at %s", config.embedding.index_path)
    except Exception as exc:
        logger.warning("VectorStore init failed: %s — RAG features disabled", exc)
        vector_store = None

    # Start Telegram bot (blocking)
    from telegram.bot import build_application
    app = build_application(config, index, stats, provider, vector_store=vector_store)
    app.post_init = _ensure_infrastructure_ready

    logger.info("Telegram bot starting — allowed_users=%s", config.telegram.allowed_user_ids)
    print(f"  Bot is running. Press Ctrl+C to stop.\n")
    _hr()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
