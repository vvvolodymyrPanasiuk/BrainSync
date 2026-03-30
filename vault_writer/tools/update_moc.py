"""update_moc MCP tool handler."""
from __future__ import annotations

from vault_writer.vault.writer import update_moc


def handle_update_moc(moc_path: str, note_path: str, note_title: str, note_number: int, vault_path: str) -> dict:
    """Update MoC file with new wikilink per contracts/mcp-tools.md."""
    update_moc(moc_path, note_path, note_title, note_number, vault_path)
    return {"success": True, "moc_path": moc_path}
