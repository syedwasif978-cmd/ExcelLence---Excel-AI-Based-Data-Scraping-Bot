from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.routes.auth import router as auth_router
from backend.routes.extract import router as extract_router
from backend.routes.export import router as export_router

BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file (development) or system env (production)
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)

app = FastAPI(title="ExcelAI", version="1.0.0")

allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in allowed_origins else allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(extract_router)
app.include_router(export_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ExcelAI"}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "ExcelAI API is running"}


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        error = str(detail.get("error") or "Request failed")
        message = str(detail.get("detail") or detail.get("message") or "")
    else:
        error = "Request failed"
        message = str(detail)
    return JSONResponse(status_code=exc.status_code, content={"error": error, "detail": message})


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(exc)})
