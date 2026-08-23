"""Preserve the migration chain without deployment-specific ownership changes.

Revision ID: 20260811_0005
Revises: 20260810_0004
"""

from collections.abc import Sequence

revision: str = "20260811_0005"
down_revision: str | None = "20260810_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Legacy ownership repair belongs in an explicit, deployment-local procedure
    # keyed by immutable user ID. A reusable migration must not choose an owner.
    pass


def downgrade() -> None:
    pass
