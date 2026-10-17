"""Add creator visibility settings and task watchers.

Revision ID: 20261017_0008
Revises: 20260816_0007
"""

import sqlalchemy as sa
from alembic import op

revision = "20261017_0008"
down_revision = "20260816_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("view_created_tasks", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("view_watched_tasks", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        "task_watchers",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "user_id"),
    )
    op.create_index("ix_task_watchers_user_id", "task_watchers", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_task_watchers_user_id", table_name="task_watchers")
    op.drop_table("task_watchers")
    op.drop_column("users", "view_watched_tasks")
    op.drop_column("users", "view_created_tasks")
