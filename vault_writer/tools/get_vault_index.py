"""get_vault_index MCP tool handler."""
from __future__ import annotations

from vault_writer.vault.indexer import VaultIndex


def handle_get_vault_index(index: VaultIndex) -> dict:
    """Return vault index snapshot per contracts/mcp-tools.md."""
    return {
        "total_notes": index.total_notes,
        "topics": index.topics,
        "tags": sorted(index.tags),
        "mocs": index.mocs,
        "last_updated": index.last_updated.isoformat() if index.last_updated else None,
    }
