from __future__ import annotations

import time
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.tokens import OAUTH_STATE_COOKIE, SESSION_COOKIE, create_session_token, decode_oauth_state, decode_session_token
from app.api.auth import _safe_destination
from app.config import get_settings
from app.models.task import Task
from app.models.user import User
from app.integrations.rocketchat.client import RocketChatClient
from app.services.users import upsert_oauth_user


def integration_headers(nonce: str) -> dict[str, str]:
    return {
        "X-OpsTracker-Secret": "test-integration-secret-that-is-long-enough",
        "X-OpsTracker-Timestamp": str(int(time.time())),
        "X-OpsTracker-Nonce": nonce,
    }


def test_forged_session_is_rejected(users: dict[str, User]) -> None:
    token = create_session_token(users["creator"], get_settings())
    claims = decode_session_token(token, get_settings())
    assert claims["rc_uid"] == "rc-creator"
    forged = token[:-2] + "xx"
    try:
        decode_session_token(forged, get_settings())
        assert False, "forged token must fail"
    except jwt.InvalidTokenError:
        pass


def test_logout_requires_csrf(client: TestClient, users: dict[str, User]) -> None:
    from tests.conftest import authenticate

    authenticate(client, users["creator"])
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": "test-csrf"}).status_code == 204


def test_user_sync_without_roles_does_not_revoke_known_admin(db: Session, users: dict[str, User]) -> None:
    updated = upsert_oauth_user(
        db,
        {
            "_id": users["admin"].rocket_chat_user_id,
            "username": users["admin"].username,
            "name": users["admin"].display_name,
            "active": True,
        },
        get_settings(),
    )
    assert updated.is_admin is True


def test_app_launch_requires_normal_oauth_login(client: TestClient, db: Session) -> None:
    payload = {
        "user": {"rocket_chat_user_id": "rc-new", "username": "new", "display_name": "New User"},
        "destination": "/kanban",
    }
    response = client.post("/api/integrations/rocketchat/launch", json=payload, headers=integration_headers("unique-nonce-launch-0001"))
    assert response.status_code == 200
    launch = urlsplit(response.json()["url"])
    assert launch.path == "/api/auth/login"
    assert parse_qs(launch.query) == {"next": ["/kanban"]}
    assert response.json()["expires_in"] == 0
    assert db.query(User).filter(User.rocket_chat_user_id == "rc-new").one_or_none() is None


def test_app_payload_roles_are_ignored_for_launch(client: TestClient, db: Session) -> None:
    payload = {
        "user": {
            "rocket_chat_user_id": "rc-new",
            "username": "new",
            "display_name": "New User",
            "roles": ["admin"],
        },
        "destination": "/kanban",
    }
    response = client.post(
        "/api/integrations/rocketchat/launch",
        json=payload,
        headers=integration_headers("unique-nonce-roles-0001"),
    )
    assert response.status_code == 200
    assert urlsplit(response.json()["url"]).path == "/api/auth/login"
    assert db.query(User).filter(User.rocket_chat_user_id == "rc-new").one_or_none() is None


def test_login_reuses_an_existing_task_session(client: TestClient, users: dict[str, User]) -> None:
    from tests.conftest import authenticate

    authenticate(client, users["creator"])
    response = client.get("/api/auth/login?next=/kanban", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/kanban"


@pytest.mark.parametrize("destination", [
    "/tasks/70", "/tasks/70?embedded=1#comments", "/kanban?task=70&embedded=1",
    "/my?task=70", "/tasks?task=70", "/kanban#board",
])
def test_login_preserves_task_destination_for_existing_session(client, users, destination):
    from tests.conftest import authenticate

    authenticate(client, users["creator"])
    response = client.get("/api/auth/login", params={"next": destination}, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == destination


@pytest.mark.parametrize("destination", ["/tasks/70", "/tasks/70?embedded=1#comments", "/kanban?task=70&embedded=1", "/my?task=70"])
def test_oauth_callback_returns_to_original_task(client, users, monkeypatch, destination):
    response = client.get("/api/auth/login", params={"next": destination}, follow_redirects=False)
    assert response.status_code == 307
    state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    signed_state = client.cookies.get(OAUTH_STATE_COOKIE)
    assert decode_oauth_state(signed_state, get_settings())["destination"] == destination
    user = users["creator"]
    monkeypatch.setattr(RocketChatClient, "exchange_oauth_code", lambda _client, _code: "qa-oauth-access")
    monkeypatch.setattr(RocketChatClient, "oauth_identity", lambda _client, _token: {
        "_id": user.rocket_chat_user_id, "username": user.username, "name": user.display_name, "roles": ["user"],
    })
    callback = client.get("/api/auth/callback", params={"code": "qa-code", "state": state}, follow_redirects=False)
    assert callback.status_code == 307
    assert callback.headers["location"] == destination
    assert client.cookies.get(SESSION_COOKIE)
    assert client.get("/api/users/me").json()["id"] == user.id


@pytest.mark.parametrize("destination", [
    "https://other.invalid/tasks/70", "//other.invalid/tasks/70", "/\\other.invalid/tasks/70",
    "///tasks/70", "////tasks/70",
    "/tasks/70/../../api/auth/logout", "/tasks/not-a-task", "/kanban/other", "/api/auth/logout",
    "/tasks/70\r\nLocation: https://other.invalid", "/tasks/70\t", "/%2f%2fother.invalid/tasks/70",
])
def test_task_return_destination_rejects_unapproved_routes(destination):
    assert _safe_destination(destination) == "/kanban"


def test_integration_nonce_replay_is_rejected(client: TestClient) -> None:
    payload = {
        "user": {"rocket_chat_user_id": "rc-new", "username": "new", "display_name": "New User"},
        "destination": "/kanban",
    }
    headers = integration_headers("unique-nonce-replay-0001")
    assert client.post("/api/integrations/rocketchat/launch", json=payload, headers=headers).status_code == 200
    assert client.post("/api/integrations/rocketchat/launch", json=payload, headers=headers).status_code == 409


def test_message_integration_duplicate(client: TestClient, db: Session) -> None:
    assignee = User(rocket_chat_user_id="rc-alex2", username="alex2", display_name="Alex")
    db.add(assignee); db.commit()
    payload = {
        "user": {"rocket_chat_user_id": "rc-peter2", "username": "peter2", "display_name": "Peter"},
        "source": {
            "room_id": "room-1", "room_name": "it", "room_type": "c", "message_id": "msg-1",
            "author_id": "rc-john", "author_username": "john", "timestamp": "2026-08-10T10:00:00Z",
            "text": "The printer stopped working"
        },
        "title": "Fix the printer", "assignee_username": "alex2", "priority": "HIGH"
    }
    first = client.post("/api/integrations/rocketchat/task-from-message", json=payload, headers=integration_headers("unique-message-nonce-001"))
    assert first.status_code == 201
    second = client.post("/api/integrations/rocketchat/task-from-message", json=payload, headers=integration_headers("unique-message-nonce-002"))
    assert second.status_code == 409
    assert second.json()["detail"]["existing_task_id"] == first.json()["id"]


def test_message_integration_upserts_selected_assignee(client: TestClient, db: Session) -> None:
    payload = {
        "user": {
            "rocket_chat_user_id": "rc-creator-selected", "username": "creator-selected",
            "display_name": "Creator", "roles": ["admin"],
        },
        "assignee": {
            "rocket_chat_user_id": "rc-selected", "username": "selected",
            "display_name": "Selected User", "roles": ["admin"],
        },
        "source": {
            "room_id": "room-selected", "room_name": "ops", "room_type": "c", "message_id": "msg-selected",
            "author_id": "rc-author", "author_username": "author", "timestamp": "2026-08-10T10:00:00Z",
            "text": "Selected assignee task", "message_url": "https://phishing.invalid/fake",
        },
        "title": "Task for selected user",
        "priority": "NORMAL",
    }
    response = client.post(
        "/api/integrations/rocketchat/task-from-message",
        json=payload,
        headers=integration_headers("unique-selected-assignee-001"),
    )
    assert response.status_code == 201
    assert response.json()["assignee_username"] == "selected"
    selected = db.query(User).filter(User.rocket_chat_user_id == "rc-selected").one()
    assert selected.display_name == "Selected User"
    assert selected.is_admin is False
    task = db.get(Task, response.json()["id"])
    assert task is not None
    assert task.rocket_chat_message_url != "https://phishing.invalid/fake"
