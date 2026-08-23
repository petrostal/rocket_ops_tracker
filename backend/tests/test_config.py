import pytest

from app.config import Settings


def test_comma_separated_collection_settings(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://chat.example.com, https://tasks.example.com/",
    )
    monkeypatch.setenv("TASK_ADMIN_USERNAMES", "Alice, Admin")

    settings = Settings(_env_file=None)

    assert settings.allowed_origins == [
        "https://chat.example.com",
        "https://tasks.example.com",
    ]
    assert settings.task_admin_usernames == {"alice", "admin"}


def production_settings(**overrides: str) -> Settings:
    values = {
        "APP_ENV": "production",
        "APP_SECRET": "a" * 48,
        "DATABASE_URL": f"postgresql+psycopg://opstracker:{'d' * 48}@database:5432/opstracker",
        "PUBLIC_URL": "https://tasks.example.com",
        "ROCKETCHAT_URL": "https://chat.example.com",
        "ROCKETCHAT_CLIENT_ID": "client-id",
        "ROCKETCHAT_CLIENT_SECRET": "c" * 48,
        "ROCKETCHAT_APP_SECRET": "b" * 48,
        "ALLOWED_ORIGINS": "https://chat.example.com,https://tasks.example.com",
        "ALLOWED_FRAME_ORIGIN": "https://chat.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("field", ["APP_SECRET", "ROCKETCHAT_APP_SECRET"])
def test_production_rejects_published_secret_placeholders(field: str) -> None:
    settings = production_settings(**{field: "replace-with-a-random-secret-before-use"})
    with pytest.raises(RuntimeError, match=field):
        settings.validate_production()


def test_production_requires_https_rocketchat_origin() -> None:
    settings = production_settings(ROCKETCHAT_URL="http://chat.example.com")
    with pytest.raises(RuntimeError, match="ROCKETCHAT_URL"):
        settings.validate_production()


def test_production_rejects_development_database() -> None:
    settings = production_settings(DATABASE_URL="sqlite+pysqlite:///./opstracker.db")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        settings.validate_production()


def test_valid_production_configuration_passes() -> None:
    production_settings().validate_production()
