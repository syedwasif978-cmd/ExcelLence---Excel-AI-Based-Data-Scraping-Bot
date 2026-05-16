from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend.routes.auth import require_current_user
from backend.models.schemas import ExtractResponse, ImageExtractResponse, TextExtractRequest, UrlExtractRequest, UserResponse
from backend.services.groq_service import generate_table
from backend.services.ocr_service import extract_text_from_upload
from backend.services.scraper_service import scrape_url

router = APIRouter(prefix="/api/extract", tags=["extract"])


@router.post("/text", response_model=ExtractResponse)
async def extract_text(payload: TextExtractRequest, user: UserResponse = Depends(require_current_user)) -> ExtractResponse:
    result = generate_table("TEXT", payload.prompt)
    return ExtractResponse(
        columns=result["columns"],
        rows=result["rows"],
        confidence=result["confidence"],
        source_type="TEXT",
        warnings=result.get("warnings", []),
        table_title=result.get("table_title"),
    )


@router.post("/image", response_model=ImageExtractResponse)
async def extract_image(
    file: UploadFile = File(...),
    instruction: str = Form(""),
    user: UserResponse = Depends(require_current_user),
) -> ImageExtractResponse:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image file is empty")

    try:
        ocr = await extract_text_from_upload(file_bytes, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    result = generate_table("IMAGE", ocr["text"], instruction=instruction)
    return ImageExtractResponse(
        columns=result["columns"],
        rows=result["rows"],
        confidence=result["confidence"],
        source_type="IMAGE",
        warnings=result.get("warnings", []),
        table_title=result.get("table_title"),
        ocr_raw_text=ocr["text"],
    )


@router.post("/url", response_model=ExtractResponse)
async def extract_url(payload: UrlExtractRequest, user: UserResponse = Depends(require_current_user)) -> ExtractResponse:
    try:
        scraped = await scrape_url(str(payload.url))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unable to scrape URL: {exc}") from exc

    result = generate_table("URL", scraped["content"], clarification=payload.clarification or scraped["title"])
    return ExtractResponse(
        columns=result["columns"],
        rows=result["rows"],
        confidence=result["confidence"],
        source_type="URL",
        warnings=result.get("warnings", []),
        table_title=result.get("table_title") or scraped["title"],
    )
