from __future__ import annotations

import shlex
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.integrations.rocketchat.permalinks import message_permalink
from app.integrations.rocketchat.security import verify_app_request
from app.models.task import Priority, Task
from app.models.user import User
from app.schemas.integration import (
    IntegrationTaskResponse,
    LaunchRequest,
    MessageTaskRequest,
    SlashTaskRequest,
)
from app.schemas.task import IntegrationTaskCreate
from app.services.notifications import notify_created
from app.services.tasks import DuplicateSourceTask, create_task
from app.services.users import upsert_app_user

router = APIRouter(prefix="/api/integrations/rocketchat", tags=["rocketchat-integration"])


def _task_response(task: Task, settings: Settings, message: str) -> IntegrationTaskResponse:
    return IntegrationTaskResponse(
        id=task.id,
        title=task.title,
        status=task.status.value,
        assignee_username=task.assignee.username if task.assignee else None,
        url=f"{settings.public_url.rstrip('/')}/tasks/{task.id}",
        message=message,
    )


def _assignee_by_username(db: Session, username: str | None) -> User | None:
    if not username:
        return None
    return db.scalar(select(User).where(User.username == username.lstrip("@"), User.is_active.is_(True)))


@router.post("/launch")
def launch(
    data: LaunchRequest,
    settings: Settings = Depends(get_settings),
    _: None = Depends(verify_app_request),
) -> dict[str, str | int]:
    return {
        "url": f"{settings.public_url.rstrip('/')}/api/auth/login?{urlencode({'next': data.destination})}",
        "expires_in": 0,
    }


@router.post("/task-from-message", response_model=IntegrationTaskResponse, status_code=status.HTTP_201_CREATED)
def task_from_message(
    data: MessageTaskRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(verify_app_request),
) -> IntegrationTaskResponse:
    actor = upsert_app_user(db, data.user, settings)
    assignee = upsert_app_user(db, data.assignee, settings) if data.assignee else _assignee_by_username(db, data.assignee_username)
    if data.assignee_username and assignee is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown assignee @{data.assignee_username.lstrip('@')}")
    source = data.source
    source_url = message_permalink(
        settings.rocketchat_url,
        source.room_name,
        source.room_type,
        source.message_id,
        source.author_username,
    )
    try:
        task = create_task(
            db,
            IntegrationTaskCreate(
                title=data.title,
                description=data.description,
                priority=data.priority,
                assignee_id=assignee.id if assignee else None,
                due_date=data.due_date,
                rocket_chat_room_id=source.room_id,
                rocket_chat_room_name=source.room_name,
                rocket_chat_room_type=source.room_type,
                rocket_chat_message_id=source.message_id,
                rocket_chat_thread_id=source.thread_id,
                rocket_chat_message_url=source_url,
                rocket_chat_message_author_id=source.author_id,
                rocket_chat_message_author_username=source.author_username,
                rocket_chat_message_timestamp=source.timestamp,
                rocket_chat_message_snippet=source.text,
            ),
            actor,
        )
    except DuplicateSourceTask as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": str(exc),
                "existing_task_id": exc.task.id,
                "existing_task_title": exc.task.title,
                "existing_task_status": exc.task.status.value,
                "url": f"{settings.public_url.rstrip('/')}/tasks/{exc.task.id}",
            },
        ) from exc
    notify_created(task, settings)
    return _task_response(task, settings, f"Задача #{task.id} создана")


def _due_date(value: str) -> datetime:
    today = datetime.now(timezone.utc).date()
    if value == "today":
        date_value = today
    elif value == "tomorrow":
        date_value = today + timedelta(days=1)
    else:
        try:
            date_value = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "due must be YYYY-MM-DD, today, or tomorrow") from exc
    return datetime.combine(date_value, time(23, 59), tzinfo=timezone.utc)


def _parse_slash(text: str) -> tuple[str, str | None, Priority, datetime | None]:
    assignee: str | None = None
    priority = Priority.NORMAL
    due: datetime | None = None
    title_parts: list[str] = []
    for part in shlex.split(text):
        if part.startswith("@") and assignee is None:
            assignee = part[1:]
        elif part.lower().startswith("priority:"):
            try:
                priority = Priority(part.split(":", 1)[1].upper())
            except ValueError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "priority must be low, normal, high, or critical") from exc
        elif part.lower().startswith("due:"):
            due = _due_date(part.split(":", 1)[1].lower())
        else:
            title_parts.append(part)
    title = " ".join(title_parts).strip()
    if not title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Task title is required")
    return title, assignee, priority, due


@router.post("/slash-command", response_model=IntegrationTaskResponse, status_code=status.HTTP_201_CREATED)
def slash_command(
    data: SlashTaskRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(verify_app_request),
) -> IntegrationTaskResponse:
    actor = upsert_app_user(db, data.user, settings)
    title, assignee_username, priority, due = _parse_slash(data.command_text)
    assignee = _assignee_by_username(db, assignee_username)
    if assignee_username and assignee is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown assignee @{assignee_username}")
    task = create_task(
        db,
        IntegrationTaskCreate(
            title=title,
            priority=priority,
            due_date=due,
            assignee_id=assignee.id if assignee else None,
            rocket_chat_room_id=data.room.room_id,
            rocket_chat_room_name=data.room.room_name,
            rocket_chat_room_type=data.room.room_type,
        ),
        actor,
    )
    notify_created(task, settings)
    return _task_response(task, settings, f"Задача #{task.id} создана")
