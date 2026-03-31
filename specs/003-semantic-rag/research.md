# Research: BrainSync Semantic Search & RAG

**Branch**: `003-semantic-rag` | **Date**: 2026-03-31

---

## 1. Embedding Backend — Decision

### Decision
Two supported backends, both local:
- **`sentence-transformers`** — pure Python, no external service required
- **Ollama embeddings** — via existing Ollama REST API (`/api/embeddings`)

Anthropic has no native embeddings endpoint (they use Voyage AI separately — a paid external service that violates Constitution Principle I). Therefore "Anthropic backend" is replaced by `sentence-transformers` for the offline-first case.

### Rationale
- `sentence-transformers` installs via pip, downloads model from HuggingFace on first run (~120 MB for `paraphrase-multilingual-MiniLM-L12-v2`), runs entirely on CPU — zero external API calls.
- Ollama already runs locally as part of the v1.1 setup; its `/api/embeddings` endpoint is a natural second backend for users who already have Ollama configured.
- Both options respect Constitution Principle I (local-first) and Principle III (provider abstraction).

### Alternatives Considered
| Option | Rejected Because |
|--------|-----------------|
| Anthropic embeddings | No native endpoint; Voyage AI is a paid external service — violates local-first |
| OpenAI embeddings | External API, paid, violates local-first |
| FAISS | No built-in persistence; requires custom serialization; more complex |
| sqlite-vec | SQLite extension, requires compiled binary — harder to install on Windows |

### Recommended Model: `paraphrase-multilingual-MiniLM-L12-v2`
| Property | Value |
|----------|-------|
| Disk size | ~120 MB |
| Vector dimensions | 384 |
| Languages | 50+ including Ukrainian and English |
| Speed (CPU) | ~50ms per note on modern CPU |
| Quality | Good for semantic similarity; not SOTA but sufficient for personal vault |

### API Usage

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
embedding = model.encode("що я думав про продуктивність?")  # numpy array, shape (384,)
```

### Ollama Embeddings API

```python
import requests

response = requests.post(
    "http://localhost:11434/api/embeddings",
    json={"model": "nomic-embed-text", "prompt": "текст нотатки"},
    timeout=30,
)
embedding = response.json()["embedding"]  # list of floats
```

Recommended Ollama embedding model: `nomic-embed-text` (768 dims, multilingual, fast).

---

## 2. Vector Store — Decision

### Decision
**ChromaDB** (embedded mode, no server).

### Rationale
- Pure Python (`pip install chromadb`) — no compiled extensions, works on Windows
- Embedded mode: data persisted to a local directory (`data/chroma/`) — survives restarts automatically
- Built-in cosine similarity search with top-K retrieval
- Metadata filtering (e.g. filter by folder, note type)
- Incremental upserts — add/update individual notes without full rebuild
- Active maintenance, well-documented

### API Usage

```python
import chromadb

client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_or_create_collection(
    name="vault_notes",
    metadata={"hnsw:space": "cosine"},
)

# Upsert a note
collection.upsert(
    ids=["Architecture/0004 CQRS pattern.md"],
    embeddings=[[0.1, 0.2, ...]],
    documents=["CQRS separates read and write models..."],
    metadatas=[{"folder": "Architecture", "type": "note", "hash": "abc123"}],
)

# Query
results = collection.query(
    query_embeddings=[[0.1, 0.2, ...]],
    n_results=5,
    include=["documents", "metadatas", "distances"],
)
```

### Content Hash for Change Detection
Each note stores a SHA-256 hash of its content. On index update, hash is compared — unchanged notes are skipped (O(1) per note, no re-embedding needed).

---

## 3. Intent Detection — Decision

### Decision
Single AI call using the existing `AIProvider.complete()` interface — classify the user message as `rag_query`, `search_query`, or `new_note`.

### Rationale
- Reuses existing `AIProvider` abstraction (Constitution Principle III)
- One AI call per message — within the spirit of `minimal` mode (intent detection replaces classification when RAG is triggered)
- More robust than keyword rules for Ukrainian natural language

### Prompt Design

```python
INTENT_PROMPT = """Classify this Telegram message as one of:
- "rag_query": user is asking a question about their existing notes/knowledge
- "search_query": user explicitly wants to find/list notes on a topic
- "new_note": user is sharing a new thought, idea, task, or information to save

Message: "{message}"

Reply with ONLY one of: rag_query, search_query, new_note"""
```

### Classification Rules (examples)
| Message | Intent |
|---------|--------|
| "що я думав про CQRS?" | rag_query |
| "як я вирішував проблему X?" | rag_query |
| "знайди нотатки про продуктивність" | search_query |
| "покажи все про Redis" | search_query |
| "купив книгу про архітектуру" | new_note |
| "задача: зателефонувати лікарю" | new_note |

---

## 4. RAG Answer Generation — Decision

### Decision
Single AI call with retrieved context injected into prompt. Answer grounded exclusively in vault content.

### Prompt Design

```python
RAG_PROMPT = """Ти асистент, який відповідає ВИКЛЮЧНО на основі нотаток з особистого vault користувача.
НЕ використовуй загальні знання — тільки наведені нотатки.
Якщо відповідь відсутня у нотатках — скажи "Не знайдено у vault".

Питання: {query}

Релевантні нотатки:
{context}

Дай відповідь з посиланнями на нотатки у форматі: (→ Назва нотатки)"""
```

Context format per note:
```
[Нотатка: Architecture/0004 CQRS pattern.md]
CQRS розділяє read і write моделі...
```

---

## 5. Deduplication Thresholds — Decision

ChromaDB returns cosine distance (0 = identical, 2 = opposite). Similarity = 1 - distance.

| Similarity | Cosine Distance | Action |
|------------|----------------|--------|
| ≥ 0.85 | ≤ 0.15 | Duplicate warning |
| 0.70–0.84 | 0.16–0.30 | Related note suggestion |
| < 0.70 | > 0.30 | No notice |

Self-match (same note just saved) is excluded by filtering on file path.

---

## 6. New Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `chromadb` | Vector store with persistence | `pip install chromadb` |
| `sentence-transformers` | Local embedding model | `pip install sentence-transformers` |
| `torch` (CPU) | Required by sentence-transformers | auto-installed |

Ollama embeddings backend uses `requests` (already present as transitive dep).

**Total new disk footprint**: ~120 MB model + ~50 MB ChromaDB + ~500 MB torch CPU = ~670 MB first install.

---

## 7. Startup Sequence

1. Load ChromaDB collection from `data/chroma/`
2. Scan vault for notes not yet in index (by file path + hash check)
3. Embed missing/changed notes in background thread (non-blocking)
4. Set `_INDEX_READY = True` when complete
5. While building: search works on partial index (returns best available results)
