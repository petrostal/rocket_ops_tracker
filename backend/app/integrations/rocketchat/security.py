from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.integration import IntegrationNonce


def verify_app_request(
    x_opstracker_secret: str = Header(""),
    x_opstracker_timestamp: str = Header(""),
    x_opstracker_nonce: str = Header(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_opstracker_secret or not secrets.compare_digest(
        x_opstracker_secret, settings.rocketchat_app_secret
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid integration credentials")
    try:
        timestamp = int(x_opstracker_timestamp)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid integration timestamp") from exc
    if abs(int(time.time()) - timestamp) > settings.integration_max_age_seconds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Integration request expired")
    if len(x_opstracker_nonce) < 16 or len(x_opstracker_nonce) > 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid integration nonce")

    nonce_hash = hashlib.sha256(x_opstracker_nonce.encode()).hexdigest()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.integration_max_age_seconds * 2)
    db.execute(delete(IntegrationNonce).where(IntegrationNonce.created_at < cutoff))
    db.add(IntegrationNonce(nonce_hash=nonce_hash))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Integration request was already used") from exc

