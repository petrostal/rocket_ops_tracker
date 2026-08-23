from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import require_admin, require_csrf
from app.database import get_db
from app.models.task import Tag
from app.models.user import AccessMode, User
from app.schemas.access import AccessUserRead, AccessUserUpdate

router = APIRouter(prefix="/api/access", tags=["access"])


@router.get("/users", response_model=list[AccessUserRead])
def access_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .options(selectinload(User.access_tags))
            .order_by(User.is_admin.desc(), User.display_name, User.username)
        ).all()
    )


@router.patch("/users/{user_id}", response_model=AccessUserRead)
def update_access(
    user_id: int,
    data: AccessUserUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    __: User = Depends(require_admin),
) -> User:
    user = db.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.access_tags))
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    tag_ids = set(data.tag_ids)
    tags = list(db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all()) if tag_ids else []
    if len(tags) != len(tag_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "One or more tags do not exist")

    user.access_mode = data.access_mode
    user.access_tags = tags if data.access_mode in {AccessMode.TAGS, AccessMode.ASSIGNED_OR_TAGS} else []
    db.commit()
    return db.scalar(
        select(User).where(User.id == user.id).options(selectinload(User.access_tags))
    ) or user
