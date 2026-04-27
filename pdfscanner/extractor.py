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
