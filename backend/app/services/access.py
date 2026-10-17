from __future__ import annotations

from sqlalchemy import false, or_, true
from sqlalchemy.sql.elements import ColumnElement

from app.models.task import Tag, Task
from app.models.user import AccessMode, User


def allowed_tag_ids(user: User) -> set[int]:
    return {tag.id for tag in user.access_tags}


def task_visibility_clause(user: User) -> ColumnElement[bool]:
    if not user.is_active:
        return false()
    if user.is_admin or user.access_mode == AccessMode.ALL:
        return true()
    if user.access_mode == AccessMode.NONE:
        return false()

    assigned = Task.assignee_id == user.id
    tag_ids = allowed_tag_ids(user)
    tagged = Task.tags.any(Tag.id.in_(tag_ids)) if tag_ids else false()
    clauses = []
    if user.access_mode in {AccessMode.ASSIGNED, AccessMode.ASSIGNED_OR_TAGS}:
        clauses.append(assigned)
    if user.access_mode in {AccessMode.TAGS, AccessMode.ASSIGNED_OR_TAGS}:
        clauses.append(tagged)
    if user.view_created_tasks:
        clauses.append(Task.creator_id == user.id)
    if user.view_watched_tasks:
        clauses.append(Task.watchers.any(User.id == user.id))
    return or_(*clauses) if clauses else false()


def can_view_task(user: User, task: Task, *, include_participation: bool = True) -> bool:
    if not user.is_active:
        return False
    if user.is_admin or user.access_mode == AccessMode.ALL:
        return True
    if user.access_mode == AccessMode.NONE:
        return False
    if include_participation:
        if user.view_created_tasks and task.creator_id == user.id:
            return True
        if user.view_watched_tasks and any(watcher.id == user.id for watcher in task.watchers):
            return True
    if user.access_mode in {AccessMode.ASSIGNED, AccessMode.ASSIGNED_OR_TAGS}:
        if task.assignee_id == user.id:
            return True
    if user.access_mode in {AccessMode.TAGS, AccessMode.ASSIGNED_OR_TAGS}:
        return bool(allowed_tag_ids(user).intersection(tag.id for tag in task.tags))
    return False
