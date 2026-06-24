from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.orm import Session

from buque.config import get_settings
from buque.models.entities import User

password_hasher = PasswordHash((BcryptHasher(),))


class AuthError(Exception):
    pass


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token if isinstance(token, str) else token.decode()


def decode_access_token(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        sub = payload.get("sub")
        if not sub:
            raise AuthError("无效 token")
        return int(sub)
    except jwt.PyJWTError as exc:
        raise AuthError("无效 token") from exc


def user_to_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
    }


def touch_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)


def register_email_user(db: Session, email: str, password: str) -> User:
    normalized = email.strip().lower()
    existing = db.query(User).filter(User.email == normalized).first()
    if existing:
        raise AuthError("邮箱已注册")
    user = User(
        email=normalized,
        password_hash=hash_password(password),
        display_name=normalized.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_email(db: Session, email: str, password: str) -> User:
    normalized = email.strip().lower()
    user = db.query(User).filter(User.email == normalized).first()
    if not user or not user.password_hash:
        raise AuthError("邮箱或密码错误")
    if not verify_password(password, user.password_hash):
        raise AuthError("邮箱或密码错误")
    return user


def upsert_google_user(
    db: Session,
    *,
    google_sub: str,
    email: str,
    display_name: str | None,
    avatar_url: str | None,
) -> User:
    normalized = email.strip().lower()
    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user is None:
        user = db.query(User).filter(User.email == normalized).first()
    if user is None:
        user = User(email=normalized, google_sub=google_sub)
        db.add(user)
    user.google_sub = google_sub
    user.email = normalized
    if display_name:
        user.display_name = display_name
    if avatar_url:
        user.avatar_url = avatar_url
    db.commit()
    db.refresh(user)
    return user


def verify_google_credential(credential: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.google_client_id:
        raise AuthError("Google 登录未配置")
    try:
        info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise AuthError("Google 凭证无效") from exc
    if not info.get("email"):
        raise AuthError("Google 账号缺少邮箱")
    return info


def issue_token_response(db: Session, user: User) -> dict[str, Any]:
    touch_login(db, user)
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": user_to_dict(user),
    }
