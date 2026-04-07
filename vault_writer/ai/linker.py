"""Semantic wikilink injector: AI extracts key terms → vault search → inject [[links]].

Flow for a new note:
  1. AI extracts named concepts + aliases from note content
  2. Synonym registry (.brainsync/synonyms.json) is updated and loaded
  3. Each term is matched against vault via token-based title lookup → vector fallback
  4. Matched notes linked inline (first prose occurrence) AND in ## Посилання
  5. Inverted index (.brainsync/word_index.json) is updated for future retrolinks
  6. retrolink_to_new_note() finds existing notes mentioning the new note's title/aliases
     using the inverted index (O(1) lookup instead of full vault scan)
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_VECTOR_THRESHOLD = 0.72   # minimum cosine similarity for vector match
_MAX_LINKS = 8             # max wikilinks injected per note
_MIN_ALIAS_LEN = 3         # minimum alias length to use in search/replacement
_MAX_RETROLINK = 30        # max existing notes updated per creation


# Module-level inverted index cache: vault_path → word_dict
_inv_cache: dict[str, dict[str, list[str]]] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def enrich_with_links(
    content: str,
    vault_index,
    vector_store,
    provider,
    config,
    exclude_path: str = "",
) -> str:
    """Extract key terms from content, find matching vault notes, inject [[wikilinks]].

    Adds [[Note Title]] both inline (first prose occurrence) and in ## Посилання.
    """
    if not content.strip() or provider is None:
        return content

    terms = _extract_terms(content, provider)
    if not terms:
        logger.debug("linker: no terms extracted")
        return content

    registry_path = Path(config.vault.path) / ".brainsync" / "synonyms.json"
    _update_registry(registry_path, terms)
    registry = _load_registry(registry_path)

    found: list[tuple[str, str, list[str]]] = []   # (note_title, note_path, aliases)
    seen: set[str] = set()
    if exclude_path:
        seen.add(exclude_path)

    for term_info in terms:
        if len(found) >= _MAX_LINKS:
            break
        term = term_info.get("term", "").strip()
        if not term:
            continue
        all_aliases: list[str] = list(dict.fromkeys(
            [term]
            + term_info.get("aliases", [])
            + _load_registry(registry_path).get(term.lower(), [])
        ))
        matched = _find_by_title(all_aliases, vault_index)
        if matched is None and vector_store is not None:
            matched = _find_by_vector(term, vector_store, vault_index)
        if matched:
            note_title, note_path = matched
            if note_path not in seen:
                seen.add(note_path)
                found.append((note_title, note_path, all_aliases))
                # Update matched note's frontmatter aliases with newly discovered synonyms
                _update_note_aliases(note_path, config.vault.path, all_aliases)

    if not found:
        return content

    logger.info("linker: injecting %d wikilinks", len(found))
    result = _inject_inline(content, found)
    result = _inject_footer(result, found)
    return result


def update_inverted_index(note_path: str, content: str, vault_path: str) -> None:
    """Index all significant words from note_path.

    Called every time a note is written so the index stays current.
    """
    inv = _load_inv(vault_path)
    words = {
        w.lower() for w in re.findall(r"\w+", content)
        if len(w) >= _MIN_ALIAS_LEN
    }
    changed = False
    for word in words:
        paths = inv.setdefault(word, [])
        if note_path not in paths:
            paths.append(note_path)
            changed = True
    if changed:
        _save_inv(vault_path, inv)


def retrolink_to_new_note(
    new_note_title: str,
    new_note_path: str,
    vault_path: str,
    vault_index,
    config,
) -> int:
    """After a new note is saved, find existing notes that mention its title/aliases
    but don't have a wikilink yet, and inject [[new_note_title|mention]] into them.

    Uses the inverted index for O(1) candidate lookup instead of a full vault scan.
    Falls back to full scan once to build the index if it is empty.

    Returns the number of notes updated.
    """
    registry_path = Path(vault_path) / ".brainsync" / "synonyms.json"
    registry = _load_registry(registry_path)

    # Build search terms: significant title words + their registry aliases
    title_words = [
        w for w in re.findall(r"\w+", new_note_title)
        if len(w) >= _MIN_ALIAS_LEN
    ]
    search_terms: list[str] = list(dict.fromkeys(
        [new_note_title]
        + title_words
        + [alias for w in title_words for alias in registry.get(w.lower(), [])]
    ))
    search_terms = [t for t in search_terms if len(t) >= _MIN_ALIAS_LEN]
    if not search_terms:
        return 0

    inv = _load_inv(vault_path)

    # First run: inverted index is empty → build it once from existing vault
    if not inv and vault_index:
        logger.info("linker: building initial inverted index from vault…")
        inv = _build_initial_inv(vault_path, vault_index)

    # Candidate paths: only notes the index says contain one of our terms
    candidates: set[str] = set()
    for term in search_terms:
        candidates.update(inv.get(term.lower(), []))
    candidates.discard(new_note_path)

    if not candidates:
        return 0

    vault = Path(vault_path)
    updated = 0

    for note_path in candidates:
        if updated >= _MAX_RETROLINK:
            break
        full_path = vault / note_path
        if not full_path.exists():
            continue
        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Verify: term actually appears unlinked in the file
        unlinked = None
        for term in search_terms:
            pat = r'(?<!\[)(?<!\|)\b' + re.escape(term) + r'\b(?!\])(?!\()'
            if re.search(pat, content, re.IGNORECASE):
                unlinked = term
                break
        if not unlinked:
            continue

        new_content = _inject_inline(content, [(new_note_title, new_note_path, search_terms)])
        new_content = _inject_footer(new_content, [(new_note_title, new_note_path, search_terms)])
        if new_content == content:
            continue

        try:
            full_path.write_text(new_content, encoding="utf-8")
            logger.info("retrolink: %s ← [[%s]] (matched %r)", note_path, new_note_title, unlinked)
            updated += 1
        except Exception as exc:
            logger.warning("retrolink: write failed %s: %s", note_path, exc)

    if updated:
        logger.info("retrolink: updated %d note(s) with [[%s]]", updated, new_note_title)
    return updated


# ── Term extraction ───────────────────────────────────────────────────────────

def _extract_terms(content: str, provider) -> list[dict]:
    """Ask AI to identify linkable named concepts and their aliases."""
    prompt = (
        "You are an Obsidian knowledge graph assistant.\n"
        "Extract named concepts from the text that are worth cross-linking in a personal vault.\n\n"
        "INCLUDE: technology names, frameworks, libraries, tools, programming languages, "
        "platforms, standards, proper nouns (companies, projects, people, products), "
        "specific named methodologies, scientific or domain terms.\n\n"
        "EXCLUDE: common everyday words, generic verbs, basic adjectives, food items, "
        "vague concepts without a specific name (problem, idea, plan, thing).\n\n"
        "For each term list ALL common aliases and abbreviations you know.\n\n"
        "Return ONLY a valid JSON array, no explanation:\n"
        '[{"term": "EntityFrameworkCore", "aliases": ["EF Core", "EFCore", "EF"]}]\n\n'
        f"Text:\n{content[:2500]}"
    )
    try:
        raw = provider.complete(prompt, max_tokens=700)
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        j_start = raw.find("[")
        j_end = raw.rfind("]") + 1
        if j_start == -1 or j_end <= j_start:
            return []
        return [d for d in json.loads(raw[j_start:j_end]) if isinstance(d, dict) and d.get("term")]
    except Exception as exc:
        logger.warning("linker: _extract_terms failed: %s", exc)
        return []


# ── Vault matching ────────────────────────────────────────────────────────────

def _find_by_title(aliases: list[str], vault_index) -> tuple[str, str] | None:
    """Token-based title match: avoids substring false-positives like 'EF' → 'EntityFramework'.

    Rules:
    - Exact full-string match → always accepted
    - Multi-token alias (≥2 words): all tokens must be in the title's token set
    - Single-token alias (≥4 chars): token must be an exact word in the title
    """
    for path, note in vault_index.notes.items():
        title_lower = note.title.lower()
        title_tokens = set(re.findall(r"\w+", title_lower))

        for alias in aliases:
            alias_lower = alias.lower().strip()
            if not alias_lower:
                continue
            alias_tokens = set(re.findall(r"\w+", alias_lower))
            if not alias_tokens:
                continue

            # Exact full match
            if alias_lower == title_lower:
                return (note.title, path)

            # Multi-word alias: require all tokens in title
            if len(alias_tokens) >= 2 and alias_tokens.issubset(title_tokens):
                return (note.title, path)

            # Single-word alias: must be a whole token AND long enough to be specific
            if len(alias_tokens) == 1:
                token = next(iter(alias_tokens))
                if len(token) >= 4 and token in title_tokens:
                    return (note.title, path)
    return None


def _find_by_vector(term: str, vector_store, vault_index) -> tuple[str, str] | None:
    """Semantic vector search: returns best match above similarity threshold."""
    try:
        results = vector_store.search(term, top_k=1)
        if not results:
            return None
        top = results[0]
        similarity = getattr(top, "similarity", 0.0)
        path = getattr(top, "file_path", None) or getattr(top, "path", None)
        if path and similarity >= _VECTOR_THRESHOLD:
            note = vault_index.notes.get(path)
            title = note.title if note else Path(path).stem
            logger.debug("linker: vector match %r → %r (%.2f)", term, title, similarity)
            return (title, path)
    except Exception as exc:
        logger.warning("linker: vector search failed for %r: %s", term, exc)
    return None


# ── Link injection ────────────────────────────────────────────────────────────

def _inject_inline(content: str, links: list[tuple[str, str, list[str]]]) -> str:
    """Replace first unlinked prose occurrence of each term/alias with [[Title|alias]].

    Protected zones (never modified):
    - YAML frontmatter
    - Fenced code blocks  ```...```
    - Inline code  `...`
    - Markdown heading lines  ## ...
    - Existing wikilinks  [[...]]
    """
    body, frontmatter = _split_frontmatter(content)

    result = body
    for note_title, _path, aliases in links:
        candidates = sorted(
            (a for a in aliases if len(a) >= _MIN_ALIAS_LEN),
            key=len,
            reverse=True,
        )
        for alias in candidates:
            pattern = (
                r'(?<!\[)'           # not preceded by [
                r'(?<!\|)'           # not preceded by | (inside wikilink)
                r'\b(' + re.escape(alias) + r')\b'
                r'(?!\])'            # not followed by ]
                r'(?!\()'            # not followed by ( (Markdown link)
            )
            new_result = _replace_first_in_prose(
                result, pattern, f'[[{note_title}|{alias}]]'
            )
            if new_result != result:
                result = new_result
                break   # one inline link per matched note

    return (frontmatter + result) if frontmatter else result


def _replace_first_in_prose(text: str, pattern: str, replacement: str) -> str:
    """Replace the first regex match that is NOT inside a code block or heading line."""
    # re.split with a capturing group gives alternating [prose, code, prose, code, ...]
    # Odd-indexed segments are code spans/blocks — leave them untouched.
    segments = re.split(r'(```[\s\S]*?```|`[^`\n]+`)', text)

    replaced = False
    result_parts: list[str] = []

    for i, segment in enumerate(segments):
        if replaced or i % 2 == 1:
            # Code block/span or already replaced → preserve as-is
            result_parts.append(segment)
            continue

        # Prose segment: process line by line, skip heading lines
        lines = segment.split("\n")
        new_lines: list[str] = []
        for line in lines:
            if not replaced and not re.match(r"^\s*#{1,6}\s", line):
                new_line = re.sub(pattern, replacement, line, count=1, flags=re.IGNORECASE)
                if new_line != line:
                    replaced = True
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        result_parts.append("\n".join(new_lines))

    return "".join(result_parts)


def _inject_footer(content: str, links: list[tuple[str, str, list[str]]]) -> str:
    """Append [[Note Title]] entries to ## Посилання (deduplicated)."""
    new_entries = [
        f"- [[{title}]]"
        for title, _, _ in links
        if f"- [[{title}]]" not in content
    ]
    if not new_entries:
        return content

    block = "\n".join(new_entries)
    marker = "## Посилання"
    if marker in content:
        idx = content.index(marker) + len(marker)
        nl = content.find("\n", idx)
        if nl == -1:
            return content + "\n" + block
        return content[:nl + 1] + block + "\n" + content[nl + 1:]
    return content + f"\n\n{marker}\n\n{block}\n"


# ── Synonym registry ──────────────────────────────────────────────────────────

def _update_registry(registry_path: Path, terms: list[dict]) -> None:
    """Merge newly discovered term aliases into the persistent synonym registry."""
    registry = _load_registry(registry_path)
    changed = False
    for item in terms:
        key = item.get("term", "").lower().strip()
        new_aliases = [a.lower().strip() for a in item.get("aliases", []) if a]
        if key and new_aliases:
            existing = set(registry.get(key, []))
            merged = existing | set(new_aliases)
            if merged != existing:
                registry[key] = sorted(merged)
                changed = True
    if changed:
        try:
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("linker: registry save failed: %s", exc)


def _load_registry(registry_path: Path) -> dict[str, list[str]]:
    """Load synonym registry, normalising all keys to lowercase."""
    try:
        if registry_path.exists():
            raw = json.loads(registry_path.read_text(encoding="utf-8"))
            return {k.lower(): v for k, v in raw.items()}
    except Exception as exc:
        logger.debug("linker: registry load failed: %s", exc)
    return {}


# ── Inverted index ────────────────────────────────────────────────────────────

_INV_FILE = ".brainsync/word_index.json"


def _load_inv(vault_path: str) -> dict[str, list[str]]:
    """Load inverted index from module cache → disk. Returns mutable dict."""
    if vault_path in _inv_cache:
        return _inv_cache[vault_path]
    path = Path(vault_path) / _INV_FILE
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            _inv_cache[vault_path] = data
            return data
    except Exception as exc:
        logger.debug("linker: inverted index load failed: %s", exc)
    _inv_cache[vault_path] = {}
    return _inv_cache[vault_path]


def _save_inv(vault_path: str, data: dict) -> None:
    """Persist inverted index to disk and update cache."""
    path = Path(vault_path) / _INV_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        _inv_cache[vault_path] = data
    except Exception as exc:
        logger.warning("linker: inverted index save failed: %s", exc)


def _build_initial_inv(vault_path: str, vault_index) -> dict[str, list[str]]:
    """One-time full vault scan to build the inverted index from existing notes."""
    vault = Path(vault_path)
    inv: dict[str, list[str]] = {}
    count = 0
    for note_path in vault_index.notes:
        fp = vault / note_path
        if not fp.exists():
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        words = {
            w.lower() for w in re.findall(r"\w+", content)
            if len(w) >= _MIN_ALIAS_LEN
        }
        for word in words:
            inv.setdefault(word, []).append(note_path)
        count += 1
    _save_inv(vault_path, inv)
    logger.info("linker: initial inverted index built (%d words, %d notes)", len(inv), count)
    return inv


# ── Alias frontmatter updater ─────────────────────────────────────────────────

def _update_note_aliases(note_path: str, vault_path: str, new_aliases: list[str]) -> None:
    """Add new_aliases to the note's frontmatter `aliases:` list (deduplicates, no-op if nothing new)."""
    full_path = Path(vault_path) / note_path
    if not full_path.exists():
        return
    try:
        content = full_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return
        end = content.find("---", 3)
        if end == -1:
            return
        fm_text = content[3:end]
        body = content[end + 3:]

        # Parse existing aliases: handles  aliases: [a, b, c]  (inline list)
        alias_match = re.search(r'^aliases:\s*\[([^\]]*)\]', fm_text, re.MULTILINE)
        if not alias_match:
            return  # no aliases field — skip rather than mutate structure unexpectedly

        existing_raw = alias_match.group(1)
        existing: list[str] = [
            a.strip().strip('"').strip("'")
            for a in existing_raw.split(",")
            if a.strip()
        ]
        existing_lower = {a.lower() for a in existing}

        additions = [
            a for a in new_aliases
            if len(a) >= _MIN_ALIAS_LEN and a.lower() not in existing_lower
        ]
        if not additions:
            return

        merged = existing + additions
        aliases_str = ", ".join(f'"{a}"' for a in merged)
        new_fm_text = re.sub(
            r'^aliases:\s*\[[^\]]*\]',
            f'aliases: [{aliases_str}]',
            fm_text,
            flags=re.MULTILINE,
        )
        if new_fm_text == fm_text:
            return

        full_path.write_text(f"---{new_fm_text}---{body}", encoding="utf-8")
        logger.debug("linker: aliases updated in %s: +%s", note_path, additions)
    except Exception as exc:
        logger.warning("linker: _update_note_aliases failed for %s: %s", note_path, exc)


# ── Utilities ─────────────────────────────────────────────────────────────────

def _split_frontmatter(content: str) -> tuple[str, str]:
    """Return (body, frontmatter_block). Frontmatter is '' if none found."""
    if not content.startswith("---"):
        return content, ""
    end = content.find("---", 3)
    if end == -1:
        return content, ""
    fm_end = end + 3
    return content[fm_end:], content[:fm_end]
