# Data Model: BrainSync Media Support

**Branch**: `002-media-support` | **Date**: 2026-03-31

> Extends `specs/001-brainsync-mvp/data-model.md`. Only new or modified entities are documented here.

---

## 1. MediaType (new enum)

Identifies the type of incoming Telegram media message.

```python
class MediaType(str, Enum):
    VOICE       = "voice"       # Telegram voice message (.ogg/opus)
    PHOTO       = "photo"       # Telegram photo
    PDF         = "pdf"         # Document with MIME type application/pdf
    TEXT_FILE   = "text_file"   # Document with MIME type text/plain or text/markdown
    UNSUPPORTED = "unsupported" # Sticker, video, GIF, audio doc, contact, etc.
```

---

## 2. TranscriptionResult (new dataclass)

Output of local voice-to-text processing. Internal use only — not persisted.

```python
@dataclass
class TranscriptionResult:
    text: str              # Full transcript joined from all segments
    language: str          # Detected or forced language code, e.g. "uk"
    duration_seconds: float
```

**Produced by**: `vault_writer/ai/transcriber.py`
**Consumed by**: `telegram/handlers/media.py` → passed as `text` to `handle_create_note`

---

## 3. ImageDescription (new dataclass)

Output of AI vision processing. Internal use only — not persisted.

```python
@dataclass
class ImageDescription:
    text: str        # AI-generated natural language description of the image
    provider: str    # "anthropic" | "ollama"
    model: str       # Model name used (e.g., "claude-sonnet-4-6" or "llava")
    fallback: bool   # True if vision failed and caption-only was used
```

**Produced by**: `AnthropicProvider.complete_with_image()` or `OllamaProvider.complete_with_image()`
**Consumed by**: `telegram/handlers/media.py`

---

## 4. ExtractedDocument (new dataclass)

Text content parsed from a file (PDF or plain text). Internal use only.

```python
@dataclass
class ExtractedDocument:
    full_text: str          # Complete extracted content — written to note body
    ai_context: str         # First N chars of full_text — sent to AI for classification
    page_count: int         # Pages extracted (PDF only; 0 for text files)
    truncated: bool         # True if page_count < total pages in PDF
    source_filename: str    # Original Telegram filename (used as fallback note title)
```

**Produced by**: `vault_writer/media/pdf_extractor.py` (PDF) or inline read (text files)
**Consumed by**: `telegram/handlers/media.py`

---

## 5. MediaConfig (new dataclass — extends AppConfig)

Configuration for media processing. Parsed from `config.yaml` `[media]` block.

```python
@dataclass
class MediaConfig:
    max_voice_duration_seconds: int   # default: 300 (5 minutes)
    transcription_model: str          # default: "small" — tiny/base/small/medium/large
    pdf_max_pages: int                # default: 50
    pdf_ai_context_chars: int         # default: 3000 — chars sent to AI for classification
    max_file_size_mb: int             # default: 20 — max Telegram file download size
```

**New field in AIConfig** (modified):
```python
@dataclass
class AIConfig:
    # ... all existing fields unchanged ...
    ollama_vision_model: str | None   # new: optional model name for Ollama vision (e.g. "llava")
```

**AppConfig** gains one new field:
```python
@dataclass
class AppConfig:
    # ... all existing fields unchanged ...
    media: MediaConfig                # new
```

---

## 6. AIProvider interface (modified)

`complete_with_image()` added as optional method with `NotImplementedError` default.

```python
class AIProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 1000) -> str: ...

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str,    # MIME type: "image/jpeg" | "image/png" | "image/webp"
        max_tokens: int = 1000,
    ) -> str:
        """Override in providers that support vision. Default raises NotImplementedError."""
        raise NotImplementedError("Vision not supported by this provider")
```

---

## 7. Infrastructure Readiness State (new — in main.py)

A module-level flag controlling whether the bot accepts incoming messages.

```python
# main.py
_infrastructure_ready: bool = False
```

**Lifecycle**:
```
Bot starts
  → check transcription model on disk
  → if missing:
      send notification to allowed_user_ids[0]: "⏳ Завантаження моделі транскрипції (~466 MB)..."
      download model (blocking)
      send confirmation: "✅ Модель готова. BrainSync запущено."
  → set _infrastructure_ready = True
  → application.run_polling() starts
```

All message handlers check `_infrastructure_ready` before processing. If `False`, reply:
`"⏳ Система ще завантажується, зачекайте хвилину…"` and return.

---

## 8. Updated Media Processing Flow

Extends the existing note creation state diagram from `001-brainsync-mvp/data-model.md`:

```
Telegram media received (voice / photo / document)
  → auth_check
  → check _infrastructure_ready → if False: reply "завантажується..." → return
  → send typing indicator (continuous)
  → detect MediaType
  ├─ VOICE:
  │    → download .ogg from Telegram
  │    → TranscriptionResult ← transcriber.transcribe(file_path, config.media)
  │    → text = result.text + (caption as prefix if present)
  │    → delete temp file
  │    → → handle_create_note(text, ...)  [existing pipeline]
  ├─ PHOTO:
  │    → download image bytes
  │    → detect MIME type (image/jpeg / image/png / image/webp)
  │    → try: ImageDescription ← provider.complete_with_image(describe_prompt, bytes, mime)
  │    → except NotImplementedError: fallback = True, description = caption or ""
  │    → text = caption_prefix + description (combined)
  │    → → handle_create_note(text, ...)  [existing pipeline]
  ├─ PDF:
  │    → download file bytes
  │    → ExtractedDocument ← pdf_extractor.extract(bytes, config.media)
  │    → if full_text empty: reply error, return
  │    → → handle_create_note(ai_context, ...)  [for classification/title]
  │         note body overridden with full_text before write
  ├─ TEXT_FILE:
  │    → download file bytes, decode as UTF-8
  │    → if too large: reply error, return
  │    → → handle_create_note(content, ...)  [existing pipeline]
  └─ UNSUPPORTED:
       → reply listing supported types → return
```
