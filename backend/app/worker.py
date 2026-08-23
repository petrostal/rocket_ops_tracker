from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import SessionLocal
from app.models.task import Task, TaskStatus
from app.services.notifications import notify_overdue

logger = logging.getLogger("opstracker.worker")


def check_overdue_tasks() -> int:
    settings = get_settings()
    if not settings.notify_task_overdue:
        return 0
    now = datetime.now(timezone.utc)
    notified = 0
    with SessionLocal() as db:
        tasks = db.scalars(
            select(Task)
            .where(
                Task.deleted_at.is_(None),
                Task.status != TaskStatus.DONE,
                Task.due_date.is_not(None),
                Task.due_date < now,
                Task.overdue_notified_at.is_(None),
                Task.assignee_id.is_not(None),
            )
            .options(selectinload(Task.assignee))
            .order_by(Task.due_date)
            .limit(100)
        ).all()
        for task in tasks:
            if notify_overdue(task, settings):
                task.overdue_notified_at = now
                notified += 1
        db.commit()
    return notified


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    )
    logger.info("overdue_worker_started interval_seconds=%s", settings.overdue_check_interval_seconds)
    while True:
        try:
            notified = check_overdue_tasks()
            if notified:
                logger.info("overdue_notifications_sent count=%s", notified)
        except Exception:
            logger.exception("overdue_check_failed")
        time.sleep(settings.overdue_check_interval_seconds)


if __name__ == "__main__":
    main()
