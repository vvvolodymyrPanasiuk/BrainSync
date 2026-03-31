# Data Model: BrainSync Semantic Search & RAG

**Branch**: `003-semantic-rag` | **Date**: 2026-03-31

---

## New Dataclasses

### `EmbeddingConfig` (in `config/loader.py`)

```python
@dataclass
class EmbeddingConfig:
    backend: str = "sentence-transformers"   # "sentence-transformers" | "ollama"
    model: str = "paraphrase-multilingual-MiniLM-L12-v2"  # or "nomic-embed-text" for ollama
    ollama_embed_url: str = "http://localhost:11434"
    index_path: str = "data/chroma"          # ChromaDB persistence directory
    similarity_duplicate_threshold: float = 0.85
    similarity_related_threshold: float = 0.70
    top_k_results: int = 5                   # max results returned for search/RAG
```

Added to `AppConfig` as `embedding: EmbeddingConfig`.

---

### `IntentType` (in `vault_writer/rag/intent.py`)

```python
class IntentType(str, Enum):
    RAG_QUERY    = "rag_query"     # "що я думав про X?"
    SEARCH_QUERY = "search_query"  # "знайди нотатки про X"
    NEW_NOTE     = "new_note"      # default: save as note
```

---

### `RAGResult` (in `vault_writer/rag/engine.py`)

```python
@dataclass
class RAGResult:
    answer: str                     # synthesized answer (or "not found" message)
    sources: list[str]              # file paths of cited notes
    query: str                      # original user query
    found: bool                     # False if vault had no relevant notes
```

---

### `SearchResult` (in `vault_writer/rag/engine.py`)

```python
@dataclass
class SearchResult:
    file_path: str
    excerpt: str
    similarity: float               # 0.0–1.0
```

---

### `SimilarityNotice` (in `vault_writer/rag/engine.py`)

```python
@dataclass
class SimilarityNotice:
    matched_path: str
    similarity: float
    is_duplicate: bool              # True if >= duplicate_threshold
```

---

## New Files / Modules

### `vault_writer/rag/__init__.py`
Package marker.

### `vault_writer/rag/embedder.py`
`EmbeddingProvider` abstract base + two concrete implementations:

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class SentenceTransformersEmbedder(EmbeddingProvider):
    def __init__(self, model_name: str): ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class OllamaEmbedder(EmbeddingProvider):
    def __init__(self, base_url: str, model: str): ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

### `vault_writer/rag/vector_store.py`
ChromaDB wrapper — upsert, query, delete, count.

```python
class VectorStore:
    def __init__(self, index_path: str, embedder: EmbeddingProvider): ...
    def upsert_note(self, file_path: str, content: str) -> None: ...
    def search(self, query: str, top_k: int) -> list[SearchResult]: ...
    def find_similar(self, content: str, exclude_path: str, top_k: int) -> list[SimilarityNotice]: ...
    def delete_note(self, file_path: str) -> None: ...
    def count(self) -> int: ...
    def build_from_vault(self, vault_path: str, callback=None) -> int: ...
```

### `vault_writer/rag/intent.py`
Intent classifier using `AIProvider`.

```python
def classify_intent(message: str, provider: AIProvider) -> IntentType: ...
```

### `vault_writer/rag/engine.py`
RAG answer generation.

```python
def answer_query(query: str, store: VectorStore, provider: AIProvider, top_k: int) -> RAGResult: ...
def search_vault(query: str, store: VectorStore, top_k: int) -> list[SearchResult]: ...
```

---

## Modified Files

### `config/loader.py`
- Add `EmbeddingConfig` dataclass
- Add `embedding: EmbeddingConfig` field to `AppConfig`
- Add `get_embedding_provider(config) -> EmbeddingProvider` factory
- Parse `embedding:` block from `config.yaml`

### `telegram/handlers/message.py`
- Before saving new note: classify intent via `classify_intent()`
- If `rag_query` → call `answer_query()` → reply with RAG answer + sources
- If `search_query` → call `search_vault()` → reply with ranked list
- If `new_note` → existing `handle_create_note()` flow + `find_similar()` + append notice

### `telegram/handlers/commands.py`
- Add `/reindex` command handler: rebuild full index, reply with note count

### `vault_writer/tools/create_note.py`
- After successful write: call `store.upsert_note(file_path, content)` to keep index in sync
- Return `SimilarityNotice` list in result dict for caller to surface to user

### `main.py`
- Initialize `VectorStore` at startup
- Start background index build (non-blocking)
- Store `vector_store` in `app.bot_data`

---

## Storage Layout

```
BrainSync/
└── data/
    └── chroma/          # ChromaDB persistence (auto-created)
        ├── chroma.sqlite3
        └── ...
```

`data/chroma/` must be in `.gitignore` (contains personal vault embeddings).
