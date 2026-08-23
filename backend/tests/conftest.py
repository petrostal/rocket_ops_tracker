from __future__ import annotations

import os

os.environ.update(
    {
        "APP_ENV": "test",
        "APP_SECRET": "test-session-secret-that-is-long-enough",
        "ROCKETCHAT_APP_SECRET": "test-integration-secret-that-is-long-enough",
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "NOTIFY_TASK_CREATED": "false",
        "NOTIFY_TASK_COMPLETED": "false",
        "NOTIFY_CREATOR_UPDATES": "false",
    }
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.tokens import CSRF_COOKIE, SESSION_COOKIE, create_session_token
from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models.user import AccessMode, User

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db() -> Session:
    with TestingSession() as session:
        yield session


@pytest.fixture
def users(db: Session) -> dict[str, User]:
    result = {
        "creator": User(rocket_chat_user_id="rc-creator", username="peter", display_name="Peter", is_admin=False, access_mode=AccessMode.ALL),
        "assignee": User(rocket_chat_user_id="rc-assignee", username="alex", display_name="Alex", is_admin=False, access_mode=AccessMode.ASSIGNED),
        "other": User(rocket_chat_user_id="rc-other", username="john", display_name="John", is_admin=False),
        "admin": User(rocket_chat_user_id="rc-admin", username="admin", display_name="Admin", is_admin=True),
    }
    db.add_all(result.values())
    db.commit()
    return result


@pytest.fixture
def client(db: Session) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def authenticate(client: TestClient, user: User) -> None:
    client.cookies.set(SESSION_COOKIE, create_session_token(user, get_settings()))
    client.cookies.set(CSRF_COOKIE, "test-csrf")


@pytest.fixture
def auth_client(client: TestClient, users: dict[str, User]) -> TestClient:
    authenticate(client, users["creator"])
    client.headers["X-CSRF-Token"] = "test-csrf"
    return client
