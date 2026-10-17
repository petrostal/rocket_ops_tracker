from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_csrf
from app.config import Settings, get_settings
from app.database import get_db
from app.models.task import Priority, Task, TaskStatus
from app.models.user import User
from app.schemas.task import AssignRequest, TaskCommentCreate, TaskCreate, TaskList, TaskRead, TaskSummary, TaskUpdate
from app.services.attachments import attachment_path, delete_attachment, get_attachment, save_attachment
from app.services.notifications import notify_assigned, notify_comment, notify_created, notify_status, notify_watchers_added
from app.services.access import can_complete_tasks, can_view_task
from app.services.tasks import (
    DuplicateSourceTask,
    add_comment,
    assign_task,
    create_task,
    delete_task,
    get_task,
    list_tasks,
    take_task,
    transition_task,
    update_task,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _duplicate(exc: DuplicateSourceTask, user: User) -> HTTPException:
    if not can_view_task(user, exc.task):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "A task already exists for this source message"},
        )
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {
            "message": str(exc),
            "existing_task_id": exc.task.id,
            "existing_task_title": exc.task.title,
            "existing_task_status": exc.task.status.value,
        },
    )


@router.get("", response_model=TaskList)
def tasks(
    status_filter: list[TaskStatus] | None = Query(None, alias="status"),
    assignee: str | None = None,
    creator: int | None = None,
    participation: Literal["assigned", "created", "watching"] | None = None,
    room: str | None = None,
    priority: Priority | None = None,
    overdue: bool | None = None,
    search: str | None = Query(None, max_length=500),
    tag_filter: list[str] | None = Query(None, alias="tag"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskList:
    items, total = list_tasks(
        db,
        current_user=user,
        statuses=status_filter,
        assignee=assignee,
        creator=creator,
        participation=participation,
        room=room,
        priority=priority,
        overdue=overdue,
        search=search,
        tags=tag_filter,
        limit=limit,
        offset=offset,
    )
    return TaskList(items=[TaskSummary.model_validate(item) for item in items], total=total, limit=limit, offset=offset)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create(
    data: TaskCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
    user: User = Depends(get_current_user),
) -> Task:
    try:
        task = create_task(db, data, user)
    except DuplicateSourceTask as exc:
        raise _duplicate(exc, user) from exc
    notify_created(task, settings)
    notify_watchers_added(task, user, set(), settings)
    return task


@router.get("/{task_id}", response_model=TaskRead)
def detail(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Task:
    return get_task(db, task_id, user)


@router.post("/{task_id}/comments", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def comment(
    task_id: int,
    data: TaskCommentCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
    user: User = Depends(get_current_user),
) -> Task:
    task = add_comment(db, get_task(db, task_id, user), data, user, settings)
    notify_comment(task, user, data.body, settings)
    return task


@router.post("/{task_id}/attachments", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
    user: User = Depends(get_current_user),
) -> Task:
    return await save_attachment(db, get_task(db, task_id, user), file, user, settings)


@router.get("/{task_id}/attachments/{attachment_id}/download", response_class=FileResponse)
def download_attachment(
    task_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> FileResponse:
    task = get_task(db, task_id, user)
    attachment = get_attachment(db, task, attachment_id)
    path = attachment_path(settings, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment file not found")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=attachment.original_name,
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/{task_id}/attachments/{attachment_id}", response_model=TaskRead)
def remove_attachment(
    task_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
    user: User = Depends(get_current_user),
) -> Task:
    task = get_task(db, task_id, user)
    attachment = get_attachment(db, task, attachment_id)
    return delete_attachment(db, task, attachment, user, settings)


@router.patch("/{task_id}", response_model=TaskRead)
def patch_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
    user: User = Depends(get_current_user),
) -> Task:
    task = get_task(db, task_id, user)
    old_status = task.status
    old_assignee_id = task.assignee_id
    old_watcher_ids = {watcher.id for watcher in task.watchers}
    updated = update_task(db, task, data, user)
    notify_watchers_added(updated, user, old_watcher_ids, settings)
    notify_assigned(updated, user, old_assignee_id, settings)
    notify_status(updated, user, old_status, settings)
    return updated


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    user: User = Depends(get_current_user),
) -> None:
    delete_task(db, get_task(db, task_id, user), user)


@router.post("/{task_id}/assign", response_model=TaskRead)
def assign(
    task_id: int,
    data: AssignRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_csrf),
    user: User = Depends(get_current_user),
) -> Task:
    if data.assignee_id is not None and db.get(User, data.assignee_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Assignee not found")
    task = get_task(db, task_id, user)
    old_assignee_id = task.assignee_id
    updated = assign_task(db, task, data.assignee_id, user)
    notify_assigned(updated, user, old_assignee_id, settings)
    return updated


@router.post("/{task_id}/take", response_model=TaskRead)
def take(task_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings), _: None = Depends(require_csrf), user: User = Depends(get_current_user)) -> Task:
    task = get_task(db, task_id, user)
    old_assignee_id = task.assignee_id
    updated = take_task(db, task, user)
    notify_assigned(updated, user, old_assignee_id, settings)
    return updated


def _transition_endpoint(target: TaskStatus):
    def endpoint(
        task_id: int,
        db: Session = Depends(get_db),
        settings: Settings = Depends(get_settings),
        _: None = Depends(require_csrf),
        user: User = Depends(get_current_user),
    ) -> Task:
        task = get_task(db, task_id, user)
        old = task.status
        destination = TaskStatus.REVIEW if target == TaskStatus.DONE and not can_complete_tasks(user) else target
        result = transition_task(db, task, destination, user)
        notify_status(result, user, old, settings)
        return result

    return endpoint


router.add_api_route("/{task_id}/start", _transition_endpoint(TaskStatus.IN_PROGRESS), methods=["POST"], response_model=TaskRead)
router.add_api_route("/{task_id}/wait", _transition_endpoint(TaskStatus.WAITING), methods=["POST"], response_model=TaskRead)
router.add_api_route("/{task_id}/review", _transition_endpoint(TaskStatus.REVIEW), methods=["POST"], response_model=TaskRead)
router.add_api_route("/{task_id}/complete", _transition_endpoint(TaskStatus.DONE), methods=["POST"], response_model=TaskRead)
router.add_api_route("/{task_id}/reopen", _transition_endpoint(TaskStatus.TODO), methods=["POST"], response_model=TaskRead)
