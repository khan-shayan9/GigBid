"""Text from a PDF (a CV uploaded as PDF)."""

from pathlib import Path

from pypdf import PdfReader


def pdf_text(path: Path) -> str:
    return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
