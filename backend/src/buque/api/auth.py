from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.db import get_db
from buque.api.deps import CurrentUser
from buque.services.auth import (
    AuthError,
    authenticate_email,
    issue_token_response,
    register_email_user,
    upsert_google_user,
    user_to_dict,
    verify_google_credential,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=1)


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _auth_error_to_http(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    if not settings.password_auth_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="密码注册未启用")
    try:
        user = register_email_user(db, str(payload.email), payload.password)
        return TokenResponse(**issue_token_response(db, user))
    except AuthError as exc:
        raise _auth_error_to_http(exc) from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    if not settings.password_auth_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="密码登录未启用")
    try:
        user = authenticate_email(db, str(payload.email), payload.password)
        return TokenResponse(**issue_token_response(db, user))
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleAuthRequest, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    if not settings.google_auth_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google 登录未配置")
    try:
        info = verify_google_credential(payload.credential)
        user = upsert_google_user(
            db,
            google_sub=str(info["sub"]),
            email=str(info["email"]),
            display_name=info.get("name"),
            avatar_url=info.get("picture"),
        )
        return TokenResponse(**issue_token_response(db, user))
    except AuthError as exc:
        raise _auth_error_to_http(exc) from exc


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser) -> UserOut:
    return UserOut(**user_to_dict(current_user))
