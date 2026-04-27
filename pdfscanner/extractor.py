from __future__ import annotations
from dataclasses import dataclass, field
import re
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


# ── Color thresholds ────────────────────────────────────────────────────────
_TOPIC_YELLOW   = lambda r, g, b: r > 0.95 and g > 0.95 and b < 0.10
_HIGHLIGHT_YELL = lambda r, g, b: r > 0.95 and g > 0.95 and 0.30 < b < 0.70

# ── Regex for numbered sections ─────────────────────────────────────────────
_SECTION_RE = re.compile(
    r'^(\d+)\.\s+(.+)$'
    r'|^话题\s*(\d+)\s*([\u4e00-\u9fff]+)'
    r'|^Chapter\s+(\d+)\s*(.+)?$',
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
    ocr_fn: callable(page) -> list[str], used when force_ocr=True.
    """
    if end_page is None:
        end_page = len(doc) - 1
    end_page = min(end_page, len(doc) - 1)

    found: list[tuple[int, float, int | str, str]] = []  # (page, y, num, name)

    for page_idx in range(start_page, end_page + 1):
        page = doc[page_idx]

        # Get page text — OCR or direct extraction
        if force_ocr and ocr_fn:
            page_text = "\n".join(t for _, t in ocr_fn(page))
        else:
            page_text = page.get_text()

        # Strategy 1: color-coded yellow rects (image-based or styled PDFs)
        color_rects = _color_topic_rects(page)
        if color_rects:
            merged = sorted(_merge_rects(color_rects), key=lambda m: m[1])  # sort by y
            if force_ocr:
                # Match rects to topic headers in order (both sorted top-to-bottom)
                hits = re.findall(r'话题\s*(\d+)\s*([\u4e00-\u9fff]+)', page_text)
                for m, (num_s, name) in zip(merged, hits):
                    found.append((page_idx, m[1], int(num_s), name))
            else:
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

        # Strategy 2: regex on page text (text PDF or OCR output)
        for mo in _SECTION_RE.finditer(page_text):
            if mo.group(1):   # "N. Title"
                num, name = int(mo.group(1)), mo.group(2).strip()
            elif mo.group(3):  # 话题N
                num, name = int(mo.group(3)), mo.group(4).strip()
            else:              # Chapter N
                num = int(mo.group(5))
                name = (mo.group(6) or f"Chapter {num}").strip()
            y_approx = page.rect.height * page_text[:mo.start()].count('\n') / max(page_text.count('\n'), 1)
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

    all_topics = detect_topics(doc, start_page, end_page, force_ocr, ocr_fn)
    if not all_topics:
        return []

    # Build boundary list with positions for topic assignment
    boundaries: list[tuple[int, float, int]] = []
    topic_map = {(t.num, t.name): i for i, t in enumerate(all_topics)}
    # Cache OCR results to avoid running OCR twice per page
    _ocr_cache: dict[int, list[tuple[float, str]]] = {}

    def _page_ocr_rows(page_idx: int) -> list[tuple[float, str]]:
        if page_idx not in _ocr_cache:
            _ocr_cache[page_idx] = ocr_fn(doc[page_idx])
        return _ocr_cache[page_idx]

    def _page_text(page_idx: int) -> str:
        if force_ocr and ocr_fn:
            return "\n".join(t for _, t in _page_ocr_rows(page_idx))
        return doc[page_idx].get_text()

    for page_idx in range(start_page, end_page + 1):
        page = doc[page_idx]
        if force_ocr and ocr_fn:
            # Image PDFs: use color rect y-positions (reliable) for boundary placement.
            # Match rects to topic headers in order (both sorted top-to-bottom by y).
            color_rects = _color_topic_rects(page)
            if color_rects:
                page_text = _page_text(page_idx)
                merged = sorted(_merge_rects(color_rects), key=lambda m: m[1])
                hits = re.findall(r'话题\s*(\d+)\s*([\u4e00-\u9fff]+)', page_text)
                for m, (num_s, name) in zip(merged, hits):
                    key = (int(num_s), name)
                    if key in topic_map:
                        boundaries.append((page_idx, m[1], topic_map[key]))
        else:
            text = _page_text(page_idx)
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
                    y = text[:mo.start()].count('\n') / max(text.count('\n'), 1) * page.rect.height
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

        if force_ocr and ocr_fn:
            ocr_rows = _page_ocr_rows(page_idx)
            for y, text in ocr_rows:
                line = text.strip()
                if not _is_valid_sentence(line):
                    continue
                ti = get_topic_index(page_idx, y)
                if ti is None and not boundaries:
                    ti = 0
                if ti is not None:
                    all_topics[ti].sentences.append(line)
        else:
            lines = [line.strip() for line in _page_text(page_idx).splitlines()]
            for line in lines:
                if not _is_valid_sentence(line):
                    continue
                ti = get_topic_index(page_idx, 100)
                if ti is None and not boundaries:
                    ti = 0
                if ti is not None:
                    all_topics[ti].sentences.append(line)

        for y, word in _highlight_words_on_page(page):
            ti = get_topic_index(page_idx, y)
            if ti is not None and word not in all_topics[ti].highlights:
                all_topics[ti].highlights.append(word)

    if topic_filter:
        return [t for t in all_topics if _match_topic_filter(t, topic_filter)]
    return all_topics
