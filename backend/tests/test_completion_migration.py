from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings


def test_completion_migration_preserves_users_and_defaults_to_review(tmp_path, monkeypatch):
    backend = Path(__file__).resolve().parents[1]
    database_url = f"sqlite+pysqlite:///{tmp_path / 'completion.db'}"
    monkeypatch.setattr(get_settings(), "database_url", database_url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "20261017_0008")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("""INSERT INTO users
                (rocket_chat_user_id, username, display_name, is_admin, is_active, access_mode,
                 view_created_tasks, view_watched_tasks, created_at, updated_at)
                VALUES ('migration-user', 'migration_user', 'Migration user', false, true,
                        'ASSIGNED', true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            user = connection.execute(text("SELECT access_mode, view_created_tasks, view_watched_tasks, can_complete_tasks FROM users")).one()
            assert tuple(user) == ("ASSIGNED", 1, 1, 0)
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261017_0009"
        column = next(column for column in inspect(engine).get_columns("users") if column["name"] == "can_complete_tasks")
        assert column["nullable"] is False
        assert column["default"] in {"0", "false"}
        command.downgrade(config, "20261017_0008")
        assert "can_complete_tasks" not in {column["name"] for column in inspect(engine).get_columns("users")}
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM users")) == 1
            assert connection.scalar(text("SELECT can_complete_tasks FROM users")) == 0
    finally:
        engine.dispose()
