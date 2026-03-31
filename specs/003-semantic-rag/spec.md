# Feature Specification: Semantic Search and RAG over Vault

**Feature Branch**: `003-semantic-rag`
**Created**: 2026-03-31
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Natural Language Vault Query (Priority: P1)

The user sends a plain Telegram message asking a question about their own notes — without using any slash command. The bot autonomously detects that this is a knowledge retrieval intent, searches the vault semantically, and replies with a synthesized answer that cites the actual notes it drew from.

**Why this priority**: This is the core RAG experience and delivers the most direct value. All other stories build on this foundation.

**Independent Test**: Send "що я думав про продуктивність?" to the bot with a vault containing at least one relevant note. Verify the bot replies with a synthesized answer and includes at least one note citation (file path or title). No `/search` command required.

**Acceptance Scenarios**:

1. **Given** the vault contains notes on productivity, **When** user sends "що я думав про продуктивність?", **Then** bot replies with a synthesized answer and cites 1–5 relevant notes by title and path.
2. **Given** the vault contains no relevant notes, **When** user asks a question, **Then** bot replies "Нічого не знайдено у vault за цим запитом" and does not hallucinate.
3. **Given** user sends a plain message that is clearly a new thought (not a question), **When** bot processes it, **Then** bot saves it as a note normally without triggering RAG.
4. **Given** user sends "знайди все про CQRS", **When** bot processes it, **Then** bot returns a ranked list of relevant notes with excerpts.

---

### User Story 2 — Semantic Vault Search (Priority: P2)

The user explicitly asks the bot to find notes related to a topic using natural language. The bot returns a ranked list of semantically relevant notes with excerpts, even if the exact words don't appear in the notes.

**Why this priority**: Replaces and extends the current keyword `/search` command. Delivers value independently of full RAG answer generation.

**Independent Test**: Send "/search управління часом" with a vault where that exact phrase doesn't appear but related concepts do (e.g. "time blocking", "deep work"). Verify bot returns relevant results that keyword search would miss.

**Acceptance Scenarios**:

1. **Given** a note contains "time blocking and deep work", **When** user searches "управління часом", **Then** the note appears in results.
2. **Given** 20 relevant notes exist, **When** user searches, **Then** bot returns top 5 most relevant notes with title, path, and excerpt.
3. **Given** `/search` command is used, **When** processed, **Then** semantic search is used instead of keyword matching.

---

### User Story 3 — Duplicate / Similar Note Detection (Priority: P3)

After saving a new note, the bot proactively checks if a semantically similar note already exists in the vault and notifies the user with a link to the existing note.

**Why this priority**: Prevents vault fragmentation. Useful but not blocking the core RAG experience.

**Independent Test**: Save a note about "CQRS separates read and write models" when a similar note already exists. Verify the bot appends "⚠️ Схожа нотатка: Architecture/0004 CQRS pattern.md" to the confirmation reply.

**Acceptance Scenarios**:

1. **Given** a semantically similar note exists (similarity ≥ 85%), **When** a new note is saved, **Then** bot appends a duplicate notice with the existing note's path to the confirmation.
2. **Given** similarity is 70–84%, **When** a new note is saved, **Then** bot suggests "можливо пов'язана нотатка:" without calling it a duplicate.
3. **Given** no similar notes exist, **When** a new note is saved, **Then** confirmation message has no similarity notice.

---

### User Story 4 — Index Persistence and Sync (Priority: P4)

The vector index persists across bot restarts and updates automatically when new notes are added. Users never need to manually manage the index.

**Why this priority**: Infrastructure requirement for correctness. Without it, RAG answers become stale after first session.

**Independent Test**: Add a note via the bot, restart the bot, then immediately ask a question matching that note. Verify the note appears in results without a full rebuild.

**Acceptance Scenarios**:

1. **Given** a new note is saved via bot, **When** user immediately queries the vault, **Then** the new note is retrievable.
2. **Given** bot restarts, **When** first query arrives, **Then** results reflect the full pre-restart vault without waiting for rebuild.
3. **Given** `/reindex` command is sent, **When** processed, **Then** bot rebuilds the full vector index and confirms completion with note count.

---

### Edge Cases

- What if the vault has 0 notes? → Bot replies that the vault is empty.
- What if the embedding backend is unavailable (Ollama offline)? → Fall back to keyword search, notify user of degraded mode.
- What if a note file is deleted from the vault between index build and query? → Stale entry is skipped gracefully; index self-heals on next rebuild or `/reindex`.
- What if the user's question matches many notes equally? → Return top 5 by similarity score.
- What if vault is very large (1000+ notes)? → Index build runs in background at startup; bot remains responsive to all other messages.
- What if a RAG answer cannot be grounded in any vault note? → Bot must not answer from general AI knowledge; respond with "не знайдено у vault".

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect when a Telegram message is a knowledge retrieval intent (question about vault content) vs. a new note to save — without requiring any command or prefix from the user.
- **FR-002**: System MUST perform semantic similarity search over all vault notes using vector embeddings, returning results ranked by relevance score.
- **FR-003**: System MUST generate a synthesized RAG answer grounded exclusively in vault content, with citations (note title + file path) for every claim made.
- **FR-004**: System MUST support two embedding backends interchangeably: fully offline (local model) and Anthropic — selectable via `config.yaml` with no code changes.
- **FR-005**: System MUST persist the vector index to disk so it survives bot restarts without requiring a full rebuild.
- **FR-006**: System MUST incrementally update the vector index within 5 seconds of any new note being saved via the bot.
- **FR-007**: System MUST check for semantically similar notes after every new note save (all types: text, voice, photo, PDF) and notify the user if similarity exceeds the configured threshold.
- **FR-008**: System MUST expose a `/reindex` command that triggers a full vault re-index and reports the number of notes indexed.
- **FR-009**: System MUST fall back to keyword search if the embedding backend is unavailable, notifying the user of degraded search mode.
- **FR-010**: System MUST NOT answer RAG questions from general AI knowledge — all responses must be grounded exclusively in vault content.
- **FR-011**: The existing `/search` command MUST use semantic search instead of keyword matching.

### Key Entities

- **VectorIndex**: Persistent store mapping each note's file path to its embedding vector and text excerpt. Survives restarts. Updated incrementally on note creation.
- **NoteEmbedding**: Single note's vector representation — file path, content hash (for change detection), embedding vector, excerpt.
- **RAGQuery**: A user's natural language question — detected intent, retrieved note references, synthesized answer, cited sources.
- **SimilarityMatch**: Result of comparing a new note against the index — matched note path, similarity score, classification (duplicate / related / unique).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Semantic search returns relevant results for queries where the exact search term does not appear in any note — at least 1 correct result where keyword search returns 0.
- **SC-002**: RAG answer is delivered to the user within 15 seconds for a vault of up to 500 notes on a CPU-only machine.
- **SC-003**: Bot correctly classifies intent (RAG query vs. new note to save) for at least 19 out of 20 representative messages without false triggers.
- **SC-004**: Duplicate detection produces zero false positives on clearly unrelated notes.
- **SC-005**: Vector index survives bot restart — first query after restart returns correct results with no rebuild wait.
- **SC-006**: New note is searchable within 5 seconds of the bot sending its confirmation reply.

## Assumptions

- The vault contains standard BrainSync `.md` notes with YAML frontmatter as produced by the existing system.
- A single authorized user interacts with the bot — no multi-user vector index isolation required.
- The embedding backend is configured by the user in `config.yaml` before first use.
- Vault notes are in Ukrainian or English; the chosen embedding model must handle both languages.
- The vector index is stored locally on the same machine as the bot — no remote vector database.
- Initial index build for up to 500 notes must complete within 5 minutes on a CPU-only machine.
- Intent detection (RAG query vs. new note) is performed by the AI provider — not a keyword rule.
- Deduplication thresholds: ≥ 85% similarity = duplicate warning; 70–84% = related note suggestion; < 70% = no notice.
- RAG answers are generated in the same language as the user's question.
- The `/search` command is replaced by semantic search; keyword search remains only as a fallback.
- Duplicate detection runs for all note types including voice transcripts and PDF extracts.
