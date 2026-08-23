from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, str]:
    database = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    rocketchat = "unavailable"
    try:
        response = httpx.get(f"{settings.rocketchat_url.rstrip('/')}/api/info", timeout=3)
        rocketchat = "ok" if response.is_success else "unavailable"
    except httpx.HTTPError:
        pass
    return {
        "status": "ok" if database == "ok" else "error",
        "database": database,
        "rocketchat": rocketchat,
    }

