from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import Settings
from app.models.user import User

SESSION_COOKIE = "opstracker_session"
CSRF_COOKIE = "opstracker_csrf"
OAUTH_STATE_COOKIE = "opstracker_oauth_state"
ISSUER = "opstracker"
AUDIENCE = "opstracker-web"


def create_session_token(user: User, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": str(user.id),
        "rc_uid": user.rocket_chat_user_id,
        "username": user.username,
        "admin": user.is_admin,
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_ttl_minutes),
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    return jwt.encode(claims, settings.app_secret, algorithm="HS256")


def decode_session_token(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.app_secret,
        algorithms=["HS256"],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={"require": ["sub", "exp", "iat", "iss", "aud"]},
    )


def create_oauth_state(settings: Settings, destination: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    nonce = secrets.token_urlsafe(24)
    state = jwt.encode(
        {
            "nonce": nonce,
            "destination": destination,
            "iat": now,
            "exp": now + timedelta(minutes=10),
            "iss": ISSUER,
            "aud": "rocketchat-oauth",
        },
        settings.app_secret,
        algorithm="HS256",
    )
    return nonce, state


def decode_oauth_state(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.app_secret,
        algorithms=["HS256"],
        issuer=ISSUER,
        audience="rocketchat-oauth",
        options={"require": ["nonce", "exp", "iat", "destination"]},
    )


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)

