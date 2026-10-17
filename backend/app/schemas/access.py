from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import AccessMode


class AccessTagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AccessUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rocket_chat_user_id: str
    username: str
    display_name: str
    avatar_url: str | None
    is_admin: bool
    is_active: bool
    access_mode: AccessMode
    view_created_tasks: bool
    view_watched_tasks: bool
    access_tags: list[AccessTagRead]
    created_at: datetime
    updated_at: datetime


class AccessUserUpdate(BaseModel):
    access_mode: AccessMode
    tag_ids: list[int] = Field(default_factory=list, max_length=100)
    view_created_tasks: bool | None = None
    view_watched_tasks: bool | None = None
