# pdfscanner — Design Spec

**Date:** 2026-04-27
**Status:** Approved

---

## Overview

`pdfscanner` is a macOS CLI tool that reads a PDF file, extracts topic-structured content (sentences + highlighted vocabulary), and produces:

- **M4A audio files** per topic (English TTS via `say` + `afconvert`)
- **Markdown reports** with highlighted vocabulary, definitions, and example sentences

Primary use case: IELTS study material processing (speaking topics, writing opinion banks, vocabulary books).

---

## CLI Interface

```
pdfscanner scan <PDF路径> [options]

Options:
  --start-page N        Start page, 1-based (default: 1)
  --end-page N          End page, 1-based (default: last page)
  --topics "1,2,广告"   Filter topics; integers match by number, strings match by name (fuzzy)
  --ocr                 Force Apple Vision OCR (default: auto-detect)
  --password PWD        PDF password
  --audio               Generate M4A audio per topic
  --markdown            Generate Markdown vocabulary report
  --output DIR          Output directory (default: ./output)
  --voice-en VOICE      English TTS voice (default: Samantha)
  --voice-zh VOICE      Chinese TTS voice (default: Tingting)
  --workers N           Parallel say processes (default: 8)
```

**Examples:**

```bash
# Encrypted PDF, pages 5-6, audio + markdown
pdfscanner scan report.pdf --start-page 5 --end-page 6 \
  --password ref790 --audio --markdown --output ~/Desktop/out

# Image-based PDF, first 4 topics only, force OCR
pdfscanner scan 口语900句.pdf --start-page 2 --topics "1,2,3,4" \
  --ocr --audio --markdown --output ~/Documents/雅思/口语
```

---

## Architecture

```
pdfscanner/
├── __main__.py     # python -m pdfscanner entry
├── cli.py          # argparse, parameter validation, orchestration
├── extractor.py    # PDF open / page range / topic detection / highlight extraction
├── ocr.py          # Apple Vision OCR wrapper (macOS only, lazy import)
├── audio.py        # macOS say + afconvert → M4A
└── report.py       # Markdown rendering and file output
```

### Core Data Structure

```python
@dataclass
class Topic:
    num: int | str        # topic number or name key
    name: str             # display name
    sentences: list[str]  # body sentences
    highlights: list[str] # highlighted vocabulary words
```

### Module Contracts

| Module | Input | Output |
|--------|-------|--------|
| `extractor` | PDF path, page range, password | `list[Topic]` |
| `ocr` | image path, languages | `list[str]` |
| `audio` | `list[Topic]`, output dir, voices | list of M4A file paths |
| `report` | `list[Topic]`, output dir | `.md` file path |
| `cli` | argv | calls modules, prints progress |

---

## Processing Pipeline

```
cli: parse args
  │
  ▼
extractor.open_pdf()
  ├─ text-based  ──► page.get_text()
  └─ image-based ──► ocr.recognize_page()
  │
  ▼
extractor.detect_topics()      # color rects + regex, page range only
  │
  ▼
extractor.extract()            # sentences + highlights per topic
  │
  ├─ filter by --topics
  │
  ├─ --audio   ──► audio.generate()    one M4A per topic
  └─ --markdown ──► report.generate()  one .md for all topics
```

### Topic Detection Strategy (priority order)

1. **Pure yellow fill** (`r>0.95, g>0.95, b<0.10`) → OCR crop → topic name
2. **Light yellow fill** (`r>0.95, g>0.95, 0.30<b<0.70`) → highlight word
3. **Numbered section regex** → matches `1. Title` / `Chapter N` / `话题N` in page text

### Output Naming

```
output/
  Topic_01_自己.m4a
  Topic_02_家庭.m4a
  highlights.md
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Wrong PDF password | Exit immediately with clear message |
| Page range out of bounds | Clamp to actual page count, print warning |
| No topics found | Print warning, output raw sentences if any |
| `say` / `afconvert` not found | Print "requires macOS", exit |
| `--ocr` on non-macOS | Print "--ocr requires macOS", exit |
| Single TTS segment fails | Replace with silence segment, continue |
| Output dir missing | Auto-create |

---

## Dependencies

```toml
[project]
name = "pdfscanner"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pymupdf>=1.24",
    "pillow>=10",
    "pyobjc-framework-Vision",  # macOS only, lazy-imported when --ocr used
]

[project.scripts]
pdfscanner = "pdfscanner.cli:main"
```

`pyobjc-framework-Vision` is only imported at runtime when OCR is triggered; non-macOS users processing text-based PDFs are unaffected.

---

## Out of Scope (v0.1)

- GUI / web interface
- Non-macOS TTS engines
- Export formats other than M4A and Markdown
- Vocabulary definition lookup (definitions are extracted from PDF content only)
