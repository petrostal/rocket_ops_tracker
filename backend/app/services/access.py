from __future__ import annotations

from sqlalchemy import false, or_, true
from sqlalchemy.sql.elements import ColumnElement

from app.models.task import Tag, Task
from app.models.user import AccessMode, User


def allowed_tag_ids(user: User) -> set[int]:
    return {tag.id for tag in user.access_tags}


def task_visibility_clause(user: User) -> ColumnElement[bool]:
    if user.is_admin or user.access_mode == AccessMode.ALL:
        return true()
    if user.access_mode == AccessMode.NONE:
        return false()

    assigned = Task.assignee_id == user.id
    if user.access_mode == AccessMode.ASSIGNED:
        return assigned

    tag_ids = allowed_tag_ids(user)
    tagged = Task.tags.any(Tag.id.in_(tag_ids)) if tag_ids else false()
    if user.access_mode == AccessMode.TAGS:
        return tagged
    if user.access_mode == AccessMode.ASSIGNED_OR_TAGS:
        return or_(assigned, tagged)
    return false()


def can_view_task(user: User, task: Task) -> bool:
    if user.is_admin or user.access_mode == AccessMode.ALL:
        return True
    if user.access_mode == AccessMode.NONE:
        return False
    if user.access_mode in {AccessMode.ASSIGNED, AccessMode.ASSIGNED_OR_TAGS}:
        if task.assignee_id == user.id:
            return True
    if user.access_mode in {AccessMode.TAGS, AccessMode.ASSIGNED_OR_TAGS}:
        return bool(allowed_tag_ids(user).intersection(tag.id for tag in task.tags))
    return False
