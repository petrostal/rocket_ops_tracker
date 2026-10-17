"""Add opt-in permission to close visible tasks.

Revision ID: 20261017_0009
Revises: 20261017_0008
"""

import sqlalchemy as sa
from alembic import op

revision = "20261017_0009"
down_revision = "20261017_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("can_complete_tasks", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "can_complete_tasks")
