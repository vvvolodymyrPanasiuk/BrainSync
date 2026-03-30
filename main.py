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


def main() -> None:
    config_path = "config.yaml"
    if not Path(config_path).exists():
        print(f"ERROR: {config_path} not found. Run python setup.py first.")
        sys.exit(1)

    from config.loader import SessionStats, get_ai_provider, load_config, setup_logging
    config = load_config(config_path)
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

    # Start Telegram bot (blocking)
    from telegram.bot import build_application
    app = build_application(config, index, stats, provider)
    logger.info("Telegram bot starting — allowed_users=%s", config.telegram.allowed_user_ids)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
