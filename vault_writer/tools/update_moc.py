"""update_moc MCP tool handler."""
from __future__ import annotations

from vault_writer.vault.writer import update_moc


def handle_update_moc(moc_path: str, note_path: str, vault_path: str,
                      note_title: str = "", note_number: int = 0) -> dict:
    """Update MoC file with new wikilink. Wikilink is derived from note_path filename."""
    update_moc(moc_path, note_path, vault_path)
    return {"success": True, "moc_path": moc_path}
