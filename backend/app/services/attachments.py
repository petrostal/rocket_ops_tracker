from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.task import Task, TaskAttachment, TaskEvent
from app.models.user import User
from app.services.tasks import _get_task_unrestricted

logger = logging.getLogger(__name__)
STORED_NAME_PATTERN = re.compile(r"^[0-9a-f]{32}$")
CHUNK_SIZE = 1024 * 1024


def clean_filename(value: str | None) -> str:
    filename = (value or "").replace("\\", "/").rsplit("/", 1)[-1]
    filename = "".join(char for char in filename if ord(char) >= 32 and char != "\x7f").strip()
    return (filename or "file")[:255]


def attachment_path(settings: Settings, stored_name: str) -> Path:
    if not STORED_NAME_PATTERN.fullmatch(stored_name):
        raise ValueError("Invalid stored attachment name")
    return Path(settings.attachments_dir) / stored_name[:2] / stored_name


async def save_attachment(
    db: Session,
    task: Task,
    upload: UploadFile,
    actor: User,
    settings: Settings,
) -> Task:
    db.execute(select(Task.id).where(Task.id == task.id).with_for_update())
    task_count, task_bytes = db.execute(
        select(func.count(TaskAttachment.id), func.coalesce(func.sum(TaskAttachment.size_bytes), 0))
        .where(TaskAttachment.task_id == task.id)
    ).one()
    if task_count >= settings.attachment_max_per_task:
        raise HTTPException(status.HTTP_409_CONFLICT, "Attachment limit for this task has been reached")
    user_bytes = db.scalar(
        select(func.coalesce(func.sum(TaskAttachment.size_bytes), 0))
        .where(TaskAttachment.uploaded_by_user_id == actor.id)
    ) or 0

    original_name = clean_filename(upload.filename)
    stored_name = uuid.uuid4().hex
    destination = attachment_path(settings, stored_name)
    temporary = destination.with_suffix(".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with temporary.open("xb") as output:
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                if size > settings.attachment_max_bytes:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"File is larger than {settings.attachment_max_bytes // (1024 * 1024)} MB",
                    )
                if task_bytes + size > settings.attachment_total_max_bytes_per_task:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        "Total attachment size limit for this task has been reached",
                    )
                if user_bytes + size > settings.attachment_total_max_bytes_per_user:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        "Total attachment size limit for this user has been reached",
                    )
                output.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File must not be empty")
        temporary.replace(destination)
        attachment = TaskAttachment(
            task=task,
            uploaded_by=actor,
            original_name=original_name,
            stored_name=stored_name,
            content_type=(upload.content_type or "application/octet-stream")[:255],
            size_bytes=size,
        )
        db.add(attachment)
        db.flush()
        db.add(
            TaskEvent(
                task=task,
                event_type="attachment_added",
                actor=actor,
                event_metadata={"attachment_id": attachment.id, "name": original_name, "size": size},
            )
        )
        db.commit()
        return _get_task_unrestricted(db, task.id)
    except Exception:
        db.rollback()
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def get_attachment(db: Session, task: Task, attachment_id: int) -> TaskAttachment:
    attachment = db.get(TaskAttachment, attachment_id)
    if attachment is None or attachment.task_id != task.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    return attachment


def delete_attachment(
    db: Session,
    task: Task,
    attachment: TaskAttachment,
    actor: User,
    settings: Settings,
) -> Task:
    if not (actor.is_admin or task.creator_id == actor.id or attachment.uploaded_by_user_id == actor.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot delete this attachment")
    path = attachment_path(settings, attachment.stored_name)
    name = attachment.original_name
    attachment_id = attachment.id
    db.delete(attachment)
    db.add(
        TaskEvent(
            task=task,
            event_type="attachment_deleted",
            actor=actor,
            event_metadata={"attachment_id": attachment_id, "name": name},
        )
    )
    db.commit()
    db.expire_all()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("attachment_file_delete_failed", extra={"attachment_id": attachment_id})
    return _get_task_unrestricted(db, task.id)
