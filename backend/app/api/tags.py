from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.task import Tag, Task, task_tags
from app.models.user import AccessMode, User
from app.schemas.task import TagRead
from app.services.access import allowed_tag_ids, task_visibility_clause

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagRead])
def tags(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Tag]:
    if user.is_admin or user.access_mode == AccessMode.ALL:
        query = select(Tag)
    else:
        visible_task_ids = select(Task.id).where(
            Task.deleted_at.is_(None), task_visibility_clause(user)
        )
        visible_tag_ids = select(task_tags.c.tag_id).where(
            task_tags.c.task_id.in_(visible_task_ids)
        )
        permitted_ids = allowed_tag_ids(user)
        query = select(Tag).where(
            or_(Tag.id.in_(visible_tag_ids), Tag.id.in_(permitted_ids))
        )
    return list(db.scalars(query.order_by(Tag.name)).all())
