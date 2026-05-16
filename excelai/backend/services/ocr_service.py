from __future__ import annotations

import io
from typing import Any

from PIL import Image, UnidentifiedImageError


def _is_pdf(filename: str | None, file_bytes: bytes) -> bool:
    if filename and filename.lower().endswith(".pdf"):
        return True
    return file_bytes.startswith(b"%PDF")


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("PDF support requires the pypdf package") from exc

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError("The uploaded PDF could not be read.") from exc

    extracted_pages = []
    for page in list(reader.pages)[:20]:
        page_text = page.extract_text() or ""
        page_text = page_text.strip()
        if page_text:
            extracted_pages.append(page_text)

    return "\n\n".join(extracted_pages).strip()


def _ocr_pdf_pages(file_bytes: bytes, max_pages: int = 10) -> str:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        raise RuntimeError("Scanned PDF OCR requires the PyMuPDF package") from exc

    try:
        import pytesseract
    except Exception as exc:
        raise RuntimeError("pytesseract is unavailable") from exc

    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("The uploaded PDF could not be opened.") from exc

    text_chunks: list[str] = []
    page_count = min(len(document), max_pages)
    for page_index in range(page_count):
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        page_text = pytesseract.image_to_string(image).strip()
        if page_text:
            text_chunks.append(page_text)

    return "\n\n".join(text_chunks).strip()


async def extract_text_from_upload(file_bytes: bytes, filename: str | None = None) -> dict[str, Any]:
    if _is_pdf(filename, file_bytes):
        text = _extract_text_from_pdf(file_bytes)
        if not text:
            text = _ocr_pdf_pages(file_bytes)
        if not text:
            raise ValueError("No readable text was found in the PDF.")
        return {
            "text": text,
            "metadata": {
                "filename": filename,
                "size_bytes": len(file_bytes),
                "file_type": "pdf",
            },
        }

    try:
        image = Image.open(io.BytesIO(file_bytes))
        image = image.convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Unsupported file format. Please upload a PDF, PNG, JPG, or WEBP file.") from exc

    try:
        import pytesseract
    except Exception as exc:
        raise RuntimeError("pytesseract is unavailable") from exc

    text = pytesseract.image_to_string(image)
    text = text.strip()
    return {
        "text": text,
        "metadata": {
            "filename": filename,
            "size_bytes": len(file_bytes),
            "file_type": "image",
        },
    }
