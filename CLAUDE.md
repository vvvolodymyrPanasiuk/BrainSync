# BrainSync Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-31

## Active Technologies
- Local filesystem (vault .md files), model cache (~466 MB for `small` Whisper model) (002-media-support)
- Python 3.12+ on Windows 11 + `chromadb`, `sentence-transformers`, `torch` (CPU), `requests` (existing) (003-semantic-rag)
- ChromaDB embedded (`data/chroma/`) — local, persistent, no server (003-semantic-rag)

- Python 3.12+ on Windows 11 (001-brainsync-mvp)

## Project Structure

```text
src/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.12+ on Windows 11: Follow standard conventions

## Recent Changes
- 003-semantic-rag: Added Python 3.12+ on Windows 11 + `chromadb`, `sentence-transformers`, `torch` (CPU), `requests` (existing)
- 002-media-support: Added Python 3.12+ on Windows 11

- 001-brainsync-mvp: Added Python 3.12+ on Windows 11

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
