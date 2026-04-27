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
