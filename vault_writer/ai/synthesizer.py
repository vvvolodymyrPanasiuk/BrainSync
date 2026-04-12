"""LLM-Wiki synthesis engine: topic summaries, contradiction detection, staleness, novelty scoring."""
from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_MIN_NOTES_FOR_SYNTHESIS = 3   # synthesize only when folder has >= N notes
_SYNTHESIS_LOCK: set[str] = set()  # paths currently being synthesized (dedup)
_SYNTHESIS_SET_LOCK = threading.Lock()


# ── Topic synthesis ───────────────────────────────────────────────────────────

def synthesize_topic_moc(
    topic_folder: str,
    vault_path: str,
    provider,
) -> bool:
    """Read all notes in topic_folder/_data/, synthesize key insights, update MoC ## Synthesis section.

    Returns True if MoC was updated.  Thread-safe — deduplicates concurrent runs per folder.
    """
    if provider is None:
        return False

    with _SYNTHESIS_SET_LOCK:
        if topic_folder in _SYNTHESIS_LOCK:
            return False
        _SYNTHESIS_LOCK.add(topic_folder)

    try:
        return _do_synthesize(topic_folder, vault_path, provider)
    finally:
        with _SYNTHESIS_SET_LOCK:
            _SYNTHESIS_LOCK.discard(topic_folder)


def _do_synthesize(topic_folder: str, vault_path: str, provider) -> bool:
    vault = Path(vault_path)
    data_dir = vault / topic_folder / "_data"
    if not data_dir.exists():
        data_dir = vault / topic_folder

    note_files = sorted(data_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[:20]
    if len(note_files) < _MIN_NOTES_FOR_SYNTHESIS:
        return False

    notes_text: list[str] = []
    for fp in note_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    content = content[end + 3:]
            notes_text.append(f"### {fp.stem}\n{content[:700]}")
        except Exception:
            continue

    if len(notes_text) < _MIN_NOTES_FOR_SYNTHESIS:
        return False

    topic_name = topic_folder.split("/")[-1]
    combined = "\n\n".join(notes_text)

    prompt = (
        f"You are maintaining a personal knowledge wiki about '{topic_name}'.\n"
        f"Below are {len(notes_text)} notes from this topic.\n\n"
        f"{combined}\n\n"
        "Write a concise synthesis (4-7 bullet points) that:\n"
        "1. Captures the key insights and conclusions across all notes\n"
        "2. Identifies patterns and connections between notes\n"
        "3. Highlights the most important knowledge in this topic\n\n"
        "Format: markdown bullet list. No preamble. Write in the same language as the notes."
    )

    try:
        synthesis = provider.complete(prompt, max_tokens=700)
        if not synthesis or not synthesis.strip():
            return False
        synthesis = re.sub(r"<think>.*?</think>", "", synthesis, flags=re.DOTALL).strip()
    except Exception as exc:
        logger.warning("synthesizer: AI call failed for '%s': %s", topic_name, exc)
        return False

    moc_file = vault / topic_folder / f"0 {topic_name}.md"
    if not moc_file.exists():
        return False

    try:
        moc_content = moc_file.read_text(encoding="utf-8")
        synthesis_block = f"### Synthesis\n\n{synthesis}\n\n"

        if "### Synthesis" in moc_content:
            moc_content = re.sub(
                r"### Synthesis\n\n.*?(?=\n##|\Z)",
                synthesis_block.rstrip("\n"),
                moc_content,
                flags=re.DOTALL,
            )
        else:
            marker = "## Опис"
            if marker in moc_content:
                idx = moc_content.index(marker) + len(marker)
                nl = moc_content.find("\n", idx)
                insert_at = (nl + 1) if nl != -1 else len(moc_content)
                moc_content = moc_content[:insert_at] + "\n" + synthesis_block + moc_content[insert_at:]
            else:
                moc_content += "\n\n## Опис\n\n" + synthesis_block

        moc_file.write_text(moc_content, encoding="utf-8")
        logger.info("synthesizer: updated '%s' MoC synthesis (%d notes)", topic_name, len(notes_text))
        return True
    except Exception as exc:
        logger.warning("synthesizer: MoC write failed for '%s': %s", topic_name, exc)
        return False


def synthesize_topic_background(topic_folder: str, vault_path: str, provider) -> None:
    """Trigger topic synthesis in a daemon thread so it does not block the caller."""
    t = threading.Thread(
        target=synthesize_topic_moc,
        args=(topic_folder, vault_path, provider),
        daemon=True,
        name=f"synth-{topic_folder}",
    )
    t.start()


# ── Contradiction detection ───────────────────────────────────────────────────

def check_contradictions(
    topic_folder: str,
    vault_path: str,
    provider,
) -> list[dict]:
    """Scan notes in topic_folder for semantic contradictions between factual claims.

    Returns list of dicts: {note_a, note_b, claim_a, claim_b, summary}
    """
    if provider is None:
        return []

    vault = Path(vault_path)
    data_dir = vault / topic_folder / "_data"
    if not data_dir.exists():
        data_dir = vault / topic_folder

    note_files = sorted(data_dir.glob("*.md"))[:8]
    if len(note_files) < 2:
        return []

    notes_text: list[str] = []
    note_names: list[str] = []
    for fp in note_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    content = content[end + 3:]
            notes_text.append(content[:600])
            note_names.append(fp.stem)
        except Exception:
            continue

    if len(notes_text) < 2:
        return []

    numbered = "\n\n".join(
        f"[{i+1}] {name}:\n{text}"
        for i, (name, text) in enumerate(zip(note_names, notes_text))
    )

    prompt = (
        "Analyze these notes for SEMANTIC CONTRADICTIONS — cases where notes make directly conflicting factual claims.\n"
        "Ignore: differences in tone, perspective, or date of writing. Only flag direct factual conflicts.\n\n"
        f"{numbered}\n\n"
        'Return a JSON array. Each item: {"note_a": "name", "note_b": "name", "claim_a": "short claim", '
        '"claim_b": "conflicting claim", "summary": "one-line description"}\n'
        "If no contradictions: return []\n"
        "Return ONLY the JSON array."
    )

    try:
        raw = provider.complete(prompt, max_tokens=800)
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        j_start = raw.find("[")
        j_end = raw.rfind("]") + 1
        if j_start == -1 or j_end <= j_start:
            return []
        results = json.loads(raw[j_start:j_end])
        return [r for r in results if isinstance(r, dict) and r.get("note_a") and r.get("note_b")]
    except Exception as exc:
        logger.warning("synthesizer: contradiction check failed for '%s': %s", topic_folder, exc)
        return []


def check_all_contradictions(vault_index, vault_path: str, provider, top_n: int = 5) -> list[dict]:
    """Run contradiction check on the N largest topic folders.

    Returns list of contradiction dicts extended with a 'folder' key.
    """
    if provider is None:
        return []

    from collections import Counter
    folder_counts: Counter = Counter(
        note.folder.split("/")[0] for note in vault_index.notes.values() if note.folder
    )
    top_folders = [f for f, _ in folder_counts.most_common(top_n)]

    all_contradictions: list[dict] = []
    for folder in top_folders:
        contras = check_contradictions(folder, vault_path, provider)
        for c in contras:
            c["folder"] = folder
        all_contradictions.extend(contras)

    return all_contradictions


# ── Staleness detection ───────────────────────────────────────────────────────

def check_staleness(vault_index, days: int = 180) -> list[str]:
    """Return vault-relative paths of notes created more than *days* ago.

    Uses the 'date' field from the vault index (note creation date).
    """
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    stale: list[str] = []
    for path, note in vault_index.notes.items():
        try:
            if date.fromisoformat(note.date) < cutoff:
                stale.append(path)
        except Exception:
            continue
    return stale


# ── Novelty scoring ───────────────────────────────────────────────────────────

def score_novelty(answer: str, source_chunks: list[str], provider) -> float:
    """Return 0.0–1.0: how much new insight does this answer add beyond the raw vault sources?

    0.0 = answer just restates sources; 1.0 = significant synthesis / new connections.
    Returns 0.5 (show button) on any error so the user never loses the save option.
    """
    if provider is None or not answer.strip() or not source_chunks:
        return 0.0

    sources_preview = "\n---\n".join(s[:300] for s in source_chunks[:3])

    prompt = (
        "Does this ANSWER meaningfully synthesize, connect, or extend the SOURCES — or just rephrase them?\n"
        "Reply with a single integer 0-10:\n"
        "0 = pure copy / trivial rephrasing\n"
        "5 = moderate synthesis\n"
        "10 = significant new insight or connections not in sources\n\n"
        f"SOURCES:\n{sources_preview}\n\n"
        f"ANSWER:\n{answer[:600]}\n\n"
        "Reply with only the integer (0-10):"
    )

    try:
        raw = provider.complete(prompt, max_tokens=5)
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        m = re.search(r"\d+", raw)
        if m:
            return min(1.0, max(0.0, int(m.group()) / 10.0))
    except Exception as exc:
        logger.debug("synthesizer: novelty score error: %s", exc)
    return 0.5
