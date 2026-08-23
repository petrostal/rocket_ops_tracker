"""Add per-user task visibility profiles.

Revision ID: 20260810_0004
Revises: 20260810_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0004"
down_revision: str | None = "20260810_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("access_mode", sa.String(length=32), nullable=False, server_default="NONE"),
    )
    op.create_index("ix_users_access_mode", "users", ["access_mode"])
    op.create_table(
        "user_access_tags",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "tag_id"),
    )
    op.create_index("ix_user_access_tags_tag_id", "user_access_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_user_access_tags_tag_id", table_name="user_access_tags")
    op.drop_table("user_access_tags")
    op.drop_index("ix_users_access_mode", table_name="users")
    op.drop_column("users", "access_mode")
