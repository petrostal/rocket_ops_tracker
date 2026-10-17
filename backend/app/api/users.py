from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin, require_csrf
from app.config import Settings, get_settings
from app.database import get_db
from app.integrations.rocketchat.client import RocketChatClient
from app.models.user import AccessMode, User
from app.schemas.user import UserRead
from app.services.users import sync_users

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def users(
    search: str | None = Query(None, max_length=100),
    watcher_candidates: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[User]:
    query = select(User).where(User.is_active.is_(True))
    if watcher_candidates:
        query = query.where(or_(User.is_admin.is_(True), User.access_mode == AccessMode.ALL,
                               (User.access_mode != AccessMode.NONE) & User.view_watched_tasks.is_(True)))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(User.username.ilike(pattern), User.display_name.ilike(pattern)))
    return list(db.scalars(query.order_by(User.display_name).limit(100)).all())


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/sync")
def synchronize(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
    __: User = Depends(require_admin),
) -> dict[str, int]:
    return {"synchronized": sync_users(db, RocketChatClient(settings), settings)}

