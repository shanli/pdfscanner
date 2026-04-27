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
    clip=None,  # fitz.Rect | None — render only this region
) -> list[tuple[float, str]]:
    """
    Render a fitz.Page to image and run Apple Vision OCR.
    Returns list of (y_pdf, text) tuples sorted top-to-bottom.

    clip: optional fitz.Rect to render only a sub-region of the page.
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

    # Render page (or sub-region) to PNG
    pix = page.get_pixmap(dpi=dpi, clip=clip)
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

        # When a clip rect is given, Vision bounding boxes are relative to the
        # clip region. Map them back to full-page PDF coordinates.
        if clip is not None:
            region_h = clip.y1 - clip.y0
            region_y0 = clip.y0
        else:
            region_h = page.rect.height
            region_y0 = 0.0

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
            # Convert Vision normalized coords (origin bottom-left) to PDF y
            y_pdf = region_y0 + region_h * (1 - y_center)
            rows.append((y_pdf, text))

        rows.sort(key=lambda x: x[0])
        return rows  # list of (y_pdf, text) tuples
    finally:
        os.unlink(tmp_path)
