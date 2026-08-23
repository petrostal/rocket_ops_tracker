from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rocket_chat_user_id: str
    username: str
    display_name: str
    avatar_url: str | None
    is_admin: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

