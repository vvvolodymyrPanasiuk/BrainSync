---
description: "Task list for BrainSync Media Support implementation"
---

# Tasks: BrainSync — Media & File Capture Support

**Input**: `specs/002-media-support/plan.md`, `spec.md`, `data-model.md`, `contracts/`, `research.md`
**Branch**: `002-media-support`

**Organization**: Tasks grouped by User Story for independent implementation and testing.
**Tests**: Not requested — test tasks omitted.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: New dependencies and package scaffolding.

- [X] T001 Add `faster-whisper` and `pypdf` to requirements.txt (append after existing deps)
- [X] T002 [P] Create empty `vault_writer/media/__init__.py` to register the new media sub-package

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on. Must complete before any story work begins.

⚠️ **CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add optional `complete_with_image(self, prompt, image_bytes, media_type, max_tokens) -> str` method to `AIProvider` in `vault_writer/ai/provider.py`: default body raises `NotImplementedError("Vision not supported by this provider")`
- [X] T004 [P] Add `MediaType` enum to `telegram/handlers/media.py` (create new file — stub only at this stage): `VOICE`, `PHOTO`, `PDF`, `TEXT_FILE`, `UNSUPPORTED`
- [X] T005 [P] Add `MediaConfig` dataclass to `config/loader.py`: fields `max_voice_duration_seconds` (int, default 300), `transcription_model` (str, default "small"), `pdf_max_pages` (int, default 50), `pdf_ai_context_chars` (int, default 3000), `max_file_size_mb` (int, default 20); parse from `config.yaml` `media:` block
- [X] T006 [P] Add `ollama_vision_model: str` field (default `""`) to `AIConfig` dataclass in `config/loader.py`; parse from `config.yaml` `ai.ollama_vision_model`; add `media: MediaConfig` field to `AppConfig`
- [X] T007 Implement `OllamaProvider` text completion in `vault_writer/ai/ollama_provider.py` (replace `NotImplementedError` stub): `complete(prompt, max_tokens)` → POST to `{ollama_url}/api/chat` with `{"model": model, "messages": [{"role": "user", "content": prompt}], "stream": false, "options": {"num_predict": max_tokens}}`; return `response.json()["message"]["content"]`; raise `RuntimeError` on HTTP error
- [X] T008 Add infrastructure readiness gate to `main.py`: before `application.run_polling()`, call `_ensure_infrastructure_ready(config, bot)` — check if `faster_whisper.WhisperModel` cache exists for configured model; if missing, send Telegram notification to `allowed_user_ids[0]` ("⏳ Завантаження моделі транскрипції…"), instantiate `WhisperModel(model_size, device="cpu", compute_type="int8")` to trigger download (blocking), send ready notification ("✅ Модель готова. BrainSync запущено."); set module-level `_READY = True`
- [X] T009 Create `telegram/handlers/media.py` entry point `handle_media_message(update, context)`: auth_check → send typing indicator → detect `MediaType` from `update.message` → route to `_handle_voice` / `_handle_photo` / `_handle_document` / reply with unsupported types list; each route stub may raise `NotImplementedError` at this stage
- [X] T010 Register three new `MessageHandler`s in `telegram/bot.py` `build_application()`: `filters.VOICE → handle_media_message`, `filters.PHOTO → handle_media_message`, `filters.Document.ALL → handle_media_message`; import from `telegram.handlers.media`

**Checkpoint**: Config loads with new fields, OllamaProvider handles text, bot registers media handlers, infrastructure gate blocks on missing model. All user stories can now begin.

---

## Phase 3: User Story 1 — Voice Message Capture (Priority: P1) 🎯 MVP

**Goal**: User sends a voice message → bot transcribes locally → structured vault note saved → bot confirms with file path.

**Independent Test**: Send a 15-second Ukrainian voice message to the bot; verify a structured `.md` file appears in the vault with transcribed content as the note body and bot replies with `✓ Збережено →`.

- [X] T011 [US1] Implement `Transcriber` class in `vault_writer/ai/transcriber.py`: constructor `__init__(self, model_size: str)` — lazy-load `WhisperModel(model_size, device="cpu", compute_type="int8")`; method `transcribe(file_path: str, language: str = "uk") -> TranscriptionResult` — call `model.transcribe(file_path, language=language, vad_filter=True, beam_size=5)`, join segment texts, return `TranscriptionResult(text, language, info.duration)`; add `TranscriptionResult` dataclass to same file
- [X] T012 [US1] Implement `_handle_voice(update, context)` in `telegram/handlers/media.py`: check `_READY` flag (reply "завантажується…" and return if False) → check `voice.duration > config.media.max_voice_duration_seconds` → download voice file as bytes to temp path via `await voice_file.download_to_drive(tmp_path)` → call `context.bot_data["transcriber"].transcribe(tmp_path)` → detect caption prefix if present → call `_run_create_note(transcript_text, ...)` (existing helper from message.py pattern) → reply confirmation → delete temp file in `finally` block
- [X] T013 [P] [US1] Add `format_voice_duration_error(max_seconds: int) -> str` and `format_media_processing_error() -> str` to `telegram/formatter.py`

**Checkpoint**: User Story 1 fully functional — send voice → note appears in vault.

---

## Phase 4: User Story 2 — Photo Capture (Priority: P2)

**Goal**: User sends a photo → AI describes it → structured vault note saved → bot confirms.

**Independent Test**: Send a photo of any whiteboard or document; verify the vault note contains a meaningful description and bot replies with `✓ Збережено →`.

- [X] T014 [US2] Implement `AnthropicProvider.complete_with_image()` in `vault_writer/ai/anthropic_provider.py`: base64-encode `image_bytes`, call `self._client.messages.create()` with content blocks `[{"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}, {"type": "text", "text": prompt}]`; catch `anthropic.BadRequestError` and re-raise as `NotImplementedError("Vision not supported by configured model")`
- [X] T015 [US2] Implement `_handle_photo(update, context)` in `telegram/handlers/media.py`: download largest photo (`update.message.photo[-1]`) as bytes → build describe prompt ("Опиши що зображено на фото детально.") → try `provider.complete_with_image(prompt, image_bytes, "image/jpeg")` → except `NotImplementedError`: set description to caption or `""`, notify user ("⚠️ Модель не підтримує зображення. Збережено лише текст.") → combine caption prefix + description → call `_run_create_note(combined_text, ...)`

**Checkpoint**: User Stories 1 AND 2 independently functional.

---

## Phase 5: User Story 3 — PDF Document Capture (Priority: P3)

**Goal**: User sends a PDF → text extracted locally → full text saved to vault note → bot confirms.

**Independent Test**: Send a 3-page PDF article; verify a vault note is created with the full extracted text as body and the title derived from the document or filename.

- [X] T016 [US3] Add optional `content_override: str | None = None` parameter to `handle_create_note()` in `vault_writer/tools/create_note.py`: if provided, assign `note.content = content_override` after formatting step (overrides AI-formatted body with raw content); this enables PDF to store full text while AI classifies on the truncated context
- [X] T017 [US3] Implement `vault_writer/media/pdf_extractor.py` `extract(file_bytes: bytes, max_pages: int, ai_context_chars: int) -> ExtractedDocument`: `PdfReader(BytesIO(file_bytes))`, iterate `reader.pages[:max_pages]`, collect `page.extract_text() or ""`, join with `"\n\n"`, set `truncated = total_pages > max_pages`; return `ExtractedDocument(full_text, full_text[:ai_context_chars], pages_extracted, truncated, source_filename)`; catch `pypdf.errors.PdfReadError` and return empty `ExtractedDocument` with error flag; add `ExtractedDocument` dataclass to same file
- [X] T018 [US3] Implement PDF branch in `_handle_document(update, context)` in `telegram/handlers/media.py`: check `document.mime_type == "application/pdf"` → size check → download bytes → call `pdf_extractor.extract(bytes, config.media.pdf_max_pages, config.media.pdf_ai_context_chars)` → if `full_text` empty: reply scanned-PDF error and return → call `_run_create_note(doc.ai_context, ..., content_override=doc.full_text)` → if `doc.truncated`: append truncation notice to confirmation reply

**Checkpoint**: User Stories 1, 2, AND 3 independently functional.

---

## Phase 6: User Story 4 — Plain Text File Capture (Priority: P4)

**Goal**: User sends a `.txt` or `.md` file → content read directly → vault note saved → bot confirms.

**Independent Test**: Send a `.txt` file with 3 paragraphs of text; verify the vault note body contains the full file content.

- [X] T019 [US4] Implement text file branch in `_handle_document(update, context)` in `telegram/handlers/media.py`: check `document.mime_type in ("text/plain", "text/markdown")` → size check against `config.media.max_file_size_mb` → download bytes → decode as UTF-8 (replace errors) → call `_run_create_note(content, ...)`
- [X] T020 [P] [US4] Add unsupported MIME type fallback as final branch in `_handle_document()` in `telegram/handlers/media.py`: reply with `format_unsupported_file_type()` message listing `pdf`, `txt`, `md` as supported; also add `format_unsupported_file_type() -> str` to `telegram/formatter.py`

**Checkpoint**: All four text-based user stories functional.

---

## Phase 7: User Story 5 — Ollama Full Vision (Priority: P5)

**Goal**: When Ollama is configured with a vision model, photos are described entirely on-device.

**Independent Test**: Configure `ai.provider = ollama` and `ai.ollama_vision_model = llava`; disable network; send a photo → verify vault note contains image description generated locally.

- [X] T021 [US5] Implement `OllamaProvider.complete_with_image()` in `vault_writer/ai/ollama_provider.py`: if `self._vision_model` empty → raise `NotImplementedError("ollama_vision_model not configured")`; base64-encode `image_bytes` → POST to `{ollama_url}/api/chat` with `{"model": vision_model, "messages": [{"role": "user", "content": prompt, "images": [b64]}], "stream": false}`; return `response.json()["message"]["content"]`
- [X] T022 [US5] Update `OllamaProvider.__init__()` in `vault_writer/ai/ollama_provider.py` to accept `vision_model: str = ""` and store as `self._vision_model`; update `config/loader.py` `get_ai_provider()` factory to pass `ollama_vision_model=config.ai.ollama_vision_model` when constructing `OllamaProvider`

**Checkpoint**: All 5 user stories functional. Full offline operation achievable with Ollama.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, observability, cleanup.

- [X] T023 [P] Add structured logging throughout `telegram/handlers/media.py`: log `MediaType` on every media message; log transcription duration and detected language; log vision provider/model used; log PDF page count and truncation status; log file size; never log note content, transcript text, or image data
- [X] T024 [P] Ensure `try/finally` temp file cleanup in `_handle_voice()` and `_handle_document()` in `telegram/handlers/media.py`: temp files MUST be deleted even on exception
- [X] T025 [P] Add remaining formatter messages to `telegram/formatter.py`: `format_model_downloading() -> str`, `format_model_ready() -> str`, `format_pdf_scanned_error() -> str`, `format_pdf_truncated_notice(pages: int) -> str`, `format_file_too_large(max_mb: int) -> str`, `format_unsupported_media_types() -> str`
- [X] T026 Run quickstart.md validation checklist end-to-end: ffmpeg present, both packages installed, model downloads on first start, all 5 media types tested per checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — requires Transcriber + infrastructure gate + media handler skeleton
- **US2 (Phase 4)**: Depends on Phase 2 — requires AIProvider.complete_with_image() + photo handler
- **US3 (Phase 5)**: Depends on Phase 2 + T016 (content_override) — requires pdf_extractor
- **US4 (Phase 6)**: Depends on Phase 2 + T018 (_handle_document exists) — text branch added to existing handler
- **US5 (Phase 7)**: Depends on Phase 2 (OllamaProvider text impl) + T015 (photo handler exists)
- **Polish (Phase 8)**: Depends on all desired stories complete

### Within Each User Story

- Config/dataclass tasks before handler tasks
- Provider tasks before handler tasks
- Core implementation before polish

### Parallel Opportunities (Phase 2)

```bash
# All can start simultaneously after Phase 1:
Task: "T003 Add complete_with_image() to AIProvider"
Task: "T004 Add MediaType enum to telegram/handlers/media.py"
Task: "T005 Add MediaConfig dataclass to config/loader.py"
Task: "T006 Add ollama_vision_model field to AIConfig"
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — **BLOCKS everything**
3. Complete Phase 3: User Story 1 (T011–T013)
4. **STOP AND VALIDATE**: Send a voice message → verify vault note appears
5. Deploy / use daily

### Incremental Delivery

1. Setup + Foundational → infrastructure ready, Ollama text works
2. US1 (Phase 3) → voice messages ✓
3. US2 (Phase 4) → photos ✓
4. US3 (Phase 5) → PDF documents ✓
5. US4 (Phase 6) → text files ✓
6. US5 (Phase 7) → full Ollama offline mode ✓
7. Polish (Phase 8) → production-ready ✓

---

## Notes

- `[P]` = different files, no blocking dependencies — safe to run in parallel
- `[Story]` maps task to user story for traceability
- No test tasks generated (not requested)
- Commit after each completed checkpoint
- Total tasks: **26** (T001–T026)
- Phase 2 (Foundational) is the densest — 8 tasks, all blocking
