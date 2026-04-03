"""Vault structure manager — tracks folder hierarchy in _vault_structure.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_STRUCTURE_FILE = "_vault_structure.json"


def load_structure(vault_path: str) -> dict:
    """Load vault folder hierarchy. Returns empty dict if file missing/invalid."""
    path = Path(vault_path) / _STRUCTURE_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("load_structure: %s", exc)
        return {}


def save_structure(vault_path: str, structure: dict) -> None:
    path = Path(vault_path) / _STRUCTURE_FILE
    try:
        path.write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("save_structure: %s", exc)


def register_folder(vault_path: str, folder_path: str) -> None:
    """Add folder_path (slash-separated, e.g. 'Навчання/Програмування/Python') to structure."""
    structure = load_structure(vault_path)
    parts = [p for p in folder_path.split("/") if p]
    node = structure
    changed = False
    for part in parts:
        if part not in node:
            node[part] = {}
            changed = True
        node = node[part]
    if changed:
        save_structure(vault_path, structure)


def get_structure_hint(vault_path: str) -> str:
    """Format vault folder tree as indented bullet list for AI prompt."""
    structure = load_structure(vault_path)
    if not structure:
        return "No existing structure yet."
    lines: list[str] = []
    _format_tree(structure, lines, 0)
    return "\n".join(lines)


def _format_tree(node: dict, lines: list, depth: int) -> None:
    indent = "  " * depth
    for key in sorted(node):
        lines.append(f"{indent}- {key}/")
        if node[key]:
            _format_tree(node[key], lines, depth + 1)
