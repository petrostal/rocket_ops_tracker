from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import Priority


class AppUserContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rocket_chat_user_id: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    # Accepted for backward compatibility with already-installed app packages.
    # Authorization never trusts this value.
    roles: list[str] = Field(default_factory=list, max_length=100)
    avatar_url: str | None = Field(None, max_length=1024)


class RoomContext(BaseModel):
    room_id: str | None = Field(None, max_length=64)
    room_name: str | None = Field(None, max_length=255)
    room_type: str | None = Field(None, max_length=16)


class LaunchRequest(BaseModel):
    user: AppUserContext
    destination: str = Field("/kanban", pattern=r"^/(kanban|my|tasks|create)(?:[/?].*)?$")
    room: RoomContext | None = None


class MessageSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(min_length=1, max_length=64)
    room_name: str = Field(min_length=1, max_length=255)
    room_type: str = Field("c", max_length=16)
    message_id: str = Field(min_length=1, max_length=64)
    thread_id: str | None = Field(None, max_length=64)
    # Accepted for old app packages; the backend always regenerates the permalink.
    message_url: str | None = Field(None, max_length=2048)
    author_id: str = Field(min_length=1, max_length=64)
    author_username: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    text: str = Field(min_length=1, max_length=4000)


class MessageTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: AppUserContext
    source: MessageSource
    title: str = Field(min_length=1, max_length=500)
    description: str = Field("", max_length=20000)
    assignee: AppUserContext | None = None
    assignee_username: str | None = Field(None, max_length=128)
    priority: Priority = Priority.NORMAL
    due_date: datetime | None = None


class SlashTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: AppUserContext
    room: RoomContext
    command_text: str = Field(min_length=1, max_length=2000)


class IntegrationTaskResponse(BaseModel):
    id: int
    title: str
    status: str
    assignee_username: str | None
    url: str
    message: str
