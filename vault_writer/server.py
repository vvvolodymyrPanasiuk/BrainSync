"""VaultWriter MCP server — standalone stdio process.

Run as standalone:
    python vault_writer/server.py

Register in Claude Code (.claude/mcp_servers.json):
    {
      "mcpServers": {
        "vault-writer": {
          "command": "python",
          "args": ["C:/Projects/BrainSync/vault_writer/server.py"]
        }
      }
    }

NOTE: This is intentionally a SEPARATE process from main.py (Telegram bot).
MCP stdio transport owns stdin/stdout and cannot run in the same process as PTB.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as standalone script
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("vault-writer")

# Lazy-loaded shared state (initialised once at startup)
_config = None
_index = None
_provider = None


def _get_shared_state():
    global _config, _index, _provider
    if _config is None:
        config_path = os.environ.get("BRAINSYNC_CONFIG", str(_root / "config.yaml"))
        from config.loader import get_ai_provider, load_config, setup_logging
        _config = load_config(config_path)
        setup_logging(_config)
        from vault_writer.vault.indexer import build_index
        _index = build_index(_config.vault.path)
        try:
            _provider = get_ai_provider(_config)
        except Exception:
            _provider = None
    return _config, _index, _provider


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_note",
            description="Create a new note in the Obsidian vault. Classifies, formats, and saves the note.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Raw note content"},
                    "type": {"type": "string", "enum": ["note", "task", "idea", "journal"], "description": "Note type (optional)"},
                    "folder": {"type": "string", "description": "Target folder (optional)"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="get_vault_index",
            description="Return a snapshot of the current vault index (topics, tags, note count).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="search_notes",
            description="Full-text search across vault notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                    "folder": {"type": "string"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="classify_content",
            description="Classify raw text and return note type, folder, and title.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        ),
        Tool(
            name="update_moc",
            description="Update a Map of Content file with a new wikilink.",
            inputSchema={
                "type": "object",
                "properties": {
                    "moc_path": {"type": "string"},
                    "note_path": {"type": "string"},
                    "note_title": {"type": "string"},
                    "note_number": {"type": "integer"},
                },
                "required": ["moc_path", "note_path", "note_title", "note_number"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    config, index, provider = _get_shared_state()
    from config.loader import SessionStats

    if name == "create_note":
        from vault_writer.tools.create_note import handle_create_note
        from vault_writer.vault.writer import NoteType
        type_str = arguments.get("type")
        note_type = NoteType(type_str) if type_str else None
        stats = SessionStats()
        result = handle_create_note(
            text=arguments["text"],
            type_=note_type,
            folder=arguments.get("folder"),
            config=config,
            index=index,
            stats=stats,
            provider=provider,
        )
        return [TextContent(type="text", text=json.dumps(result))]

    if name == "get_vault_index":
        from vault_writer.tools.get_vault_index import handle_get_vault_index
        return [TextContent(type="text", text=json.dumps(handle_get_vault_index(index)))]

    if name == "search_notes":
        from vault_writer.tools.search_notes import handle_search_notes
        result = handle_search_notes(
            query=arguments["query"],
            limit=arguments.get("limit", 10),
            folder=arguments.get("folder"),
            index=index,
            vault_path=config.vault.path,
        )
        return [TextContent(type="text", text=json.dumps(result))]

    if name == "classify_content":
        from vault_writer.tools.classify_content import handle_classify_content
        result = handle_classify_content(arguments["text"], provider, index, config)
        return [TextContent(type="text", text=json.dumps(result))]

    if name == "update_moc":
        from vault_writer.vault.writer import update_moc as _update_moc
        _update_moc(
            arguments["moc_path"],
            arguments["note_path"],
            arguments["note_title"],
            arguments["note_number"],
            config.vault.path,
        )
        return [TextContent(type="text", text=json.dumps({"success": True}))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
