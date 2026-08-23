from __future__ import annotations

import secrets

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.tokens import CSRF_COOKIE, SESSION_COOKIE, decode_session_token
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User


def get_optional_current_user(
    request: Request,
    db: Session,
    settings: Settings,
) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        claims = decode_session_token(token, settings)
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.rocket_chat_user_id != claims.get("rc_uid"):
        return None
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    user = get_optional_current_user(request, db, settings)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return user


def require_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("X-CSRF-Token", "")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator permission required")
    return user
