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
    except ImportError as e:
        raise RuntimeError(
            f"OCR dependencies missing: {e}. "
            "Install with: pip install pyobjc-framework-Vision"
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
