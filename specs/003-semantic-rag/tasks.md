---
description: "Task list for BrainSync Semantic Search & RAG implementation"
---

# Tasks: BrainSync — Semantic Search & RAG

**Input**: `specs/003-semantic-rag/plan.md`, `spec.md`, `data-model.md`, `contracts/`, `research.md`, `quickstart.md`
**Branch**: `003-semantic-rag`

**Organization**: Tasks grouped by User Story for independent implementation and testing.
**Tests**: Not requested — test tasks omitted.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: New dependencies, package scaffolding, config extension.

- [x] T001 Add `chromadb` and `sentence-transformers` to `requirements.txt` (append after existing deps)
- [x] T002 [P] Create empty `vault_writer/rag/__init__.py` to register the new rag sub-package
- [x] T003 [P] Add `data/chroma/` to `.gitignore` (vector index contains personal vault embeddings)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on. Must complete before any story work begins.

⚠️ **CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Add `EmbeddingConfig` dataclass to `config/loader.py`: fields `backend` (str, default `"sentence-transformers"`), `model` (str, default `"paraphrase-multilingual-MiniLM-L12-v2"`), `ollama_embed_url` (str, default `"http://localhost:11434"`), `index_path` (str, default `"data/chroma"`), `similarity_duplicate_threshold` (float, default `0.85`), `similarity_related_threshold` (float, default `0.70`), `top_k_results` (int, default `5`); add `embedding: EmbeddingConfig` field to `AppConfig`; parse from `config.yaml` `embedding:` block

- [x] T005 Add `get_embedding_provider(config: AppConfig) -> EmbeddingProvider` factory to `config/loader.py`: returns `SentenceTransformersEmbedder` if `backend == "sentence-transformers"`, else `OllamaEmbedder`

- [x] T006 [P] Create `vault_writer/rag/embedder.py`: define `EmbeddingProvider` ABC with `embed(texts: list[str]) -> list[list[float]]`; implement `SentenceTransformersEmbedder.__init__(model_name)` with lazy `SentenceTransformer` load; implement `embed()` using `model.encode(texts).tolist()`; implement `OllamaEmbedder.__init__(base_url, model)` and `embed()` via POST to `{base_url}/api/embeddings` for each text, return list of embeddings; raise `RuntimeError` on HTTP error

- [x] T007 [P] Create `vault_writer/rag/vector_store.py`: `VectorStore.__init__(index_path, embedder)` — create `chromadb.PersistentClient(index_path)`, get/create collection `"vault_notes"` with cosine space; implement `upsert_note(file_path, content)` — compute SHA-256 hash of content, check if already indexed with same hash (skip if unchanged), embed content, call `collection.upsert(ids, embeddings, documents, metadatas)`; implement `search(query, top_k) -> list[SearchResult]` — embed query, call `collection.query`, return ranked `SearchResult` list; implement `find_similar(content, exclude_path, top_k) -> list[SimilarityNotice]` — embed content, query collection, filter out `exclude_path`, classify each result as duplicate/related/unique based on `EmbeddingConfig` thresholds; implement `delete_note(file_path)`; implement `count() -> int`; implement `build_from_vault(vault_path, config) -> int` — scan all `.md` files excluding MoC files (`0 *.md`), upsert each, return count

- [x] T008 [P] Create `vault_writer/rag/intent.py`: `classify_intent(message: str, provider: AIProvider) -> IntentType` — build prompt classifying message as `rag_query` / `search_query` / `new_note`; call `provider.complete(prompt, max_tokens=20)`; parse response to `IntentType`; on any error or unrecognised response return `IntentType.NEW_NOTE` (safe default); define `IntentType` enum in same file: `RAG_QUERY = "rag_query"`, `SEARCH_QUERY = "search_query"`, `NEW_NOTE = "new_note"`

- [x] T009 [P] Create `vault_writer/rag/engine.py`: define `RAGResult` dataclass (`answer`, `sources: list[str]`, `query`, `found: bool`) and `SearchResult` dataclass (`file_path`, `excerpt`, `similarity: float`) and `SimilarityNotice` dataclass (`matched_path`, `similarity`, `is_duplicate: bool`); implement `answer_query(query, store, provider, top_k, config) -> RAGResult` — call `store.search(query, top_k)`, if no results return `RAGResult(found=False, ...)`; build RAG prompt with retrieved context; call `provider.complete(prompt)`; return `RAGResult(answer, sources, query, found=True)`; implement `search_vault(query, store, top_k) -> list[SearchResult]` — delegate to `store.search()`

- [x] T010 Update `main.py`: import `get_embedding_provider` from `config.loader`; after `get_ai_provider()`, call `get_embedding_provider(config)` to create embedder; instantiate `VectorStore(config.embedding.index_path, embedder)`; store in `app.bot_data["vector_store"]`; in `_ensure_infrastructure_ready()`, start background thread calling `store.build_from_vault(config.vault.path, config.embedding)` — non-blocking; log count when complete

**Checkpoint**: Config loads with embedding fields, EmbeddingProvider factory works, VectorStore initialises, background indexing starts on bot launch. All user stories can now begin.

---

## Phase 3: User Story 1 — Natural Language Vault Query (Priority: P1) 🎯 MVP

**Goal**: User sends a plain question → bot classifies intent → retrieves relevant notes via vector search → synthesizes RAG answer with citations.

**Independent Test**: Send "що я думав про X?" to bot with a vault containing ≥1 relevant note. Verify bot replies with a synthesized answer and at least one citation. No command required.

- [x] T011 [US1] Add `format_rag_answer(answer: str, sources: list[str]) -> str` and `format_rag_not_found() -> str` to `telegram/formatter.py`

- [x] T012 [US1] Update `telegram/handlers/message.py` `handle_message()`: after auth check and before `detect_prefix()`, if `provider` is not None and `context.bot_data.get("vector_store")` exists, call `classify_intent(text, provider)` in executor; if `IntentType.RAG_QUERY` → call `answer_query(text, store, provider, config.embedding.top_k_results, config)` in executor → reply with `format_rag_answer(result.answer, result.sources)` or `format_rag_not_found()` → return early (do not save as note); if `IntentType.SEARCH_QUERY` → fall through to Phase 4 handler (stub return for now); if `IntentType.NEW_NOTE` → continue existing save flow; if `provider` is None or vector_store absent → skip intent classification entirely (safe fallback to existing behaviour)

**Checkpoint**: User Story 1 fully functional — question about vault → RAG answer with citations.

---

## Phase 4: User Story 2 — Semantic Vault Search (Priority: P2)

**Goal**: `/search` uses vector similarity instead of keyword matching; natural language search queries also routed here.

**Independent Test**: Send `/search управління часом` where the phrase doesn't appear literally in any note but related concepts do. Verify bot returns relevant semantic results.

- [x] T013 [US2] Add `format_semantic_search_results(results: list[SearchResult], query: str) -> str` and `format_search_degraded_notice() -> str` to `telegram/formatter.py`

- [x] T014 [US2] Replace keyword search in `telegram/handlers/commands.py` `cmd_search()`: if `vector_store` in `bot_data`, call `search_vault(query, store, config.embedding.top_k_results)` in executor; format with `format_semantic_search_results()`; if `vector_store` absent or raises → fall back to existing `search_notes()` keyword search; prepend `format_search_degraded_notice()` on fallback

- [x] T015 [US2] Complete `SEARCH_QUERY` branch in `telegram/handlers/message.py` `handle_message()`: call `search_vault(text, store, config.embedding.top_k_results)` in executor; reply with `format_semantic_search_results()`; return early

**Checkpoint**: User Stories 1 AND 2 independently functional.

---

## Phase 5: User Story 3 — Duplicate / Similar Note Detection (Priority: P3)

**Goal**: After every note save, bot checks for semantically similar notes and appends a notice to the confirmation reply.

**Independent Test**: Save a note semantically similar to an existing one. Verify confirmation reply includes "⚠️ Схожа нотатка" or "💡 Можливо пов'язана нотатка" with the matching note's path and similarity percentage.

- [x] T016 [US3] Add `format_similarity_notice(notices: list[SimilarityNotice]) -> str` to `telegram/formatter.py`: for each notice, if `is_duplicate` → "⚠️ Схожа нотатка вже існує:\n→ {path} ({pct}%)"; else → "💡 Можливо пов'язана нотатка:\n→ {path} ({pct}%)"; return empty string if list is empty

- [x] T017 [US3] Update `vault_writer/tools/create_note.py` `handle_create_note()`: after `write_note()` success, call `store.upsert_note(file_path, content)` if `store` provided (new optional param `vector_store=None`); call `store.find_similar(content, exclude_path=file_path, top_k=3)` filtered to similarity ≥ `config.embedding.similarity_related_threshold`; include `similarity_notices` list in returned dict

- [x] T018 [US3] Update `telegram/handlers/message.py` `handle_message()` NEW_NOTE branch: after `_run_create_note()`, if `result["success"]` and `result.get("similarity_notices")`, append `format_similarity_notice(notices)` to reply string

- [x] T019 [US3] Update `telegram/handlers/media.py` all `_run_create_note()` call sites (voice, photo, PDF, text file): pass `vector_store=context.bot_data.get("vector_store")` and `embedding_config=config.embedding`; append `format_similarity_notice()` to reply if notices returned

**Checkpoint**: User Stories 1, 2, AND 3 independently functional.

---

## Phase 6: User Story 4 — Index Persistence and Sync (Priority: P4)

**Goal**: Vector index persists across restarts; `/reindex` command triggers full rebuild.

**Independent Test**: Add a note via bot, restart bot, ask a question matching that note. Verify it appears in results without waiting for rebuild. Send `/reindex` and verify completion message with note count.

- [x] T020 [US4] Add `/reindex` command handler to `telegram/handlers/commands.py`: auth check → reply "⏳ Переіндексація vault…" → call `store.build_from_vault(config.vault.path, config.embedding)` in executor → reply "✅ Переіндексовано: {N} нотаток."

- [x] T021 [US4] Register `/reindex` `CommandHandler` in `telegram/bot.py` `build_application()`: `app.add_handler(CommandHandler("reindex", cmd_reindex))`

- [x] T022 [US4] Add `format_reindex_done(count: int) -> str` and `format_reindex_start() -> str` to `telegram/formatter.py`

- [x] T023 [US4] Verify ChromaDB persistence across restarts in `vault_writer/rag/vector_store.py`: ensure `PersistentClient` is used (not `Client`); add `is_ready() -> bool` method that returns `True` if collection exists and `count() > 0`; log collection size on `VectorStore.__init__()` if existing index found

**Checkpoint**: All 4 user stories functional. Index survives restart. Manual reindex works.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, observability, edge cases.

- [x] T024 [P] Add structured logging throughout `vault_writer/rag/`: log intent classification result and confidence; log search query + result count + top similarity score; log RAG answer source count; log index upsert (file_path, hash_changed); log similarity notices found; never log note content or query text

- [x] T025 [P] Add fallback handling in `telegram/handlers/message.py` intent classification: if embedding backend raises `RuntimeError` (Ollama offline) or `ImportError` (sentence-transformers not installed), catch silently, default to `IntentType.NEW_NOTE`, log warning once per session

- [x] T026 [P] Add `format_index_building_notice() -> str` to `telegram/formatter.py`; in `vault_writer/rag/vector_store.py` expose `_building: bool` flag; in `handle_message()` if intent is RAG/search and `store._building`, prepend "⏳ Індекс будується — результати можуть бути неповними." to reply

- [x] T027 [P] Add `data/chroma/` to `.gitignore` and update `quickstart.md` validation checklist status to reflect implemented tasks

- [x] T028 Run `quickstart.md` validation checklist end-to-end: both packages installed, background indexing starts on launch, `/reindex` works, RAG query returns citations, `/search` returns semantic results, duplicate detection triggers, restart preserves index

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — requires `VectorStore`, `classify_intent`, `answer_query`
- **US2 (Phase 4)**: Depends on Phase 2 — requires `VectorStore`, `search_vault`; independent of US1
- **US3 (Phase 5)**: Depends on Phase 2 + T017 (create_note extended) — requires `find_similar`; independent of US1/US2
- **US4 (Phase 6)**: Depends on Phase 2 (VectorStore persistence) — independent of US1/US2/US3
- **Polish (Phase 7)**: Depends on all desired stories complete

### Within Each User Story

- Formatter tasks before handler tasks
- Core RAG/search logic before Telegram integration
- `create_note.py` extension (T017) before media handler updates (T019)

### Parallel Opportunities (Phase 2)

```bash
# All can start simultaneously after Phase 1:
T006 "Create vault_writer/rag/embedder.py"
T007 "Create vault_writer/rag/vector_store.py"
T008 "Create vault_writer/rag/intent.py"
T009 "Create vault_writer/rag/engine.py"
```

T004 and T005 (config changes) must precede T010 (main.py) but can run parallel to T006–T009.

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — **BLOCKS everything**
3. Complete Phase 3: User Story 1 (T011–T012)
4. **STOP AND VALIDATE**: Ask a question → verify RAG answer with citations appears
5. Deploy / use daily

### Incremental Delivery

1. Setup + Foundational → infrastructure ready, background indexing works
2. US1 (Phase 3) → RAG answers ✓
3. US2 (Phase 4) → semantic `/search` ✓
4. US3 (Phase 5) → duplicate detection ✓
5. US4 (Phase 6) → index persistence + `/reindex` ✓
6. Polish (Phase 7) → production-ready ✓

---

## Notes

- `[P]` = different files, no blocking dependencies — safe to run in parallel
- `[Story]` maps task to user story for traceability
- No test tasks generated (not requested)
- Commit after each completed checkpoint
- Total tasks: **28** (T001–T028)
- Phase 2 (Foundational) is the densest — 7 tasks, all blocking
