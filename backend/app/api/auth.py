from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import (
    CSRF_COOKIE,
    OAUTH_STATE_COOKIE,
    SESSION_COOKIE,
    create_csrf_token,
    create_oauth_state,
    create_session_token,
    decode_oauth_state,
)
from app.auth.dependencies import get_optional_current_user, require_csrf
from app.config import Settings, get_settings
from app.database import get_db
from app.integrations.rocketchat.client import RocketChatClient, RocketChatError
from app.models.integration import LaunchCode
from app.models.user import User
from app.services.users import upsert_oauth_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _safe_destination(value: str) -> str:
    allowed = ("/kanban", "/my", "/tasks", "/create", "/access")
    return value if any(value == item or value.startswith(f"{item}?") for item in allowed) else "/kanban"


def _set_session(response: Response, user: User, settings: Settings) -> None:
    secure = settings.public_url.startswith("https://")
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user, settings),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        create_csrf_token(),
        max_age=settings.session_ttl_minutes * 60,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


@router.get("/login")
def login(
    request: Request,
    next: str = Query("/kanban"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    destination = _safe_destination(next)
    if get_optional_current_user(request, db, settings) is not None:
        return RedirectResponse(destination)
    nonce, state_cookie = create_oauth_state(settings, destination)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.rocketchat_client_id,
            "redirect_uri": f"{settings.public_url.rstrip('/')}/api/auth/callback",
            "state": nonce,
        }
    )
    response = RedirectResponse(f"{settings.rocketchat_url.rstrip('/')}/oauth/authorize?{query}")
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state_cookie,
        max_age=600,
        httponly=True,
        secure=settings.public_url.startswith("https://"),
        samesite="lax",
        path="/api/auth",
    )
    return response


@router.get("/callback")
def callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE, "")
    try:
        state_data = decode_oauth_state(state_cookie, settings)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth state is invalid or expired") from exc
    if not secrets.compare_digest(str(state_data["nonce"]), state):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth state mismatch")
    try:
        client = RocketChatClient(settings)
        identity = client.oauth_identity(client.exchange_oauth_code(code))
        user = upsert_oauth_user(db, identity, settings)
    except (RocketChatError, ValueError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Rocket.Chat authentication failed") from exc
    response = RedirectResponse(_safe_destination(str(state_data["destination"])))
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/api/auth")
    _set_session(response, user, settings)
    return response


@router.get("/launch")
def consume_launch_code(
    request: Request,
    code: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    launch = db.scalar(select(LaunchCode).where(LaunchCode.code_hash == code_hash).with_for_update())
    now = datetime.now(timezone.utc)
    expires_at = launch.expires_at if launch is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if launch is None or launch.consumed_at is not None or expires_at is None or expires_at < now:
        current_user = get_optional_current_user(request, db, settings)
        if current_user is not None:
            destination = "/kanban"
            if launch is not None and launch.user_id == current_user.id:
                destination = _safe_destination(str(launch.context.get("destination", "/kanban")))
            return RedirectResponse(destination)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Launch link is invalid, expired, or already used")
    user = db.get(User, launch.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is not active")
    launch.consumed_at = now
    db.commit()
    destination = _safe_destination(str(launch.context.get("destination", "/kanban")))
    response = RedirectResponse(destination)
    _set_session(response, user, settings)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, _: None = Depends(require_csrf)) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
