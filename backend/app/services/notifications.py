from __future__ import annotations

import logging
import re

from app.config import Settings
from app.integrations.rocketchat.client import RocketChatClient, RocketChatError
from app.models.task import Task, TaskStatus
from app.models.user import User

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    TaskStatus.TODO: "Нужно сделать",
    TaskStatus.IN_PROGRESS: "В работе",
    TaskStatus.WAITING: "Ожидание",
    TaskStatus.REVIEW: "Проверка",
    TaskStatus.DONE: "Готово",
}
MARKDOWN_CONTROL = re.compile(r"([\\`*_{}\[\]()#+.!|>~@-])")


def _task_url(task: Task, settings: Settings) -> str:
    return f"{settings.public_url.rstrip('/')}/tasks/{task.id}"


def _escape_markdown(value: str) -> str:
    return MARKDOWN_CONTROL.sub(r"\\\1", value)


def notify_created(task: Task, settings: Settings) -> None:
    if not settings.notify_task_created:
        return
    if task.assignee:
        _post_direct(
            task,
            task.assignee,
            f"📋 Вам назначена задача #{task.id}\n"
            f"**{_escape_markdown(task.title)}**\n"
            f"Приоритет: {task.priority.value}\n"
            f"[Открыть задачу]({_task_url(task, settings)})",
            settings,
        )


def notify_assigned(task: Task, actor: User, old_assignee_id: int | None, settings: Settings) -> None:
    if (
        not settings.notify_task_assigned
        or old_assignee_id == task.assignee_id
    ):
        return
    if task.assignee:
        _post_direct(
            task,
            task.assignee,
            f"👤 Вам назначена задача #{task.id} пользователем {_escape_markdown('@' + actor.username)}\n"
            f"[{_escape_markdown(task.title)}]({_task_url(task, settings)})",
            settings,
        )


def notify_status(task: Task, actor: User, old_status: TaskStatus, settings: Settings) -> None:
    if old_status == task.status:
        return

    if settings.notify_creator_updates and task.creator:
        _post_direct(
            task,
            task.creator,
            f"🔄 В задаче #{task.id} изменён статус пользователем {_escape_markdown('@' + actor.username)}\n"
            f"{STATUS_LABELS[old_status]} → **{STATUS_LABELS[task.status]}**\n"
            f"[{_escape_markdown(task.title)}]({_task_url(task, settings)})",
            settings,
        )

    enabled = task.status == TaskStatus.DONE and settings.notify_task_completed
    enabled = enabled or task.status == TaskStatus.IN_PROGRESS and settings.notify_task_started
    if (
        not enabled
        or not task.assignee
        or task.assignee_id == task.creator_id
    ):
        return
    icon = "✅" if task.status == TaskStatus.DONE else "▶"
    verb = "завершена" if task.status == TaskStatus.DONE else "начата"
    _post_direct(
        task,
        task.assignee,
        f"{icon} Задача #{task.id} {verb} пользователем {_escape_markdown('@' + actor.username)}\n"
        f"[{_escape_markdown(task.title)}]({_task_url(task, settings)})",
        settings,
    )


def notify_comment(task: Task, actor: User, body: str, settings: Settings) -> None:
    if not settings.notify_creator_updates:
        return
    preview = _escape_markdown(body.strip())
    if len(preview) > 1000:
        preview = f"{preview[:997]}…"
    text = (
        f"💬 Новый комментарий к задаче #{task.id} от {_escape_markdown('@' + actor.username)}\n"
        f"> {preview.replace(chr(10), chr(10) + '> ')}\n"
        f"[{_escape_markdown(task.title)}]({_task_url(task, settings)})"
    )
    recipients = {
        participant.id: participant
        for participant in (task.creator, task.assignee)
        if participant is not None and participant.id != actor.id
    }
    for recipient in recipients.values():
        _post_direct(task, recipient, text, settings)


def notify_overdue(task: Task, settings: Settings) -> bool:
    if not settings.notify_task_overdue or not task.assignee:
        return False
    due = task.due_date.strftime("%d.%m.%Y %H:%M UTC") if task.due_date else "неизвестен"
    return _post_direct(
        task,
        task.assignee,
        f"⏰ Задача #{task.id} просрочена\n**{_escape_markdown(task.title)}**\nСрок: {due}\n"
        f"[Открыть задачу]({_task_url(task, settings)})",
        settings,
    )


def _post_direct(task: Task, recipient: User, text: str, settings: Settings) -> bool:
    try:
        RocketChatClient(settings).post_message(f"@{recipient.username}", text)
        return True
    except RocketChatError:
        logger.exception(
            "rocketchat_direct_notification_failed",
            extra={"task_id": task.id, "recipient": recipient.username},
        )
        return False
