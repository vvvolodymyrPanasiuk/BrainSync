"""Vault reader: parse frontmatter and note content from .md files."""
from __future__ import annotations

from pathlib import Path

import yaml


def read_frontmatter(file_path: str) -> dict:
    """Parse YAML frontmatter between --- delimiters at top of .md file."""
    text = Path(file_path).read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    fm_block = text[3:end].strip()
    try:
        return yaml.safe_load(fm_block) or {}
    except yaml.YAMLError:
        return {}


def read_note_content(file_path: str, vault_path: str) -> str:
    """Read note body (after frontmatter block). Used for search excerpts."""
    full_path = Path(vault_path) / file_path
    text = full_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    return text[end + 3:].strip()
