from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task import Priority, TaskStatus
from app.schemas.user import UserRead


def clean_tag_names(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        name = " ".join(raw.strip().lstrip("#").split())
        if not name:
            continue
        if len(name) > 64:
            raise ValueError("Tag must not exceed 64 characters")
        normalized = name.casefold()
        if normalized not in seen:
            seen.add(normalized)
            result.append(name)
    if len(result) > 20:
        raise ValueError("A task can have at most 20 tags")
    return result


class SourceFields(BaseModel):
    rocket_chat_room_id: str | None = Field(None, max_length=64)
    rocket_chat_room_name: str | None = Field(None, max_length=255)
    rocket_chat_room_type: str | None = Field(None, max_length=16)
    rocket_chat_message_id: str | None = Field(None, max_length=64)
    rocket_chat_thread_id: str | None = Field(None, max_length=64)
    rocket_chat_message_url: str | None = Field(None, max_length=2048)
    rocket_chat_message_author_id: str | None = Field(None, max_length=64)
    rocket_chat_message_author_username: str | None = Field(None, max_length=128)
    rocket_chat_message_timestamp: datetime | None = None
    rocket_chat_message_snippet: str | None = Field(None, max_length=4000)


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    description: str = Field("", max_length=20000)
    priority: Priority = Priority.NORMAL
    assignee_id: int | None = None
    due_date: datetime | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Title must not be empty")
        return value

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return clean_tag_names(value) or []


class IntegrationTaskCreate(TaskCreate, SourceFields):
    """Task input accepted only after Rocket.Chat integration authentication."""


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, max_length=20000)
    status: TaskStatus | None = None
    priority: Priority | None = None
    assignee_id: int | None = None
    due_date: datetime | None = None
    tags: list[str] | None = Field(None, max_length=20)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str] | None) -> list[str] | None:
        return clean_tag_names(value)


class AssignRequest(BaseModel):
    assignee_id: int | None


class TaskEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    actor: UserRead | None
    created_at: datetime
    event_metadata: dict[str, object]


class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment must not be empty")
        return value


class TaskCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body: str
    author: UserRead
    created_at: datetime


class TaskAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    content_type: str
    size_bytes: int
    uploaded_by: UserRead
    created_at: datetime


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TaskSummary(SourceFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TaskStatus
    priority: Priority
    creator: UserRead
    assignee: UserRead | None
    created_at: datetime
    updated_at: datetime
    due_date: datetime | None
    completed_at: datetime | None
    tags: list[TagRead] = []


class TaskRead(TaskSummary):
    events: list[TaskEventRead] = []
    comments: list[TaskCommentRead] = []
    attachments: list[TaskAttachmentRead] = []


class TaskList(BaseModel):
    items: list[TaskSummary]
    total: int
    limit: int
    offset: int


class DuplicateTaskResponse(BaseModel):
    detail: str
    existing_task: TaskRead
