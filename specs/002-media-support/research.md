# Research: BrainSync Media Support

**Branch**: `002-media-support` | **Date**: 2026-03-31

---

## 1. Voice Transcription — faster-whisper

### Decision
Use `faster-whisper` library for on-device speech-to-text.

### Rationale
- 4× faster than original OpenAI `whisper` library (uses CTranslate2 backend)
- Identical model quality and language support
- Pure Python install (`pip install faster-whisper`) — no manual model download needed
- Supports `.ogg` (Telegram voice format) via ffmpeg
- Ukrainian language (`uk`) supported across all model sizes

### Alternatives Considered
| Library | Rejected Because |
|---------|-----------------|
| `openai-whisper` | 4× slower, same models, no benefit |
| OpenAI Whisper API | External API, costs money, violates "no external APIs" requirement |
| `vosk` | Lower accuracy for Ukrainian, smaller community |
| `speech_recognition` | Cloud-dependent, not offline-capable |

### API Usage

```python
from faster_whisper import WhisperModel

# One-time initialization (loads model into memory)
model = WhisperModel(
    "small",           # model size: tiny/base/small/medium/large
    device="cpu",      # "cpu" for Windows without CUDA GPU
    compute_type="int8"  # quantized — faster on CPU, same quality
)

# Transcribe audio file
segments, info = model.transcribe(
    "voice.ogg",
    language="uk",         # force Ukrainian; None = auto-detect
    beam_size=5,           # accuracy vs speed tradeoff
    vad_filter=True,       # skip silence segments
)
text = " ".join(segment.text.strip() for segment in segments)
# info.language → detected language code
# info.duration → total audio duration in seconds
```

### Model Sizes & Ukrainian Quality

| Model | Disk | RAM | Speed (CPU) | Ukrainian |
|-------|------|-----|-------------|-----------|
| `tiny` | ~75 MB | ~150 MB | fastest | basic |
| `base` | ~145 MB | ~200 MB | fast | good |
| `small` | ~466 MB | ~500 MB | moderate | **recommended** |
| `medium` | ~1.5 GB | ~1.5 GB | slow | excellent |
| `large-v3` | ~3 GB | ~3 GB | very slow | best |

**Default**: `small` — best balance of size (~466 MB), speed, and Ukrainian accuracy.

### Model Cache Location
- Default: `~/.cache/huggingface/hub/` (Windows: `C:\Users\{user}\.cache\huggingface\hub\`)
- Custom path via `download_root` constructor param
- Download is automatic on first `WhisperModel()` instantiation
- Subsequent starts load from cache instantly

### Audio Format Support
- Requires **ffmpeg** installed and on PATH
- Supports: `.ogg` (Telegram voice), `.mp3`, `.wav`, `.m4a`, `.flac`, `.webm`
- Telegram voice messages use `.ogg` with Opus codec — directly supported

### ffmpeg Requirement
```bat
winget install ffmpeg
```
ffmpeg must be on system PATH. Verify: `ffmpeg -version`

---

## 2. PDF Text Extraction — pypdf

### Decision
Use `pypdf` library for local PDF text extraction.

### Rationale
- Pure Python, no system dependencies (no poppler, no Java)
- Works on Windows out of the box
- Simple, clean API
- Actively maintained (successor to PyPDF2)
- Sufficient for text-based PDFs (articles, reports, documentation)

### Alternatives Considered
| Library | Rejected Because |
|---------|-----------------|
| `pdfminer.six` | More complex API, overkill for basic text extraction |
| `pdfplumber` | Heavier dependency, better for tables/layout — not needed here |
| `pymupdf` (fitz) | AGPL license, binary dependency |
| Anthropic PDF API | External API, costs tokens, violates local-first principle |

### API Usage

```python
import io
from pypdf import PdfReader

def extract_pdf_text(file_bytes: bytes, max_pages: int = 50) -> tuple[str, int, bool]:
    """Returns (full_text, pages_extracted, was_truncated)."""
    reader = PdfReader(io.BytesIO(file_bytes))
    total_pages = len(reader.pages)
    pages_to_read = min(total_pages, max_pages)
    truncated = total_pages > max_pages

    parts = []
    for page in reader.pages[:pages_to_read]:
        text = page.extract_text()
        if text:
            parts.append(text)

    full_text = "\n\n".join(parts)
    return full_text, pages_to_read, truncated
```

### Scanned PDF Detection
`page.extract_text()` returns `""` or `None` for image-only (scanned) pages.
Check: if all pages produce empty text → scanned PDF → notify user, do not save empty note.

```python
is_scanned = not full_text.strip()
```

### Known Limitations
- Scanned/image PDFs: no text extraction (OCR not included — out of scope)
- Complex layouts (multi-column): may produce garbled text order
- Password-protected PDFs: raises `pypdf.errors.PdfReadError` — catch and notify user

---

## 3. Ollama REST API — Text & Vision

### Decision
Implement `OllamaProvider` using Ollama's REST API over HTTP (`requests` or `httpx`).

### Rationale
- Ollama exposes a simple REST API at `http://localhost:11434`
- No Python SDK required — `requests` (already in Python stdlib path) or `httpx` suffices
- Same endpoint handles both text-only and vision (multimodal) requests

### Text Completion API

```python
import requests

def complete(prompt: str, model: str, base_url: str, max_tokens: int = 1000) -> str:
    response = requests.post(
        f"{base_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]
```

### Vision API (multimodal)

```python
import base64

def complete_with_image(
    prompt: str, image_bytes: bytes, vision_model: str, base_url: str, max_tokens: int = 1000
) -> str:
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = requests.post(
        f"{base_url}/api/chat",
        json={
            "model": vision_model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [b64],   # base64 string, no data URI prefix
            }],
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]
```

### Vision-Capable Models

| Model | Pull Command | Notes |
|-------|-------------|-------|
| `llava` | `ollama pull llava` | Most popular, good general vision |
| `llava-phi3` | `ollama pull llava-phi3` | Smaller, faster |
| `moondream` | `ollama pull moondream` | Very small, basic vision |
| `llava-llama3` | `ollama pull llava-llama3` | Stronger understanding |
| `bakllava` | `ollama pull bakllava` | Alternative base |

**Recommended**: `llava` for first-time setup (best support and documentation).

### Dependency
`requests` is already a transitive dependency of `python-telegram-bot`. No new package needed.

---

## 4. Anthropic Vision API

### Decision
Extend `AnthropicProvider.complete_with_image()` using the existing `anthropic` SDK.

### API Usage

```python
import base64

def complete_with_image(
    self, prompt: str, image_bytes: bytes, media_type: str, max_tokens: int = 1000
) -> str:
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = self._client.messages.create(
        model=self._model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,  # "image/jpeg" | "image/png" | "image/webp"
                        "data": b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return response.content[0].text
```

### Supported MIME Types
- `image/jpeg` — Telegram photos (JPEG)
- `image/png` — PNG attachments
- `image/webp` — WebP images
- `image/gif` — GIF (static frame only)

### Model Compatibility
`claude-sonnet-4-6` (default) fully supports vision. If the configured model does not support vision, the SDK raises `anthropic.BadRequestError` — catch this and fall back to caption-only.

### No New Dependencies
Uses the existing `anthropic` SDK already in `requirements.txt`.

---

## 5. Telegram File Download

### How It Works
PTB provides `update.message.voice.get_file()` / `update.message.photo[-1].get_file()` etc.
Files are downloaded via `file.download_to_drive(path)` or `file.download_as_bytearray()`.

```python
# Voice
voice_file = await update.message.voice.get_file()
file_bytes = await voice_file.download_as_bytearray()

# Photo (largest available size)
photo = update.message.photo[-1]
photo_file = await photo.get_file()
image_bytes = await photo_file.download_as_bytearray()

# Document
doc_file = await update.message.document.get_file()
file_bytes = await doc_file.download_as_bytearray()
```

### File Size Limit
Telegram Bot API: max **20 MB** for bot file downloads. Our `max_file_size_mb` default matches this.

### MIME Type Detection for Documents
```python
mime_type = update.message.document.mime_type  # e.g. "application/pdf", "text/plain"
filename = update.message.document.file_name   # original filename
```

---

## 6. Summary of New Dependencies

| Package | Purpose | Already Present |
|---------|---------|----------------|
| `faster-whisper` | Voice transcription | No — add to requirements.txt |
| `pypdf` | PDF text extraction | No — add to requirements.txt |
| `ffmpeg` (system) | Audio decoding for faster-whisper | No — document in setup |
| `requests` | Ollama HTTP calls | Transitive dep (via python-telegram-bot) — explicit import safe |
| `anthropic` | Anthropic vision | Yes — already in requirements.txt |
