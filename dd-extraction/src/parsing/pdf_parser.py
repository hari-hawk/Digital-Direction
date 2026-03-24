"""
PDF parser: extracts text from PDFs using pdfplumber.
Falls back to image extraction for scanned/image-only PDFs.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber


@dataclass
class PdfPage:
    page_number: int
    text: str
    tables: list[list[list[str]]]
    has_text: bool
    width: float
    height: float


@dataclass
class PdfResult:
    path: Path
    pages: list[PdfPage]
    is_scanned: bool  # True if no text layer detected
    total_pages: int

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)

    @property
    def all_tables(self) -> list[list[list[str]]]:
        tables = []
        for p in self.pages:
            tables.extend(p.tables)
        return tables


def parse_pdf(path: Path) -> PdfResult:
    """
    Extract text and tables from a PDF file.
    Detects if the PDF is scanned (image-only) by checking for text content.
    """
    path = Path(path)
    pages = []
    total_chars = 0

    with pdfplumber.open(path) as pdf:
        total_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            total_chars += len(text.strip())

            pages.append(PdfPage(
                page_number=i + 1,
                text=text,
                tables=tables,
                has_text=bool(text.strip()),
                width=page.width,
                height=page.height,
            ))

    # If total extracted text is very short, likely a scanned PDF
    is_scanned = total_chars < 50

    return PdfResult(
        path=path,
        pages=pages,
        is_scanned=is_scanned,
        total_pages=total_pages,
    )


def extract_pdf_page_images(path: Path, dpi: int = 200) -> list[bytes]:
    """
    Convert PDF pages to images (PNG bytes) for OCR processing.
    Uses PyMuPDF (fitz) — no poppler dependency required.
    Falls back to pdf2image if fitz is not available.
    """
    # Try PyMuPDF first (no external dependencies)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        result = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            result.append(pix.tobytes("png"))
        doc.close()
        return result
    except ImportError:
        pass  # Fall through to pdf2image

    # Fallback: pdf2image (requires poppler)
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(path), dpi=dpi)
        result = []
        for img in images:
            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            result.append(buf.getvalue())
        return result
    except ImportError:
        raise ImportError(
            "Neither PyMuPDF nor pdf2image available. "
            "Install with: pip install PyMuPDF (recommended) or pip install pdf2image + poppler"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to convert PDF to images: {e}")
