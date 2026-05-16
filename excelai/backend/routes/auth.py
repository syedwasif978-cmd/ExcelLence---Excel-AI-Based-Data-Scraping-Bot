from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.models.schemas import TokenResponse, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = os.getenv("ALGORITHM", "HS256")
SECRET_KEY = os.getenv("SECRET_KEY", "excelai-dev-secret")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

_DEMO_USERS = {
    "demo@excelai.dev": {
        "name": "Demo Analyst",
        "email": "demo@excelai.dev",
        "password_hash": bcrypt.hashpw(b"ExcelAI123!", bcrypt.gensalt()).decode("utf-8"),
    },
    "admin@excelai.dev": {
        "name": "Admin User",
        "email": "admin@excelai.dev",
        "password_hash": bcrypt.hashpw(b"AdminExcelAI123!", bcrypt.gensalt()).decode("utf-8"),
    },
}


def _create_token(email: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": email, "exp": expires}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _get_user_record(email: str) -> dict[str, Any] | None:
    return _DEMO_USERS.get(email.lower())


def _build_response(user_record: dict[str, Any]) -> TokenResponse:
    return TokenResponse(
        access_token=_create_token(user_record["email"]),
        user=UserResponse(name=user_record["name"], email=user_record["email"]),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin) -> TokenResponse:
    user_record = _get_user_record(payload.email)
    if not user_record or not bcrypt.checkpw(payload.password.encode("utf-8"), user_record["password_hash"].encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return _build_response(user_record)


@router.post("/signup", response_model=TokenResponse)
def signup(payload: UserCreate) -> TokenResponse:
    email = payload.email.lower()
    if email in _DEMO_USERS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    _DEMO_USERS[email] = {
        "name": payload.name,
        "email": email,
        "password_hash": bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
    }
    return _build_response(_DEMO_USERS[email])


@router.get("/me", response_model=UserResponse)
def me(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> UserResponse:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        decoded = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = decoded.get("sub")
        if not email:
            raise ValueError("Missing subject")
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is invalid or expired")
    user_record = _get_user_record(str(email))
    if not user_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return UserResponse(name=user_record["name"], email=user_record["email"])


def require_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> UserResponse:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        decoded = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = decoded.get("sub")
        if not email:
            raise ValueError("Missing subject")
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is invalid or expired")
    user_record = _get_user_record(str(email))
    if not user_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return UserResponse(name=user_record["name"], email=user_record["email"])
