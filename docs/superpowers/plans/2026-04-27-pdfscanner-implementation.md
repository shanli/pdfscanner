# pdfscanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS CLI tool (`pdfscanner scan`) that extracts topic-structured content from PDFs and produces M4A audio files and Markdown vocabulary reports.

**Architecture:** Five focused modules (`extractor`, `ocr`, `audio`, `report`, `cli`) share a single `Topic` dataclass defined in `extractor.py`. The CLI orchestrates them; each module is independently testable via mocking or synthetic fixtures.

**Tech Stack:** Python 3.11+, PyMuPDF (fitz), Pillow, pyobjc-framework-Vision (macOS/OCR), macOS `say` + `afconvert`, pytest

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `pdfscanner/__main__.py`
- Create: `pdfscanner/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "pdfscanner"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pymupdf>=1.24",
    "pillow>=10",
    "pyobjc-framework-Vision; sys_platform == 'darwin'",
]

[project.scripts]
pdfscanner = "pdfscanner.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create package entry files**

`pdfscanner/__init__.py` — empty file.

`pdfscanner/__main__.py`:
```python
from pdfscanner.cli import main
main()
```

`tests/__init__.py` — empty file.

- [ ] **Step 3: Install in editable mode**

```bash
cd /Users/dashan/Documents/daily/pdfscanner
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pip install pytest
```

- [ ] **Step 4: Verify install**

```bash
python -m pdfscanner --help 2>&1 | head -5
```
Expected: error about missing `cli.py` (module not found) — confirms package loads.

- [ ] **Step 5: Commit**

```bash
cd /Users/dashan/Documents/daily/pdfscanner
git add pyproject.toml pdfscanner/ tests/
git commit -m "chore: project scaffold"
```

---

## Task 2: Topic Dataclass + Extractor Skeleton

**Files:**
- Create: `pdfscanner/extractor.py`
- Create: `tests/conftest.py`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Write failing test for Topic dataclass**

`tests/test_extractor.py`:
```python
from pdfscanner.extractor import Topic

def test_topic_defaults():
    t = Topic(num=1, name="自己")
    assert t.num == 1
    assert t.name == "自己"
    assert t.sentences == []
    assert t.highlights == []

def test_topic_with_data():
    t = Topic(num="Advertising", name="Advertising",
              sentences=["Ads inform us."], highlights=["inform"])
    assert len(t.sentences) == 1
    assert t.highlights[0] == "inform"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/dashan/Documents/daily/pdfscanner
pytest tests/test_extractor.py -v 2>&1 | tail -10
```
Expected: `ImportError: cannot import name 'Topic' from 'pdfscanner.extractor'`

- [ ] **Step 3: Implement Topic + open_pdf skeleton**

`pdfscanner/extractor.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
import fitz  # PyMuPDF


@dataclass
class Topic:
    num: int | str
    name: str
    sentences: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)


def open_pdf(path: str, password: str | None = None) -> fitz.Document:
    """Open a PDF, authenticate if needed. Raises ValueError on bad password."""
    doc = fitz.open(path)
    if doc.needs_pass:
        if not password or not doc.authenticate(password):
            raise ValueError(f"PDF requires a valid password: {path}")
    return doc


def is_text_based(doc: fitz.Document, sample_pages: int = 3) -> bool:
    """Return True if the PDF has extractable text (not image-only)."""
    pages_to_check = min(sample_pages, len(doc))
    total_chars = sum(
        len(doc[i].get_text().strip()) for i in range(pages_to_check)
    )
    return total_chars > 50 * pages_to_check
```

- [ ] **Step 4: Create conftest.py with synthetic PDF fixture**

`tests/conftest.py`:
```python
import pytest
import fitz
import tempfile
import os


@pytest.fixture
def text_pdf(tmp_path):
    """A simple text-based PDF with two numbered sections."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "1. Advertising", fontsize=14)
    page.insert_text((50, 80), "Advertising informs consumers.", fontsize=11)
    page.insert_text((50, 110), "2. Animal Rights", fontsize=14)
    page.insert_text((50, 140), "Animals deserve protection.", fontsize=11)
    path = str(tmp_path / "sample.pdf")
    doc.save(path)
    doc.close()
    return path
```

- [ ] **Step 5: Add open_pdf and is_text_based tests**

Append to `tests/test_extractor.py`:
```python
from pdfscanner.extractor import open_pdf, is_text_based

def test_open_pdf_no_password(text_pdf):
    doc = open_pdf(text_pdf)
    assert len(doc) == 1
    doc.close()

def test_open_pdf_bad_password(text_pdf):
    import pytest
    with pytest.raises(ValueError, match="requires a valid password"):
        open_pdf(text_pdf, password="wrong")

def test_is_text_based_true(text_pdf):
    doc = open_pdf(text_pdf)
    assert is_text_based(doc) is True
    doc.close()
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_extractor.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add pdfscanner/extractor.py tests/
git commit -m "feat: Topic dataclass + PDF open/detect"
```

---

## Task 3: Topic Detection

**Files:**
- Modify: `pdfscanner/extractor.py`
- Modify: `tests/test_extractor.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing tests for detect_topics**

Append to `tests/test_extractor.py`:
```python
from pdfscanner.extractor import detect_topics

def test_detect_topics_by_number(text_pdf):
    doc = open_pdf(text_pdf)
    topics = detect_topics(doc, start_page=0, end_page=0)
    doc.close()
    assert len(topics) == 2
    nums = [t.num for t in topics]
    assert 1 in nums
    assert 2 in nums

def test_detect_topics_names(text_pdf):
    doc = open_pdf(text_pdf)
    topics = detect_topics(doc, start_page=0, end_page=0)
    doc.close()
    names = [t.name for t in topics]
    assert "Advertising" in names
    assert "Animal Rights" in names
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_extractor.py::test_detect_topics_by_number -v
```
Expected: `ImportError` — `detect_topics` not defined.

- [ ] **Step 3: Implement detect_topics**

Add to `pdfscanner/extractor.py`:
```python
import re

# ── Color thresholds ────────────────────────────────────────────────────────
_TOPIC_YELLOW   = lambda r, g, b: r > 0.95 and g > 0.95 and b < 0.10
_HIGHLIGHT_YELL = lambda r, g, b: r > 0.95 and g > 0.95 and 0.30 < b < 0.70

# ── Regex for numbered sections ─────────────────────────────────────────────
_SECTION_RE = re.compile(
    r'^(\d+)\.\s+(.+)$'           # "1. Advertising"
    r'|^话题\s*(\d+)\s*([\u4e00-\u9fff]+)'   # "话题1 自己"
    r'|^Chapter\s+(\d+)\s*(.+)?$',            # "Chapter 1 Nature"
    re.MULTILINE,
)


def _color_topic_rects(page: fitz.Page) -> list[fitz.Rect]:
    rects = []
    for d in page.get_drawings():
        fill = d.get("fill")
        rect = d.get("rect")
        if not fill or not rect or len(fill) < 3:
            continue
        r, g, b = fill[0], fill[1], fill[2]
        if _TOPIC_YELLOW(r, g, b):
            rects.append(rect)
    return rects


def _merge_rects(rects: list[fitz.Rect]) -> list[list[float]]:
    """Merge adjacent same-row rectangles into single bounding boxes."""
    if not rects:
        return []
    s = sorted(rects, key=lambda rc: (rc.y0, rc.x0))
    groups = [[s[0].x0, s[0].y0, s[0].x1, s[0].y1]]
    for rc in s[1:]:
        g = groups[-1]
        if rc.y0 < g[3] + 6 and rc.y1 > g[1] - 6:
            g[0] = min(g[0], rc.x0); g[1] = min(g[1], rc.y0)
            g[2] = max(g[2], rc.x1); g[3] = max(g[3], rc.y1)
        else:
            groups.append([rc.x0, rc.y0, rc.x1, rc.y1])
    return groups


def detect_topics(
    doc: fitz.Document,
    start_page: int = 0,
    end_page: int | None = None,
    force_ocr: bool = False,
    ocr_fn=None,
) -> list[Topic]:
    """
    Detect topic boundaries in [start_page, end_page] (0-based, inclusive).
    Returns a list of Topic objects (sentences/highlights empty at this stage).
    ocr_fn: callable(image_path) -> list[str], used when force_ocr=True.
    """
    if end_page is None:
        end_page = len(doc) - 1
    end_page = min(end_page, len(doc) - 1)

    found: list[tuple[int, float, int | str, str]] = []  # (page, y, num, name)

    for page_idx in range(start_page, end_page + 1):
        page = doc[page_idx]

        # Strategy 1: color-coded yellow rects (image-based or styled PDFs)
        color_rects = _color_topic_rects(page)
        if color_rects:
            merged = _merge_rects(color_rects)
            for m in merged:
                clip = fitz.Rect(m[0] - 5, m[1], m[2] + 5, m[3])
                words = page.get_text("words", clip=clip)
                raw = " ".join(w[4] for w in words)
                mo = re.search(r'话题\s*(\d+)\s*([\u4e00-\u9fff]+)', raw)
                if mo:
                    found.append((page_idx, m[1], int(mo.group(1)), mo.group(2)))
                    continue
                mo2 = re.search(r'(\d+)\.\s+(.+)', raw)
                if mo2:
                    found.append((page_idx, m[1], int(mo2.group(1)), mo2.group(2).strip()))

        # Strategy 2: regex on extracted text (text-based PDFs)
        text = page.get_text()
        for mo in _SECTION_RE.finditer(text):
            if mo.group(1):   # "N. Title"
                num, name = int(mo.group(1)), mo.group(2).strip()
            elif mo.group(3):  # 话题N
                num, name = int(mo.group(3)), mo.group(4).strip()
            else:              # Chapter N
                num = int(mo.group(5))
                name = (mo.group(6) or f"Chapter {num}").strip()
            # approximate y from character position
            y_approx = page.rect.height * text[:mo.start()].count('\n') / max(text.count('\n'), 1)
            found.append((page_idx, y_approx, num, name))

    # Deduplicate by (num, name) keeping first occurrence
    seen: set[tuple] = set()
    topics: list[Topic] = []
    for _, _, num, name in sorted(found, key=lambda x: (x[0], x[1])):
        key = (num, name)
        if key not in seen:
            seen.add(key)
            topics.append(Topic(num=num, name=name))

    return topics
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_extractor.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdfscanner/extractor.py tests/test_extractor.py
git commit -m "feat: topic detection via color rects + regex"
```

---

## Task 4: Highlight & Sentence Extraction

**Files:**
- Modify: `pdfscanner/extractor.py`
- Modify: `tests/test_extractor.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_extractor.py`:
```python
from pdfscanner.extractor import extract

def test_extract_sentences(text_pdf):
    doc = open_pdf(text_pdf)
    topics = extract(doc, start_page=0, end_page=0)
    doc.close()
    ad = next(t for t in topics if t.name == "Advertising")
    assert any("informs" in s for s in ad.sentences)

def test_extract_topic_filter(text_pdf):
    doc = open_pdf(text_pdf)
    topics = extract(doc, start_page=0, end_page=0, topic_filter=["1"])
    doc.close()
    assert len(topics) == 1
    assert topics[0].num == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_extractor.py::test_extract_sentences -v
```
Expected: `ImportError` — `extract` not defined.

- [ ] **Step 3: Implement extract + filter helpers**

Add to `pdfscanner/extractor.py`:
```python
def _highlight_words_on_page(page: fitz.Page) -> list[tuple[float, str]]:
    """Return [(y_pdf, word)] for all light-yellow highlighted spans."""
    result = []
    for d in page.get_drawings():
        fill = d.get("fill")
        rect = d.get("rect")
        if not fill or not rect or len(fill) < 3:
            continue
        r, g, b = fill[0], fill[1], fill[2]
        if _HIGHLIGHT_YELL(r, g, b):
            words = page.get_text("words", clip=rect)
            w = " ".join(x[4] for x in words).strip()
            if w and len(w) > 1 and re.search(r'[a-zA-Z\u4e00-\u9fff]{2,}', w):
                result.append((rect.y0, w))
    return result


def _is_valid_sentence(text: str) -> bool:
    if len(text) < 10:
        return False
    if re.match(r'^(ielts|ideas for|chapter|\d+\s*$)', text.lower()):
        return False
    return len(re.findall(r'\b[a-zA-Z]{2,}\b', text)) >= 3


def _match_topic_filter(topic: Topic, filters: list[str]) -> bool:
    """Return True if topic matches any filter (number or fuzzy name)."""
    for f in filters:
        f = f.strip()
        if f.isdigit() and topic.num == int(f):
            return True
        if isinstance(topic.num, str) and f.lower() in topic.num.lower():
            return True
        if f.lower() in topic.name.lower():
            return True
    return False


def extract(
    doc: fitz.Document,
    start_page: int = 0,
    end_page: int | None = None,
    topic_filter: list[str] | None = None,
    force_ocr: bool = False,
    ocr_fn=None,
) -> list[Topic]:
    """
    Full extraction: detect topics, assign sentences and highlights.
    topic_filter: list of strings (numbers or names); None = all topics.
    Returns filtered list of Topic objects with sentences and highlights filled.
    """
    if end_page is None:
        end_page = len(doc) - 1
    end_page = min(end_page, len(doc) - 1)

    # Detect boundaries
    all_topics = detect_topics(doc, start_page, end_page, force_ocr, ocr_fn)
    if not all_topics:
        return []

    # Build sorted boundary list: (page_idx, y, topic_index)
    # Re-detect to get positions
    boundaries: list[tuple[int, float, int]] = []
    topic_map = {(t.num, t.name): i for i, t in enumerate(all_topics)}

    for page_idx in range(start_page, end_page + 1):
        page = doc[page_idx]
        text = page.get_text()
        for mo in _SECTION_RE.finditer(text):
            if mo.group(1):
                num, name = int(mo.group(1)), mo.group(2).strip()
            elif mo.group(3):
                num, name = int(mo.group(3)), mo.group(4).strip()
            else:
                num = int(mo.group(5))
                name = (mo.group(6) or f"Chapter {num}").strip()
            key = (num, name)
            if key in topic_map:
                y = page.rect.height * text[:mo.start()].count('\n') / max(text.count('\n'), 1)
                boundaries.append((page_idx, y, topic_map[key]))

    boundaries.sort(key=lambda x: (x[0], x[1]))

    def get_topic_index(page_idx: int, y: float) -> int | None:
        cur = None
        for bp, by, bi in boundaries:
            if (bp < page_idx) or (bp == page_idx and by <= y + 5):
                cur = bi
        return cur

    # Extract sentences and highlights per page
    for page_idx in range(start_page, end_page + 1):
        page = doc[page_idx]

        # Sentences
        if force_ocr and ocr_fn:
            lines = ocr_fn(page_idx)
        else:
            lines = [line.strip() for line in page.get_text().splitlines()]

        for line in lines:
            if not _is_valid_sentence(line):
                continue
            # Estimate y from line order (rough)
            ti = get_topic_index(page_idx, 100)  # conservative: assign to active topic
            if ti is not None:
                all_topics[ti].sentences.append(line)

        # Highlights
        for y, word in _highlight_words_on_page(page):
            ti = get_topic_index(page_idx, y)
            if ti is not None and word not in all_topics[ti].highlights:
                all_topics[ti].highlights.append(word)

    # Apply filter
    if topic_filter:
        return [t for t in all_topics if _match_topic_filter(t, topic_filter)]
    return all_topics
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_extractor.py -v
```
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdfscanner/extractor.py tests/test_extractor.py tests/conftest.py
git commit -m "feat: highlight and sentence extraction with topic filtering"
```

---

## Task 5: OCR Module

**Files:**
- Create: `pdfscanner/ocr.py`

- [ ] **Step 1: Create ocr.py**

`pdfscanner/ocr.py`:
```python
"""
Apple Vision OCR wrapper. macOS only.
Import is deferred so non-macOS users can still use text-based PDF mode.
"""
from __future__ import annotations
import os
import sys
import tempfile


def _check_macos():
    if sys.platform != "darwin":
        raise RuntimeError("--ocr requires macOS (Apple Vision framework)")


def recognize_page(
    page,  # fitz.Page
    langs: tuple[str, ...] = ("zh-Hans", "en-US"),
    dpi: int = 200,
) -> list[str]:
    """
    Render a fitz.Page to image and run Apple Vision OCR.
    Returns list of recognized text strings, sorted top-to-bottom.
    """
    _check_macos()

    try:
        import Vision
        from Foundation import NSURL
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            f"OCR dependencies missing: {e}. "
            "Install with: pip install pyobjc-framework-Vision pillow"
        ) from e

    # Render page to PNG
    pix = page.get_pixmap(dpi=dpi)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
    pix.save(tmp_path)

    try:
        url = NSURL.fileURLWithPath_(tmp_path)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLanguages_(list(langs))
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
        handler.performRequests_error_([req], None)

        page_h = page.rect.height
        rows: list[tuple[float, str]] = []
        for obs in req.results():
            candidates = obs.topCandidates_(1)
            if not candidates:
                continue
            text = candidates[0].string().strip()
            if not text:
                continue
            bb = obs.boundingBox()
            y_center = bb.origin.y + bb.size.height / 2
            y_pdf = page_h * (1 - y_center)
            rows.append((y_pdf, text))

        rows.sort(key=lambda x: x[0])
        return [t for _, t in rows]
    finally:
        os.unlink(tmp_path)
```

- [ ] **Step 2: Verify import works on macOS**

```bash
python -c "from pdfscanner.ocr import recognize_page; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pdfscanner/ocr.py
git commit -m "feat: Apple Vision OCR wrapper"
```

---

## Task 6: Audio Generation

**Files:**
- Create: `pdfscanner/audio.py`
- Create: `tests/test_audio.py`

- [ ] **Step 1: Write failing tests**

`tests/test_audio.py`:
```python
import os
import pytest
from unittest.mock import patch, MagicMock
from pdfscanner.audio import build_script, generate
from pdfscanner.extractor import Topic


def test_build_script_contains_topic_name():
    t = Topic(num=1, name="自己", sentences=["I enjoy reading books."], highlights=[])
    script = build_script(t, voice_en="Samantha")
    assert "自己" in script or "Topic 1" in script
    assert "I enjoy reading books" in script


def test_build_script_excludes_short_sentences():
    t = Topic(num=1, name="Test", sentences=["Hi.", "I enjoy long walks in the park."], highlights=[])
    script = build_script(t, voice_en="Samantha")
    assert "Hi." not in script
    assert "I enjoy long walks" in script


def test_generate_calls_say(tmp_path):
    t = Topic(num=1, name="Ads", sentences=["Advertising informs consumers."], highlights=[])
    with patch("pdfscanner.audio._say_to_m4a") as mock_say:
        mock_say.return_value = str(tmp_path / "Topic_01_Ads.m4a")
        results = generate([t], output_dir=str(tmp_path))
    mock_say.assert_called_once()
    assert len(results) == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_audio.py -v
```
Expected: `ImportError` — `audio` module not defined.

- [ ] **Step 3: Implement audio.py**

`pdfscanner/audio.py`:
```python
from __future__ import annotations
import os
import re
import sys
import wave
import subprocess
import tempfile
from pdfscanner.extractor import Topic


def _check_macos():
    if sys.platform != "darwin":
        raise RuntimeError("Audio generation requires macOS (say + afconvert)")


def build_script(topic: Topic, voice_en: str = "Samantha") -> str:
    """Build the say-compatible script for a topic."""
    lines = [f"Topic {topic.num}. {topic.name}. [[slnc 1000]]"]
    for s in topic.sentences:
        # Strip Chinese characters and trailing noise
        en = re.sub(r'[\u4e00-\u9fff].*', '', s).strip(" .•·")
        en = re.sub(r'\s+', ' ', en)
        if len(en) < 8:
            continue
        lines.append(f"{en}. [[slnc 800]]")
    return "\n".join(lines)


def _say_to_m4a(
    script: str,
    voice: str,
    out_path: str,
    workers: int = 8,
) -> str:
    """Write script to temp file, call say once, convert to M4A."""
    _check_macos()
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "script.txt")
        aiff_path   = os.path.join(tmpdir, "out.aiff")
        wav_path    = os.path.join(tmpdir, "out.wav")

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        subprocess.run(
            ["say", "-v", voice, "-o", aiff_path, "-f", script_path],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["afconvert", aiff_path, wav_path,
             "-f", "WAVE", "-d", "LEI16@22050", "-c", "1"],
            check=True, capture_output=True,
        )
        r = subprocess.run(
            ["afconvert", wav_path, out_path, "-f", "m4af", "-d", "aac "],
            capture_output=True,
        )
        if r.returncode != 0:
            # fallback: keep wav
            import shutil
            wav_out = out_path.replace(".m4a", ".wav")
            shutil.copy(wav_path, wav_out)
            return wav_out
    return out_path


def generate(
    topics: list[Topic],
    output_dir: str,
    voice_en: str = "Samantha",
    workers: int = 8,
) -> list[str]:
    """
    Generate one M4A per topic. Returns list of output file paths.
    Skips topics with no sentences.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for t in topics:
        if not t.sentences:
            continue
        safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', t.name)
        out_path = os.path.join(output_dir, f"Topic_{t.num:02d}_{safe_name}.m4a"
                                if isinstance(t.num, int)
                                else f"Topic_{safe_name}.m4a")
        script = build_script(t, voice_en=voice_en)
        path = _say_to_m4a(script, voice=voice_en, out_path=out_path, workers=workers)
        results.append(path)
        size = os.path.getsize(path) // 1024
        print(f"  {os.path.basename(path)}  {size}KB")
    return results
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_audio.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdfscanner/audio.py tests/test_audio.py
git commit -m "feat: audio generation via macOS say + afconvert"
```

---

## Task 7: Markdown Report

**Files:**
- Create: `pdfscanner/report.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write failing tests**

`tests/test_report.py`:
```python
import os
from pdfscanner.report import generate
from pdfscanner.extractor import Topic


def test_generate_creates_file(tmp_path):
    topics = [
        Topic(num=1, name="Advertising",
              sentences=["Advertising informs consumers."],
              highlights=["informs", "consumers"]),
    ]
    path = generate(topics, output_dir=str(tmp_path))
    assert os.path.exists(path)


def test_markdown_contains_topic_name(tmp_path):
    topics = [Topic(num=1, name="Advertising",
                    sentences=["Ads inform us."], highlights=["inform"])]
    path = generate(topics, output_dir=str(tmp_path))
    content = open(path, encoding="utf-8").read()
    assert "Advertising" in content


def test_markdown_highlights_table(tmp_path):
    topics = [Topic(num=1, name="Ads",
                    sentences=[], highlights=["manipulates", "glamorous"])]
    path = generate(topics, output_dir=str(tmp_path))
    content = open(path, encoding="utf-8").read()
    assert "manipulates" in content
    assert "glamorous" in content
    assert "|" in content  # table format


def test_markdown_sentences_listed(tmp_path):
    topics = [Topic(num=1, name="Ads",
                    sentences=["Advertising informs consumers."], highlights=[])]
    path = generate(topics, output_dir=str(tmp_path))
    content = open(path, encoding="utf-8").read()
    assert "Advertising informs consumers" in content
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_report.py -v
```
Expected: `ImportError` — `report` not defined.

- [ ] **Step 3: Implement report.py**

`pdfscanner/report.py`:
```python
from __future__ import annotations
import os
import re
from pdfscanner.extractor import Topic


def generate(
    topics: list[Topic],
    output_dir: str,
    filename: str = "highlights.md",
) -> str:
    """Render topics to a Markdown file. Returns the output file path."""
    os.makedirs(output_dir, exist_ok=True)
    lines = ["# PDF Scanner — Highlights Report", ""]

    for t in topics:
        lines += [f"## Topic {t.num}：{t.name}", ""]

        if t.highlights:
            lines += ["### 🔑 重点词汇", ""]
            lines += ["| 词汇 | 词性 | 中文释义 | 用法说明 | 搭配例句 |",
                      "|------|------|----------|----------|----------|"]
            for w in sorted(set(t.highlights)):
                lines.append(f"| **{w}** | — | — | — | — |")
            lines.append("")

        if t.sentences:
            lines += ["### 📝 句子", ""]
            for s in t.sentences:
                en = re.sub(r'[\u4e00-\u9fff].*', '', s).strip(" .•")
                zh_m = re.search(
                    r'[\u4e00-\u9fff][\u4e00-\u9fff\s，。！？、；：""''（）\w]*', s
                )
                zh = zh_m.group(0).strip() if zh_m else ""
                if not en:
                    continue
                lines.append(f"- {en}")
                if zh:
                    lines.append(f"  > {zh}")
            lines.append("")

    out_path = os.path.join(output_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Markdown → {out_path}")
    return out_path
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_report.py -v
```
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdfscanner/report.py tests/test_report.py
git commit -m "feat: markdown report generation"
```

---

## Task 8: CLI Wiring

**Files:**
- Create: `pdfscanner/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

`tests/test_cli.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from pdfscanner.cli import build_parser, main


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["scan", "report.pdf"])
    assert args.pdf == "report.pdf"
    assert args.start_page == 1
    assert args.end_page is None
    assert args.ocr is False
    assert args.audio is False
    assert args.markdown is False
    assert args.output == "./output"
    assert args.voice_en == "Samantha"
    assert args.voice_zh == "Tingting"
    assert args.workers == 8


def test_parser_all_options():
    parser = build_parser()
    args = parser.parse_args([
        "scan", "file.pdf",
        "--start-page", "5", "--end-page", "10",
        "--topics", "1,2,Advertising",
        "--ocr", "--password", "secret",
        "--audio", "--markdown",
        "--output", "/tmp/out",
        "--voice-en", "Alex",
        "--voice-zh", "Mei-Jia",
        "--workers", "4",
    ])
    assert args.start_page == 5
    assert args.end_page == 10
    assert args.topics == "1,2,Advertising"
    assert args.ocr is True
    assert args.password == "secret"
    assert args.audio is True
    assert args.markdown is True
    assert args.output == "/tmp/out"
    assert args.workers == 4


def test_main_no_output_flags(tmp_path, text_pdf):
    """Running without --audio or --markdown should warn but not crash."""
    with patch("sys.argv", ["pdfscanner", "scan", text_pdf,
                            "--output", str(tmp_path)]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == 1  # exits with error: nothing to do
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_cli.py::test_parser_defaults -v
```
Expected: `ImportError` — `cli` not defined.

- [ ] **Step 3: Implement cli.py**

`pdfscanner/cli.py`:
```python
from __future__ import annotations
import argparse
import sys
import os
from pdfscanner.extractor import open_pdf, extract, is_text_based


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdfscanner",
        description="Extract topics, audio, and highlights from PDF files.",
    )
    sub = parser.add_subparsers(dest="command")
    scan = sub.add_parser("scan", help="Scan a PDF and produce outputs")

    scan.add_argument("pdf", metavar="PDF", help="Path to PDF file")
    scan.add_argument("--start-page", type=int, default=1,
                      help="Start page, 1-based (default: 1)")
    scan.add_argument("--end-page", type=int, default=None,
                      help="End page, 1-based (default: last page)")
    scan.add_argument("--topics", type=str, default=None,
                      help='Comma-separated topic numbers or names, e.g. "1,2,Advertising"')
    scan.add_argument("--ocr", action="store_true",
                      help="Force Apple Vision OCR (default: auto-detect)")
    scan.add_argument("--password", type=str, default=None,
                      help="PDF password")
    scan.add_argument("--audio", action="store_true",
                      help="Generate M4A audio per topic")
    scan.add_argument("--markdown", action="store_true",
                      help="Generate Markdown vocabulary report")
    scan.add_argument("--output", type=str, default="./output",
                      help="Output directory (default: ./output)")
    scan.add_argument("--voice-en", type=str, default="Samantha",
                      help="English TTS voice (default: Samantha)")
    scan.add_argument("--voice-zh", type=str, default="Tingting",
                      help="Chinese TTS voice (default: Tingting)")
    scan.add_argument("--workers", type=int, default=8,
                      help="Parallel say processes (default: 8)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command != "scan":
        parser.print_help()
        sys.exit(0)

    if not args.audio and not args.markdown:
        print("Error: specify at least one output flag: --audio, --markdown", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.pdf):
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    # Convert 1-based page numbers to 0-based
    start = args.start_page - 1
    end = (args.end_page - 1) if args.end_page else None

    topic_filter = [t.strip() for t in args.topics.split(",")] if args.topics else None

    ocr_fn = None
    if args.ocr:
        from pdfscanner.ocr import recognize_page
        ocr_fn = recognize_page

    print(f"Opening: {args.pdf}")
    try:
        doc = open_pdf(args.pdf, password=args.password)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    text_mode = not args.ocr and is_text_based(doc)
    print(f"Mode: {'text' if text_mode else 'OCR'} | Pages {args.start_page}–{args.end_page or len(doc)}")

    print("Extracting topics...")
    topics = extract(
        doc,
        start_page=start,
        end_page=end,
        topic_filter=topic_filter,
        force_ocr=args.ocr,
        ocr_fn=ocr_fn,
    )

    if not topics:
        print("Warning: no topics found in the specified page range.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(topics)} topic(s):")
    for t in topics:
        print(f"  Topic {t.num} 《{t.name}》: {len(t.sentences)} sentences, {len(t.highlights)} highlights")

    os.makedirs(args.output, exist_ok=True)

    if args.audio:
        print("\nGenerating audio...")
        from pdfscanner.audio import generate as gen_audio
        gen_audio(topics, output_dir=args.output, voice_en=args.voice_en, workers=args.workers)

    if args.markdown:
        print("\nGenerating Markdown...")
        from pdfscanner.report import generate as gen_report
        gen_report(topics, output_dir=args.output)

    print(f"\nDone. Files saved to: {args.output}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cli.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdfscanner/cli.py tests/test_cli.py
git commit -m "feat: CLI wiring with argparse"
```

---

## Task 9: Full Test Suite + Push

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/dashan/Documents/daily/pdfscanner
pytest tests/ -v
```
Expected: all tests PASS, 0 failures.

- [ ] **Step 2: Smoke test with real PDF**

```bash
pdfscanner scan "/Users/dashan/Documents/雅思/考官写作观点库ielts-simon ebook (密码是ref790)1.pdf" \
  --start-page 5 --end-page 6 \
  --password ref790 \
  --markdown \
  --output /tmp/pdfscanner_test
cat /tmp/pdfscanner_test/highlights.md | head -30
```
Expected: Markdown output with Advertising and Animal Rights topics.

- [ ] **Step 3: Smoke test audio (macOS only)**

```bash
pdfscanner scan "/Users/dashan/Documents/雅思/考官写作观点库ielts-simon ebook (密码是ref790)1.pdf" \
  --start-page 5 --end-page 6 \
  --password ref790 \
  --audio \
  --output /tmp/pdfscanner_audio_test
ls -lh /tmp/pdfscanner_audio_test/
```
Expected: `.m4a` files present with non-zero size.

- [ ] **Step 4: Rename default branch to main and push**

```bash
cd /Users/dashan/Documents/daily/pdfscanner
git branch -m master main
git push -u origin main
```

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git status  # should be clean
```
