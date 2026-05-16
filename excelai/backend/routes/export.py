from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from backend.models.schemas import ExportRequest, UserResponse
from backend.routes.auth import require_current_user
from backend.services.excel_service import create_excel_workbook
from backend.utils.helpers import csv_bytes

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/excel")
def export_excel(payload: ExportRequest, user: UserResponse = Depends(require_current_user)) -> StreamingResponse:
    try:
        workbook_bytes, filename = create_excel_workbook(payload.columns, payload.rows, payload.filename)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Excel export failed: {exc}") from exc

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        iter([workbook_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/csv")
def export_csv(payload: ExportRequest, user: UserResponse = Depends(require_current_user)) -> Response:
    try:
        data = csv_bytes(payload.columns, payload.rows)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"CSV export failed: {exc}") from exc

    filename = payload.filename or "ExcelAI_Export.csv"
    if not filename.lower().endswith(".csv"):
        filename += ".csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=data, media_type="text/plain; charset=utf-8", headers=headers)
