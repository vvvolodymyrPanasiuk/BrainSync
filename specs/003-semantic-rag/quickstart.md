# Quickstart: BrainSync Semantic Search & RAG (v1.2)

**Branch**: `003-semantic-rag` | **Date**: 2026-03-31

---

## Prerequisites

- BrainSync v1.1 fully configured and running
- ~670 MB free disk space (sentence-transformers model + torch + ChromaDB)

---

## New Dependencies

```bat
pip install chromadb sentence-transformers
```

> `sentence-transformers` downloads the multilingual model (~120 MB) on first bot start.
> This is a one-time operation. The bot indexes your vault in the background — it remains responsive immediately.

### Optional: Ollama embedding backend

If you prefer to use Ollama for embeddings (no extra pip install needed):

```bash
ollama pull nomic-embed-text
```

---

## Config Changes

Add to your existing `config.yaml`:

```yaml
embedding:
  backend: "sentence-transformers"          # or "ollama"
  model: "paraphrase-multilingual-MiniLM-L12-v2"  # ignored if backend=ollama
  ollama_embed_url: "http://localhost:11434" # only used if backend=ollama
  index_path: "data/chroma"                 # where ChromaDB stores vectors
  similarity_duplicate_threshold: 0.85
  similarity_related_threshold: 0.70
  top_k_results: 5
```

---

## How It Works

### Asking questions about your vault

Just send a question naturally — no command needed:

```
Що я думав про CQRS?
Як я вирішував проблему кешування?
Розкажи мені про мої думки щодо продуктивності
```

The bot detects the intent automatically and answers using only your notes, with citations.

### Semantic search

```
/search управління часом
знайди нотатки про архітектуру мікросервісів
```

Returns ranked results — finds notes even when exact words don't match.

### Duplicate detection

Happens automatically after every note save. If a similar note exists:

```
✓ Збережено → General/0012 productivity hacks.md

⚠️ Схожа нотатка вже існує:
→ General/0008 deep work notes.md (91%)
```

### Manual reindex

If you added notes directly in Obsidian (outside the bot):

```
/reindex
```

---

## Validation Checklist

- [ ] `pip show chromadb sentence-transformers` — both installed
- [ ] `config.yaml` has `embedding:` block with all fields
- [ ] Start bot → background indexing begins (no blocking message)
- [ ] Send `/reindex` → bot replies "✅ Переіндексовано: N нотаток."
- [ ] Ask "що я думав про X?" → bot replies with answer citing actual notes
- [ ] `/search Y` where Y is concept not literally in any note → returns semantic matches
- [ ] Save a note that's similar to an existing one → duplicate notice appears
- [ ] Stop and restart bot → first query works immediately (no rebuild wait)
- [ ] Set `backend: "ollama"` with `nomic-embed-text` pulled → same behavior fully offline

---

## `.gitignore` Addition

The vector index contains embeddings of your personal vault content — keep it local:

```
data/chroma/
```
