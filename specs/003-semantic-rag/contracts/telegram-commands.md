# Contract: Telegram Interface — Semantic Search & RAG

**Branch**: `003-semantic-rag` | **Date**: 2026-03-31

---

## New Commands

### `/reindex`

Triggers a full rebuild of the vector index from all vault notes.

**Input**: No arguments required.

**Behavior**:
1. Bot replies immediately: "⏳ Переіндексація vault…"
2. Scans all `.md` files in vault (excluding MoC files `0 *.md`)
3. Embeds all notes (replaces existing vectors)
4. Replies: "✅ Переіндексовано: {N} нотаток."

**Error case**: If embedding backend unavailable → "❌ Embedding backend недоступний. Перевірте налаштування."

---

## Modified Commands

### `/search <query>`

**Before**: Keyword full-text search, returns excerpts.
**After**: Semantic vector search, returns top-K results ranked by similarity.

**Input**: Natural language query in any language.

**Output format**:
```
🔍 Знайдено {N} нотаток для "{query}":

1. Architecture/0004 CQRS pattern.md (94%)
   ...CQRS розділяє read і write моделі...

2. Architecture/0003 Event Sourcing.md (81%)
   ...Event Sourcing зберігає всі зміни стану...
```

**Fallback** (embedding backend unavailable):
```
⚠️ Семантичний пошук недоступний — використовую keyword пошук.
🔍 Знайдено {N} нотаток для "{query}":
...
```

---

## Modified Plain-Text Message Handling

Plain text messages now go through intent classification before routing.

### Intent: `rag_query`

**Trigger examples**: "що я думав про X?", "як я вирішував Y?", "розкажи мені про мої думки щодо Z"

**Output format**:
```
💡 На основі твого vault:

{synthesized answer}

Джерела:
→ Architecture/0004 CQRS pattern.md
→ Architecture/0003 Event Sourcing.md
```

**Not found case**:
```
🔍 Нічого не знайдено у vault за цим запитом.
```

### Intent: `search_query`

**Trigger examples**: "знайди нотатки про X", "покажи все про Y", "є щось про Z?"

**Output**: Same format as `/search` command.

### Intent: `new_note`

**Output**: Existing confirmation + optional similarity notice appended:
```
✓ Збережено → Architecture/0005 CQRS Commands.md

⚠️ Схожа нотатка вже існує:
→ Architecture/0004 CQRS pattern.md (91%)
```

Or for related (70–84%):
```
✓ Збережено → General/0012 productivity hacks.md

💡 Можливо пов'язана нотатка:
→ General/0008 deep work notes.md (76%)
```

---

## Config Schema Addition

```yaml
embedding:
  backend: "sentence-transformers"   # "sentence-transformers" | "ollama"
  model: "paraphrase-multilingual-MiniLM-L12-v2"
  ollama_embed_url: "http://localhost:11434"
  index_path: "data/chroma"
  similarity_duplicate_threshold: 0.85
  similarity_related_threshold: 0.70
  top_k_results: 5
```
