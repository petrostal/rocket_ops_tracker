from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.task import Tag, Task, TaskAttachment, TaskEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AccessMode(str, enum.Enum):
    NONE = "NONE"
    ASSIGNED = "ASSIGNED"
    TAGS = "TAGS"
    ASSIGNED_OR_TAGS = "ASSIGNED_OR_TAGS"
    ALL = "ALL"


user_access_tags = Table(
    "user_access_tags",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    rocket_chat_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    view_created_tasks: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    view_watched_tasks: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_complete_tasks: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_mode: Mapped[AccessMode] = mapped_column(
        Enum(AccessMode, name="user_access_mode", native_enum=False),
        default=AccessMode.NONE,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    created_tasks: Mapped[list[Task]] = relationship(
        back_populates="creator", foreign_keys="Task.creator_id"
    )
    assigned_tasks: Mapped[list[Task]] = relationship(
        back_populates="assignee", foreign_keys="Task.assignee_id"
    )
    events: Mapped[list[TaskEvent]] = relationship(back_populates="actor")
    uploaded_attachments: Mapped[list[TaskAttachment]] = relationship(
        back_populates="uploaded_by", foreign_keys="TaskAttachment.uploaded_by_user_id"
    )
    access_tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary=user_access_tags, order_by="Tag.name"
    )
