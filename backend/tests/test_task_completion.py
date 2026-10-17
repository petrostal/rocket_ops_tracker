from __future__ import annotations

import pytest

from app.config import get_settings
from app.integrations.rocketchat.client import RocketChatClient
from app.models.user import AccessMode, User
from app.services.users import upsert_oauth_user
from tests.conftest import authenticate


def make_task(client, users):
    return client.post("/api/tasks", json={"title": "Ready for acceptance", "assignee_id": users["assignee"].id}).json()


def test_default_completion_submits_review_without_closing(auth_client, users):
    task = make_task(auth_client, users)
    authenticate(auth_client, users["assignee"])
    assert auth_client.get("/api/users/me").json()["can_complete_tasks"] is False
    review = auth_client.post(f"/api/tasks/{task['id']}/complete")
    assert review.status_code == 200
    payload = review.json()
    assert payload["status"] == "REVIEW"
    assert payload["completed_at"] is None
    assert payload["events"][-1]["event_type"] == "status_changed"
    assert payload["events"][-1]["event_metadata"] == {"from": "TODO", "to": "REVIEW"}
    assert auth_client.post(f"/api/tasks/{task['id']}/complete").json()["events"] == payload["events"]
    assert auth_client.get("/api/tasks?status=DONE").json()["total"] == 0


@pytest.mark.parametrize("patch", [{"status": "DONE"}, {"status": "DONE", "description": "Must remain unchanged"}])
def test_no_direct_done_bypass_or_partial_mutation(auth_client, users, patch):
    task = make_task(auth_client, users)
    authenticate(auth_client, users["assignee"])
    denied = auth_client.patch(f"/api/tasks/{task['id']}", json=patch)
    assert denied.status_code == 403
    unchanged = auth_client.get(f"/api/tasks/{task['id']}").json()
    assert unchanged["status"] == "TODO"
    assert unchanged["description"] == ""
    assert unchanged["completed_at"] is None
    assert unchanged["events"] == task["events"]


def test_only_admin_can_grant_and_revoke_completion(auth_client, users, db):
    assignee = users["assignee"]
    assert auth_client.patch(f"/api/access/users/{assignee.id}", json={"access_mode": "ASSIGNED", "can_complete_tasks": True}).status_code == 403
    authenticate(auth_client, users["admin"])
    endpoint = f"/api/access/users/{assignee.id}"
    assert auth_client.patch(endpoint, json={"access_mode": "ASSIGNED", "can_complete_tasks": True}, headers={"X-CSRF-Token": "bad"}).status_code == 403
    assert db.get(User, assignee.id).can_complete_tasks is False
    grant = auth_client.patch(endpoint, json={"access_mode": "ASSIGNED", "can_complete_tasks": True})
    assert grant.status_code == 200
    assert grant.json()["can_complete_tasks"] is True
    assert grant.json()["view_watched_tasks"] is True
    assert grant.json()["view_created_tasks"] is False
    assert auth_client.patch(endpoint, json={"access_mode": "ALL"}).json()["can_complete_tasks"] is True
    assert auth_client.patch(endpoint, json={"access_mode": "ASSIGNED", "can_complete_tasks": False}).json()["can_complete_tasks"] is False


@pytest.mark.parametrize("method", ["POST", "PATCH"])
def test_authorized_assignee_can_close_and_permission_revocation_is_immediate(auth_client, users, db, method):
    task = make_task(auth_client, users)
    assignee = users["assignee"]
    authenticate(auth_client, users["admin"])
    assert auth_client.patch(f"/api/access/users/{assignee.id}", json={"access_mode": "ASSIGNED", "can_complete_tasks": True}).status_code == 200
    authenticate(auth_client, assignee)
    assert auth_client.get("/api/users/me").json()["can_complete_tasks"] is True
    endpoint = f"/api/tasks/{task['id']}"
    response = auth_client.post(f"{endpoint}/complete") if method == "POST" else auth_client.patch(endpoint, json={"status": "DONE"})
    assert response.status_code == 200
    assert response.json()["status"] == "DONE"
    assert response.json()["completed_at"]
    assert response.json()["events"][-1]["event_type"] == "completed"
    assert auth_client.post(f"{endpoint}/reopen").status_code == 403
    authenticate(auth_client, users["creator"])
    another = make_task(auth_client, users)
    authenticate(auth_client, assignee)
    assignee.can_complete_tasks = False
    db.commit()
    assert auth_client.get("/api/users/me").json()["can_complete_tasks"] is False
    assert auth_client.patch(f"/api/tasks/{another['id']}", json={"status": "DONE"}).status_code == 403
    assert auth_client.post(f"/api/tasks/{another['id']}/complete").json()["status"] == "REVIEW"


@pytest.mark.parametrize("method", ["POST", "PATCH"])
def test_reviewer_can_close_visible_tasks_without_being_assignee(auth_client, users, db, method):
    task = make_task(auth_client, users)
    reviewer = users["other"]
    reviewer.access_mode = AccessMode.ALL
    reviewer.can_complete_tasks = True
    db.commit()
    authenticate(auth_client, reviewer)
    endpoint = f"/api/tasks/{task['id']}"
    for action in ["start", "review", "wait", "reopen"]:
        assert auth_client.post(f"{endpoint}/{action}").status_code == 403
    for changes in [{"title": "No"}, {"assignee_id": reviewer.id}, {"status": "DONE", "description": "No"}]:
        assert auth_client.patch(endpoint, json=changes).status_code == 403
    response = auth_client.post(f"{endpoint}/complete") if method == "POST" else auth_client.patch(endpoint, json={"status": "DONE"})
    assert response.status_code == 200
    assert response.json()["status"] == "DONE"
    assert response.json()["assignee"]["id"] == users["assignee"].id
    assert response.json()["title"] == task["title"]
    assert auth_client.post(f"{endpoint}/reopen").status_code == 403
    assert auth_client.post(f"{endpoint}/complete").json()["events"] == response.json()["events"]


@pytest.mark.parametrize("mode", [AccessMode.NONE, AccessMode.ASSIGNED, AccessMode.TAGS])
def test_completion_permission_does_not_reveal_hidden_tasks(auth_client, users, db, mode):
    task = make_task(auth_client, users)
    reviewer = users["other"]
    reviewer.access_mode = mode
    reviewer.can_complete_tasks = True
    db.commit()
    authenticate(auth_client, reviewer)
    assert auth_client.get("/api/tasks").json()["total"] == 0
    assert auth_client.post(f"/api/tasks/{task['id']}/complete").status_code == 404
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"status": "DONE"}).status_code == 404


def test_visibility_alone_does_not_grant_review_or_closing(auth_client, users, db):
    task = make_task(auth_client, users)
    viewer = users["other"]
    viewer.access_mode = AccessMode.ALL
    db.commit()
    authenticate(auth_client, viewer)
    assert auth_client.get(f"/api/tasks/{task['id']}").status_code == 200
    assert auth_client.post(f"/api/tasks/{task['id']}/complete").status_code == 403
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"status": "DONE"}).status_code == 403


def test_admin_always_can_close_and_completion_still_requires_csrf(auth_client, users):
    task = make_task(auth_client, users)
    admin = users["admin"]
    assert admin.can_complete_tasks is False
    authenticate(auth_client, admin)
    endpoint = f"/api/tasks/{task['id']}/complete"
    assert auth_client.post(endpoint, headers={"X-CSRF-Token": "bad"}).status_code == 403
    assert auth_client.post(endpoint).json()["status"] == "DONE"


def test_review_notifications_report_actual_destination(auth_client, users, monkeypatch):
    task = make_task(auth_client, users)
    calls = []
    monkeypatch.setattr(get_settings(), "notify_creator_updates", True)
    monkeypatch.setattr(RocketChatClient, "post_message", lambda _client, room, text: calls.append((room, text)))
    authenticate(auth_client, users["assignee"])
    assert auth_client.post(f"/api/tasks/{task['id']}/complete").json()["status"] == "REVIEW"
    assert len(calls) == 1
    assert calls[0][0] == "@peter"
    assert "Проверка" in calls[0][1]
    assert "Готово" not in calls[0][1]


def test_oauth_sync_preserves_local_completion_permission(db, users):
    user = users["assignee"]
    user.can_complete_tasks = True
    db.commit()
    updated = upsert_oauth_user(db, {"_id": user.rocket_chat_user_id, "username": user.username, "roles": []}, get_settings())
    assert updated.can_complete_tasks is True
    newcomer = upsert_oauth_user(db, {"_id": "rc-new", "username": "new", "roles": [], "can_complete_tasks": True}, get_settings())
    assert newcomer.can_complete_tasks is False
