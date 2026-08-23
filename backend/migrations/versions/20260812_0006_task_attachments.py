"""Add task attachments.

Revision ID: 20260812_0006
Revises: 20260811_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0006"
down_revision: str | None = "20260811_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index("ix_task_attachments_task_id", "task_attachments", ["task_id"])
    op.create_index(
        "ix_task_attachments_uploaded_by_user_id",
        "task_attachments",
        ["uploaded_by_user_id"],
    )
    op.create_index("ix_task_attachments_created_at", "task_attachments", ["created_at"])
    op.create_index(
        "ix_task_attachments_task_created_at",
        "task_attachments",
        ["task_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_attachments_task_created_at", table_name="task_attachments")
    op.drop_index("ix_task_attachments_created_at", table_name="task_attachments")
    op.drop_index("ix_task_attachments_uploaded_by_user_id", table_name="task_attachments")
    op.drop_index("ix_task_attachments_task_id", table_name="task_attachments")
    op.drop_table("task_attachments")
