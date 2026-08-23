"""Initial task tracker schema."""

from alembic import op
import sqlalchemy as sa

revision = "20260810_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rocket_chat_user_id", sa.String(64), nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("avatar_url", sa.String(1024)),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rocket_chat_user_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_rocket_chat_user_id", "users", ["rocket_chat_user_id"])
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="TODO"),
        sa.Column("priority", sa.String(32), nullable=False, server_default="NORMAL"),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("overdue_notified_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("rocket_chat_room_id", sa.String(64)),
        sa.Column("rocket_chat_room_name", sa.String(255)),
        sa.Column("rocket_chat_room_type", sa.String(16)),
        sa.Column("rocket_chat_message_id", sa.String(64)),
        sa.Column("rocket_chat_thread_id", sa.String(64)),
        sa.Column("rocket_chat_message_url", sa.String(2048)),
        sa.Column("rocket_chat_message_author_id", sa.String(64)),
        sa.Column("rocket_chat_message_author_username", sa.String(128)),
        sa.Column("rocket_chat_message_timestamp", sa.DateTime(timezone=True)),
        sa.Column("rocket_chat_message_snippet", sa.Text()),
        sa.UniqueConstraint("rocket_chat_message_id"),
    )
    for name in ("status", "priority", "creator_id", "assignee_id", "due_date", "deleted_at", "rocket_chat_room_id", "rocket_chat_message_id"):
        op.create_index(f"ix_tasks_{name}", "tasks", [name])
    op.create_index("ix_tasks_status_due_date", "tasks", ["status", "due_date"])
    op.create_index("ix_tasks_room_status", "tasks", ["rocket_chat_room_id", "status"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])
    op.create_index("ix_task_events_event_type", "task_events", ["event_type"])
    op.create_index("ix_task_events_created_at", "task_events", ["created_at"])

    op.create_table(
        "integration_nonces",
        sa.Column("nonce_hash", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_integration_nonces_created_at", "integration_nonces", ["created_at"])
    op.create_table(
        "launch_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_launch_codes_user_id", "launch_codes", ["user_id"])
    op.create_index("ix_launch_codes_expires_at", "launch_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_table("launch_codes")
    op.drop_table("integration_nonces")
    op.drop_table("task_events")
    op.drop_table("tasks")
    op.drop_table("users")
