"""
PDF page renderer for the X-Ray preview pane.

PyMuPDF (`fitz`) opens the source PDF and rasterises individual pages
to PNG bytes at a configurable DPI. Per-page metadata (width / height
in PDF points) is exposed alongside so the frontend can compute
bbox → pixel transforms for the overlay layer.

PDF coordinates are top-left origin in points; PNGs are rendered with
`y0/y1` matching PDF order (PyMuPDF default — `Page.get_pixmap` uses
top-left origin in pixel space at the requested zoom).

Caching: PyMuPDF document objects are cheap to open; we don't cache
across requests for the POC. If profile shows hot-path overhead,
add an LRU dict keyed on (path, mtime).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass(frozen=True)
class PageMetadata:
    page: int            # 1-indexed
    width_pt: float      # PDF page width in points (origin top-left)
    height_pt: float
    width_px: int        # rendered PNG width at the chosen DPI
    height_px: int
    dpi: int


_DEFAULT_DPI = 144  # 2× standard 72dpi → crisp on retina, ~3× iframe sharpness


def _zoom_for_dpi(dpi: int) -> float:
    """PyMuPDF `Matrix(zoom, zoom)` factor — PDF default is 72dpi."""
    return dpi / 72.0


def open_document(pdf_path: Path) -> fitz.Document:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return fitz.open(str(pdf_path))


def page_metadata(pdf_path: Path, *, dpi: int = _DEFAULT_DPI) -> list[PageMetadata]:
    """One PageMetadata per page in the document."""
    out: list[PageMetadata] = []
    doc = open_document(pdf_path)
    try:
        zoom = _zoom_for_dpi(dpi)
        for i, page in enumerate(doc):
            rect = page.rect
            out.append(
                PageMetadata(
                    page=i + 1,
                    width_pt=float(rect.width),
                    height_pt=float(rect.height),
                    width_px=int(round(rect.width * zoom)),
                    height_px=int(round(rect.height * zoom)),
                    dpi=dpi,
                )
            )
    finally:
        doc.close()
    return out


def render_page_png(pdf_path: Path, page_number: int, *, dpi: int = _DEFAULT_DPI) -> bytes:
    """
    Render a single page (1-indexed) as PNG bytes.

    Raises:
      FileNotFoundError if the PDF doesn't exist.
      IndexError if `page_number` is out of range.
    """
    doc = open_document(pdf_path)
    try:
        if page_number < 1 or page_number > len(doc):
            raise IndexError(
                f"page {page_number} out of range; document has {len(doc)} pages"
            )
        page = doc.load_page(page_number - 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(_zoom_for_dpi(dpi), _zoom_for_dpi(dpi)))
        return pix.tobytes("png")
    finally:
        doc.close()
