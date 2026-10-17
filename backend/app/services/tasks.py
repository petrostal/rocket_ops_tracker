from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.models.task import Priority, Tag, Task, TaskAttachment, TaskComment, TaskEvent, TaskStatus
from app.models.user import AccessMode, User
from app.schemas.task import IntegrationTaskCreate, TaskCommentCreate, TaskCreate, TaskUpdate
from app.services.access import can_view_task, task_visibility_clause


LOAD_TASK = (
    selectinload(Task.watchers).selectinload(User.access_tags),
    selectinload(Task.creator),
    selectinload(Task.assignee),
    selectinload(Task.events).selectinload(TaskEvent.actor),
    selectinload(Task.comments).selectinload(TaskComment.author),
    selectinload(Task.attachments).selectinload(TaskAttachment.uploaded_by),
    selectinload(Task.tags),
)
LOAD_TASK_SUMMARY = (
    selectinload(Task.creator),
    selectinload(Task.assignee),
    selectinload(Task.tags),
)


class DuplicateSourceTask(Exception):
    def __init__(self, task: Task):
        self.task = task
        super().__init__(f"Task #{task.id} already exists for this Rocket.Chat message")


def task_query() -> Select[tuple[Task]]:
    return select(Task).where(Task.deleted_at.is_(None)).options(*LOAD_TASK)


def _get_task_unrestricted(db: Session, task_id: int) -> Task:
    task = db.scalar(task_query().where(Task.id == task_id))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


def get_task(db: Session, task_id: int, current_user: User) -> Task:
    task = db.scalar(
        task_query().where(Task.id == task_id, task_visibility_clause(current_user))
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


def find_by_message(db: Session, message_id: str) -> Task | None:
    return db.scalar(task_query().where(Task.rocket_chat_message_id == message_id))


def list_tasks(
    db: Session,
    *,
    current_user: User,
    statuses: list[TaskStatus] | None = None,
    assignee: str | None = None,
    creator: int | None = None,
    participation: str | None = None,
    room: str | None = None,
    priority: Priority | None = None,
    overdue: bool | None = None,
    search: str | None = None,
    tags: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Task], int]:
    query = select(Task).where(
        Task.deleted_at.is_(None), task_visibility_clause(current_user)
    )
    if statuses:
        query = query.where(Task.status.in_(statuses))
    if assignee:
        if assignee == "me":
            query = query.where(Task.assignee_id == current_user.id)
        elif assignee == "unassigned":
            query = query.where(Task.assignee_id.is_(None))
        else:
            try:
                assignee_id = int(assignee)
            except ValueError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "assignee must be an integer, me, or unassigned") from exc
            query = query.where(Task.assignee_id == assignee_id)
    if creator is not None:
        query = query.where(Task.creator_id == creator)
    if participation == "assigned":
        query = query.where(Task.assignee_id == current_user.id)
    elif participation == "created":
        query = query.where(Task.creator_id == current_user.id)
    elif participation == "watching":
        query = query.where(Task.watchers.any(User.id == current_user.id))
    if room:
        query = query.where(or_(Task.rocket_chat_room_id == room, Task.rocket_chat_room_name == room))
    if priority:
        query = query.where(Task.priority == priority)
    if overdue is True:
        query = query.where(
            Task.due_date < datetime.now(timezone.utc), Task.status != TaskStatus.DONE
        )
    if search:
        pattern = f"%{search.strip()}%"
        clauses = [Task.title.ilike(pattern), Task.description.ilike(pattern)]
        if search.strip().lstrip("#").isdigit():
            clauses.append(Task.id == int(search.strip().lstrip("#")))
        query = query.where(or_(*clauses))
    for tag in tags or []:
        normalized = " ".join(tag.strip().lstrip("#").split()).casefold()
        if normalized:
            query = query.where(Task.tags.any(Tag.normalized_name == normalized))
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    order_by = (
        (Task.completed_at.desc().nullslast(), Task.updated_at.desc(), Task.id.desc())
        if statuses == [TaskStatus.DONE]
        else (Task.status, Task.due_date.asc().nullslast(), Task.created_at.desc())
    )
    items = list(
        db.scalars(
            query.options(*LOAD_TASK_SUMMARY)
            .order_by(*order_by)
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return items, total


def _event(db: Session, task: Task, event_type: str, actor: User, metadata: dict[str, object]) -> None:
    db.add(TaskEvent(task=task, event_type=event_type, actor=actor, event_metadata=metadata))


def _set_tags(db: Session, task: Task, names: list[str]) -> None:
    normalized = {name.casefold(): name for name in names}
    existing = {
        tag.normalized_name: tag
        for tag in db.scalars(select(Tag).where(Tag.normalized_name.in_(normalized))).all()
    } if normalized else {}
    task.tags = [
        existing.get(key) or Tag(name=name, normalized_name=key)
        for key, name in normalized.items()
    ]


def create_task(db: Session, data: TaskCreate | IntegrationTaskCreate, actor: User) -> Task:
    message_id = data.rocket_chat_message_id if isinstance(data, IntegrationTaskCreate) else None
    if message_id:
        existing = find_by_message(db, message_id)
        if existing:
            raise DuplicateSourceTask(existing)
    payload = data.model_dump()
    tag_names = payload.pop("tags")
    watchers = _resolve_watchers(db, payload.pop("watcher_ids"))
    task = Task(**payload, creator_id=actor.id)
    task.watchers = watchers
    db.add(task)
    _set_tags(db, task, tag_names)
    db.flush()
    _event(db, task, "task_created", actor, {"status": TaskStatus.TODO.value})
    if task.assignee_id:
        _event(db, task, "assigned", actor, {"assignee_id": task.assignee_id})
    if watchers:
        _event(db, task, "watchers_changed", actor, {"added": [user.username for user in watchers], "removed": []})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if message_id:
            existing = find_by_message(db, message_id)
            if existing:
                raise DuplicateSourceTask(existing) from exc
        raise
    return _get_task_unrestricted(db, task.id)


def _can_edit(task: Task, actor: User) -> bool:
    return actor.is_admin or task.creator_id == actor.id or task.assignee_id == actor.id


def _resolve_watchers(db: Session, ids: list[int]) -> list[User]:
    watchers = list(db.scalars(select(User).where(User.id.in_(ids)).order_by(User.display_name, User.id)).all()) if ids else []
    if len(watchers) != len(set(ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "One or more watchers do not exist")
    if any(not user.is_active or (not user.is_admin and user.access_mode != AccessMode.ALL
           and (user.access_mode == AccessMode.NONE or not user.view_watched_tasks)) for user in watchers):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Наблюдателю нужен доступ к трекеру и разрешение видеть наблюдаемые задачи")
    return watchers


def update_task(db: Session, task: Task, data: TaskUpdate, actor: User) -> Task:
    if not _can_edit(task, actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot edit this task")
    changes = data.model_dump(exclude_unset=True)
    if "watcher_ids" in changes and not (actor.is_admin or task.creator_id == actor.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator or an administrator can manage watchers")
    watchers = _resolve_watchers(db, changes["watcher_ids"]) if "watcher_ids" in changes else None
    if {"priority", "due_date"}.intersection(changes) and not actor.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can change priority or due date")
    if "assignee_id" in changes and not (actor.is_admin or task.creator_id == actor.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator or an administrator can reassign")
    if changes.get("assignee_id") is not None and db.get(User, changes["assignee_id"]) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Assignee not found")
    if "status" in changes:
        target = changes.pop("status")
        _check_transition(task, target, actor)
        if changes:
            task = update_task(db, task, TaskUpdate(**changes), actor)
        return transition_task(db, task, target, actor)
    old_assignee = task.assignee_id
    old_priority = task.priority
    old_due = task.due_date
    tag_names = changes.pop("tags", None)
    changes.pop("watcher_ids", None)
    if watchers is not None:
        previous = {user.id: user.username for user in task.watchers}
        current = {user.id: user.username for user in watchers}
        if previous.keys() != current.keys():
            task.watchers = watchers
            _event(db, task, "watchers_changed", actor, {
                "added": [name for uid, name in current.items() if uid not in previous],
                "removed": [name for uid, name in previous.items() if uid not in current],
            })
    old_tags = [tag.normalized_name for tag in task.tags]
    for name, value in changes.items():
        setattr(task, name, value)
    if changes:
        _event(db, task, "task_updated", actor, {"fields": sorted(changes)})
    if "assignee_id" in changes and old_assignee != task.assignee_id:
        _event(db, task, "assigned" if task.assignee_id else "unassigned", actor, {"from": old_assignee, "to": task.assignee_id})
    if "priority" in changes and old_priority != task.priority:
        _event(db, task, "priority_changed", actor, {"from": old_priority.value, "to": task.priority.value})
    if "due_date" in changes and old_due != task.due_date:
        task.overdue_notified_at = None
        _event(db, task, "due_date_changed", actor, {"from": old_due.isoformat() if old_due else None, "to": task.due_date.isoformat() if task.due_date else None})
    if tag_names is not None:
        _set_tags(db, task, tag_names)
        new_tags = [name.casefold() for name in tag_names]
        if old_tags != new_tags:
            _event(db, task, "tags_changed", actor, {"from": old_tags, "to": new_tags})
    db.commit()
    return _get_task_unrestricted(db, task.id)


def assign_task(db: Session, task: Task, assignee_id: int | None, actor: User) -> Task:
    return update_task(db, task, TaskUpdate(assignee_id=assignee_id), actor)


def take_task(db: Session, task: Task, actor: User) -> Task:
    if not _can_edit(task, actor) and not can_view_task(actor, task, include_participation=False):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Watching a task does not grant permission to take it")
    if task.assignee_id is not None and task.assignee_id != actor.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task is already assigned")
    if task.assignee_id == actor.id:
        return task
    task.assignee_id = actor.id
    _event(db, task, "assigned", actor, {"from": None, "to": actor.id, "taken": True})
    db.commit()
    return _get_task_unrestricted(db, task.id)


def _check_transition(task: Task, target: TaskStatus, actor: User) -> None:
    if not (actor.is_admin or task.assignee_id == actor.id or (task.assignee_id is None and task.creator_id == actor.id)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the assignee can change task status")
    if task.status == TaskStatus.DONE and target != TaskStatus.DONE and not actor.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can reopen completed tasks")


def transition_task(db: Session, task: Task, target: TaskStatus, actor: User) -> Task:
    _check_transition(task, target, actor)
    old = task.status
    if old == target:
        return task
    task.status = target
    task.completed_at = datetime.now(timezone.utc) if target == TaskStatus.DONE else None
    if old == TaskStatus.DONE and target != TaskStatus.DONE:
        task.overdue_notified_at = None
    event_type = "completed" if target == TaskStatus.DONE else "reopened" if old == TaskStatus.DONE else "status_changed"
    _event(db, task, event_type, actor, {"from": old.value, "to": target.value})
    db.commit()
    return _get_task_unrestricted(db, task.id)


def delete_task(db: Session, task: Task, actor: User) -> None:
    if not actor.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can delete tasks")
    task.deleted_at = datetime.now(timezone.utc)
    _event(db, task, "deleted", actor, {})
    db.commit()


def add_comment(
    db: Session,
    task: Task,
    data: TaskCommentCreate,
    actor: User,
    settings: Settings,
) -> Task:
    db.execute(select(Task.id).where(Task.id == task.id).with_for_update())
    comment_count = db.scalar(select(func.count(TaskComment.id)).where(TaskComment.task_id == task.id)) or 0
    if comment_count >= settings.comment_max_per_task:
        raise HTTPException(status.HTTP_409_CONFLICT, "Comment limit for this task has been reached")
    comment = TaskComment(task=task, author=actor, body=data.body)
    db.add(comment)
    db.flush()
    _event(db, task, "comment_added", actor, {"comment_id": comment.id})
    db.commit()
    return _get_task_unrestricted(db, task.id)
