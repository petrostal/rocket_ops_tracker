"""Index completed tasks by completion time.

Revision ID: 20260816_0007
Revises: 20260812_0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260816_0007"
down_revision: str | None = "20260812_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tasks_status_completed_at",
        "tasks",
        ["status", "completed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_status_completed_at", table_name="tasks")
