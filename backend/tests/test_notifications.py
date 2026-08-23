from __future__ import annotations

from app.config import get_settings
from app.integrations.rocketchat.client import RocketChatClient
from app.models.task import Priority, Task, TaskStatus
from app.models.user import User
from app.services.notifications import notify_comment, notify_created, notify_overdue, notify_status


def test_task_notifications_are_direct_only(monkeypatch, db, users: dict[str, User]) -> None:
    task = Task(
        title="Replace UPS battery",
        priority=Priority.HIGH,
        creator_id=users["creator"].id,
        assignee_id=users["assignee"].id,
        rocket_chat_room_id="room-ops",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    calls: list[tuple[str, str, str | None]] = []

    def capture(_client, room_id: str, text: str, thread_message_id: str | None = None) -> None:
        calls.append((room_id, text, thread_message_id))

    monkeypatch.setattr(RocketChatClient, "post_message", capture)
    settings = get_settings().model_copy(
        update={
            "notify_task_created": True,
            "notify_task_completed": True,
            "notify_task_overdue": True,
            "notify_creator_updates": True,
            "public_url": "https://tasks.example.com",
        }
    )
    notify_created(task, settings)
    task.status = TaskStatus.DONE
    notify_status(task, users["assignee"], TaskStatus.REVIEW, settings)
    notify_comment(task, users["assignee"], "Battery replaced", settings)
    assert notify_overdue(task, settings) is True

    assert [call[0] for call in calls] == ["@alex", "@peter", "@alex", "@peter", "@alex"]
    assert all(call[0] != "room-ops" for call in calls)
    assert "Вам назначена задача" in calls[0][1]
    assert all(f"https://tasks.example.com/tasks/{task.id}" in call[1] for call in calls)


def test_notification_content_is_markdown_escaped(monkeypatch, db, users: dict[str, User]) -> None:
    task = Task(
        title="[Open this](https://phishing.invalid) @all",
        creator_id=users["creator"].id,
        assignee_id=users["assignee"].id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    messages: list[str] = []

    def capture(_client, _room_id: str, text: str, thread_message_id: str | None = None) -> None:
        messages.append(text)

    monkeypatch.setattr(RocketChatClient, "post_message", capture)
    settings = get_settings().model_copy(update={"notify_creator_updates": True})
    notify_comment(task, users["creator"], "[reset](https://phishing.invalid) @all", settings)

    assert "\\[reset\\]\\(https://phishing\\.invalid\\)" in messages[0]
    assert "\\@all" in messages[0]
    assert "\\[Open this\\]\\(https://phishing\\.invalid\\)" in messages[0]


def test_status_notification_is_not_duplicated_when_creator_is_assignee(monkeypatch, db, users: dict[str, User]) -> None:
    task = Task(
        title="Creator owns task",
        creator_id=users["creator"].id,
        assignee_id=users["creator"].id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    recipients: list[str] = []

    def capture(_client, room_id: str, _text: str, thread_message_id: str | None = None) -> None:
        recipients.append(room_id)

    monkeypatch.setattr(RocketChatClient, "post_message", capture)
    settings = get_settings().model_copy(
        update={"notify_task_completed": True, "notify_creator_updates": True}
    )
    task.status = TaskStatus.DONE
    notify_status(task, users["creator"], TaskStatus.REVIEW, settings)

    assert recipients == ["@peter"]


def test_creator_is_notified_for_status_without_legacy_assignee_notification(monkeypatch, db, users: dict[str, User]) -> None:
    task = Task(
        title="Ready for review",
        creator_id=users["creator"].id,
        assignee_id=users["assignee"].id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    calls: list[tuple[str, str]] = []

    def capture(_client, room_id: str, text: str, thread_message_id: str | None = None) -> None:
        calls.append((room_id, text))

    monkeypatch.setattr(RocketChatClient, "post_message", capture)
    settings = get_settings().model_copy(
        update={
            "notify_task_started": False,
            "notify_task_completed": False,
            "notify_creator_updates": True,
        }
    )
    task.status = TaskStatus.REVIEW
    notify_status(task, users["assignee"], TaskStatus.IN_PROGRESS, settings)

    assert [recipient for recipient, _ in calls] == ["@peter"]
    assert "В работе → **Проверка**" in calls[0][1]


def test_comment_notifies_other_task_participants_without_duplicates(monkeypatch, db, users: dict[str, User]) -> None:
    task = Task(
        title="Discuss maintenance window",
        creator_id=users["creator"].id,
        assignee_id=users["assignee"].id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    recipients: list[str] = []

    def capture(_client, room_id: str, _text: str, thread_message_id: str | None = None) -> None:
        recipients.append(room_id)

    monkeypatch.setattr(RocketChatClient, "post_message", capture)
    settings = get_settings().model_copy(update={"notify_creator_updates": True})

    notify_comment(task, users["creator"], "Can we start tonight?", settings)
    assert recipients == ["@alex"]

    recipients.clear()
    notify_comment(task, users["assignee"], "Yes, after 22:00.", settings)
    assert recipients == ["@peter"]

    recipients.clear()
    notify_comment(task, users["other"], "I will monitor it.", settings)
    assert set(recipients) == {"@peter", "@alex"}

    recipients.clear()
    task.assignee_id = task.creator_id
    db.commit()
    db.refresh(task)
    notify_comment(task, users["creator"], "Self-assigned note", settings)
    assert recipients == []
