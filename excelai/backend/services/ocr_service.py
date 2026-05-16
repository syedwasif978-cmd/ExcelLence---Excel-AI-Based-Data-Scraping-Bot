from __future__ import annotations

import io
from typing import Any

from PIL import Image, UnidentifiedImageError


async def extract_text_from_upload(file_bytes: bytes, filename: str | None = None) -> dict[str, Any]:
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image = image.convert("RGB")
    except UnidentifiedImageError as exc:
        if filename and filename.lower().endswith(".pdf"):
            try:
                import fitz

                pdf = fitz.open(stream=file_bytes, filetype="pdf")
                page = pdf.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            except Exception as pdf_exc:
                raise ValueError("PDF OCR requires an available PDF rendering library") from pdf_exc
        else:
            raise ValueError("Unsupported image format") from exc

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
        },
    }
