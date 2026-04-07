"""Semantic wikilink injector: AI extracts key terms → vault search → inject [[links]].

Flow:
  1. AI extracts named concepts + aliases from note content
  2. Synonym registry is updated and loaded for term augmentation
  3. Each term is matched against vault via title lookup then vector search
  4. Matched notes are linked inline (first occurrence) AND in ## Посилання
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Minimum vector similarity to accept a semantic match
_VECTOR_THRESHOLD = 0.72

# Maximum wikilinks to inject per note (to avoid noise)
_MAX_LINKS = 8

# Minimum alias length to use in search/replacement (avoids "EF", "DB" etc false matches)
_MIN_ALIAS_LEN = 3


def enrich_with_links(
    content: str,
    vault_index,
    vector_store,
    provider,
    config,
    exclude_path: str = "",
) -> str:
    """Extract key terms from content, find matching vault notes, inject [[wikilinks]].

    Adds [[Note Title]] both inline (first occurrence of each term/alias)
    and in the ## Посилання footer section.
    """
    if not content.strip() or provider is None:
        return content

    # Step 1: AI extracts named concepts + their aliases/synonyms
    terms = _extract_terms(content, provider)
    if not terms:
        logger.debug("linker: no terms extracted")
        return content
    logger.debug("linker: extracted %d terms: %s", len(terms), [t.get("term") for t in terms])

    # Step 2: Persist synonyms for future runs
    registry_path = Path(config.vault.path) / ".brainsync" / "synonyms.json"
    _update_registry(registry_path, terms)
    registry = _load_registry(registry_path)

    # Step 3: Match each term to a vault note
    found_links: list[tuple[str, str, list[str]]] = []   # (note_title, note_path, all_aliases)
    seen_paths: set[str] = set()
    if exclude_path:
        seen_paths.add(exclude_path)

    for term_info in terms:
        if len(found_links) >= _MAX_LINKS:
            break

        term = term_info.get("term", "").strip()
        if not term:
            continue

        ai_aliases = [a for a in term_info.get("aliases", []) if a]
        registry_aliases = registry.get(term.lower(), [])
        all_aliases: list[str] = list(dict.fromkeys(
            [term] + ai_aliases + registry_aliases   # deduplicated, insertion-ordered
        ))

        # Title match first (fast, no AI call)
        matched = _find_by_title(all_aliases, vault_index)

        # Semantic vector search as fallback
        if matched is None and vector_store is not None:
            matched = _find_by_vector(term, vector_store, vault_index)

        if matched:
            note_title, note_path = matched
            if note_path not in seen_paths:
                seen_paths.add(note_path)
                found_links.append((note_title, note_path, all_aliases))

    if not found_links:
        logger.debug("linker: no matching notes found")
        return content

    logger.info("linker: injecting %d wikilinks", len(found_links))

    # Step 4: Inject inline (first occurrence of term/alias in body)
    result = _inject_inline(content, found_links)

    # Step 5: Append to ## Посилання footer
    result = _inject_footer(result, found_links)

    return result


# ── Term extraction ───────────────────────────────────────────────────────────

def _extract_terms(content: str, provider) -> list[dict]:
    """Ask AI to identify linkable named concepts and their aliases."""
    prompt = (
        "You are an Obsidian knowledge graph assistant.\n"
        "Extract named concepts from the text that are worth cross-linking in a personal vault.\n\n"
        "INCLUDE:\n"
        "- Technology names, frameworks, libraries, tools (e.g. EntityFrameworkCore, Redis, pytest)\n"
        "- Programming languages, platforms, standards (e.g. Python, REST, OAuth2)\n"
        "- Proper nouns: companies, projects, people, products\n"
        "- Specific methodologies or named concepts (e.g. SOLID, CQRS, Zettelkasten)\n"
        "- Scientific or domain terms (e.g. дофамін, маржа, HIIT)\n\n"
        "EXCLUDE:\n"
        "- Common everyday words (молоко, будинок, погода)\n"
        "- Generic verbs and adjectives (зробити, великий, важливий)\n"
        "- Vague concepts without a specific name (проблема, ідея, план)\n"
        "- Pronouns, prepositions, articles\n\n"
        "For each term, list ALL common aliases and abbreviations you know.\n\n"
        "Return ONLY a valid JSON array, no explanation:\n"
        '[{"term": "EntityFrameworkCore", "aliases": ["EF Core", "EFCore", "Entity Framework", "EF"]}]\n\n'
        f"Text:\n{content[:2500]}"
    )
    try:
        raw = provider.complete(prompt, max_tokens=700)
        # Strip thinking blocks (Qwen3, DeepSeek)
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        json_start = raw.find("[")
        json_end = raw.rfind("]") + 1
        if json_start == -1 or json_end <= json_start:
            logger.debug("linker: no JSON array in extraction response")
            return []
        data = json.loads(raw[json_start:json_end])
        return [d for d in data if isinstance(d, dict) and d.get("term")]
    except Exception as exc:
        logger.warning("linker: _extract_terms failed: %s", exc)
        return []


# ── Vault matching ────────────────────────────────────────────────────────────

def _find_by_title(aliases: list[str], vault_index) -> tuple[str, str] | None:
    """Case-insensitive title match: alias == note title OR alias is contained in title."""
    alias_lower = {a.lower() for a in aliases if len(a) >= _MIN_ALIAS_LEN}
    if not alias_lower:
        return None
    for path, note in vault_index.notes.items():
        title_lower = note.title.lower()
        for alias in alias_lower:
            # Exact match
            if alias == title_lower:
                return (note.title, path)
            # Alias is a significant substring of the title (and long enough)
            if len(alias) >= 4 and alias in title_lower:
                return (note.title, path)
            # Title is contained within alias (e.g. alias="EntityFrameworkCore", title="EFCore")
            if len(title_lower) >= 4 and title_lower in alias:
                return (note.title, path)
    return None


def _find_by_vector(term: str, vector_store, vault_index) -> tuple[str, str] | None:
    """Semantic search: find the most similar note to the term."""
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
    """Replace the first occurrence of each term/alias in the body with [[Title|alias]].

    Skips: existing [[wikilinks]], code blocks, section headers.
    """
    # Split frontmatter out to avoid linking inside YAML
    body, frontmatter = _split_frontmatter(content)

    # Build a set of ranges that are already inside [[ ]] to avoid double-linking
    result = body
    for note_title, _path, aliases in links:
        # Try each alias from longest to shortest (avoids partial-word false positives)
        candidates = sorted(
            (a for a in aliases if len(a) >= _MIN_ALIAS_LEN),
            key=len,
            reverse=True,
        )
        for alias in candidates:
            # Pattern: word boundary, not already inside [[ ]] or Markdown link syntax
            pattern = (
                r'(?<!\[)'          # not preceded by [
                r'(?<!\|)'          # not preceded by | (already inside [[X|...]])
                r'\b(' + re.escape(alias) + r')\b'
                r'(?!\])'           # not followed by ]
                r'(?!\()'           # not followed by ( (Markdown link)
            )
            replacement = f'[[{note_title}|{alias}]]'
            new_result = re.sub(pattern, replacement, result, count=1, flags=re.IGNORECASE)
            if new_result != result:
                result = new_result
                break  # only one inline link per note

    return (frontmatter + result) if frontmatter else result


def _inject_footer(content: str, links: list[tuple[str, str, list[str]]]) -> str:
    """Append [[Note Title]] entries to ## Посилання section (deduplicated)."""
    links_section = "## Посилання"

    # Collect titles not already present in content
    new_entries: list[str] = []
    for note_title, _path, _aliases in links:
        link_text = f"- [[{note_title}]]"
        if link_text not in content:
            new_entries.append(link_text)

    if not new_entries:
        return content

    new_links_block = "\n".join(new_entries)

    if links_section in content:
        idx = content.index(links_section) + len(links_section)
        newline_idx = content.find("\n", idx)
        if newline_idx == -1:
            return content + "\n" + new_links_block
        return content[:newline_idx + 1] + new_links_block + "\n" + content[newline_idx + 1:]

    return content + f"\n\n{links_section}\n\n{new_links_block}\n"


# ── Synonym registry ──────────────────────────────────────────────────────────

def _update_registry(registry_path: Path, terms: list[dict]) -> None:
    """Merge newly discovered aliases into the persistent synonym registry."""
    registry = _load_registry(registry_path)
    changed = False
    for item in terms:
        term_key = item.get("term", "").lower()
        new_aliases = [a.lower() for a in item.get("aliases", []) if a]
        if term_key and new_aliases:
            existing = set(registry.get(term_key, []))
            merged = existing | set(new_aliases)
            if merged != existing:
                registry[term_key] = sorted(merged)
                changed = True
    if changed:
        try:
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            logger.debug("linker: synonym registry updated (%d terms)", len(registry))
        except Exception as exc:
            logger.warning("linker: could not save synonym registry: %s", exc)


def _load_registry(registry_path: Path) -> dict[str, list[str]]:
    """Load synonym registry from disk. Returns {} on any error."""
    try:
        if registry_path.exists():
            return json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("linker: registry load failed: %s", exc)
    return {}


# ── Retroactive linking ──────────────────────────────────────────────────────

# Short words that are too generic to use as search anchors
_GENERIC_WORDS = frozenset({
    "і", "й", "в", "у", "на", "з", "що", "як", "до", "це", "не", "та",
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of",
    "by", "is", "are", "was", "with", "from",
    # generic nouns that appear in many note titles
    "нотатки", "notes", "basics", "guide", "intro", "основи", "вступ",
    "overview", "study", "навчання", "learning",
})


def retrolink_to_new_note(
    new_note_title: str,
    new_note_path: str,
    vault_path: str,
    vault_index,
    config,
) -> int:
    """After a new note is written, scan existing vault notes for unlinked mentions
    of the new note's title / known aliases and inject [[new_note_title|mention]] links.

    Example: when 'SQLite Basics' is created, every existing note that says
    'SQLite' gets '[[SQLite Basics|SQLite]]' injected automatically.

    Returns the number of notes updated.
    """
    registry_path = Path(vault_path) / ".brainsync" / "synonyms.json"
    registry = _load_registry(registry_path)

    # Build search terms from significant title words + registry aliases
    title_words = [
        w for w in re.findall(r"\w+", new_note_title)
        if w.lower() not in _GENERIC_WORDS and len(w) >= _MIN_ALIAS_LEN
    ]

    search_terms: list[str] = list(dict.fromkeys(
        [new_note_title]
        + title_words
        + [alias for word in title_words for alias in registry.get(word.lower(), [])]
    ))
    search_terms = [t for t in search_terms if len(t) >= _MIN_ALIAS_LEN]

    if not search_terms:
        return 0

    vault = Path(vault_path)
    updated = 0
    _MAX_RETROLINK_UPDATES = 30  # safety cap per note creation

    for note_path, _note in list(vault_index.notes.items()):
        if updated >= _MAX_RETROLINK_UPDATES:
            break
        if note_path == new_note_path:
            continue

        full_path = vault / note_path
        if not full_path.exists():
            continue

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Fast check: any term appears in content but is NOT already a wikilink?
        unlinked_term: str | None = None
        for term in search_terms:
            # Matches the term as a whole word, NOT already inside [[ ]]
            pattern = r'(?<!\[)(?<!\|)\b' + re.escape(term) + r'\b(?!\])'
            if re.search(pattern, content, re.IGNORECASE):
                unlinked_term = term
                break

        if unlinked_term is None:
            continue

        # Inject inline link + footer entry
        new_content = _inject_inline(content, [(new_note_title, new_note_path, search_terms)])
        new_content = _inject_footer(new_content, [(new_note_title, new_note_path, search_terms)])

        if new_content == content:
            continue

        try:
            full_path.write_text(new_content, encoding="utf-8")
            logger.info(
                "retrolink: %s ← [[%s]] (matched %r)",
                note_path, new_note_title, unlinked_term,
            )
            updated += 1
        except Exception as exc:
            logger.warning("retrolink: could not write %s: %s", note_path, exc)

    if updated:
        logger.info(
            "retrolink: injected [[%s]] into %d existing note(s)", new_note_title, updated
        )
    return updated


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_frontmatter(content: str) -> tuple[str, str]:
    """Returns (body, frontmatter). Frontmatter is '' if none found."""
    if not content.startswith("---"):
        return content, ""
    end = content.find("---", 3)
    if end == -1:
        return content, ""
    fm_end = end + 3
    return content[fm_end:], content[:fm_end]
