from __future__ import annotations

import pytest

from app.config import get_settings
from app.integrations.rocketchat.client import RocketChatClient
from app.models.task import Task, TaskStatus
from app.models.user import AccessMode
from app.services.access import can_view_task
from app.services.notifications import notify_comment, notify_status, notify_watchers_added
from tests.conftest import authenticate


def test_creator_visibility_is_opt_in_and_survives_reassignment(auth_client, db, users):
    creator = users["creator"]
    creator.access_mode = AccessMode.ASSIGNED
    db.commit()
    task = auth_client.post("/api/tasks", json={"title": "Created by me", "assignee_id": users["assignee"].id}).json()
    assert auth_client.get(f"/api/tasks/{task['id']}").status_code == 404
    authenticate(auth_client, users["admin"])
    updated = auth_client.patch(f"/api/access/users/{creator.id}", json={"access_mode": "ASSIGNED", "view_created_tasks": True})
    assert updated.status_code == 200
    assert updated.json()["view_created_tasks"] is True
    authenticate(auth_client, creator)
    assert auth_client.get(f"/api/tasks/{task['id']}").status_code == 200
    assert auth_client.get("/api/tasks?participation=created").json()["total"] == 1
    assert auth_client.get("/api/tasks?participation=assigned").json()["total"] == 0
    assert auth_client.post(f"/api/tasks/{task['id']}/complete").status_code == 403
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": users["other"].id}).status_code == 200
    authenticate(auth_client, users["admin"])
    assert auth_client.post(f"/api/tasks/{task['id']}/complete").status_code == 200
    authenticate(auth_client, creator)
    assert auth_client.get("/api/tasks?status=DONE&participation=created").json()["total"] == 1
    creator.access_mode = AccessMode.NONE
    db.commit()
    assert auth_client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_watchers_view_discussion_but_cannot_manage_task(auth_client, db, users, monkeypatch, tmp_path):
    watcher = users["other"]
    watcher.access_mode = AccessMode.ASSIGNED
    db.commit()
    monkeypatch.setattr(get_settings(), "attachments_dir", str(tmp_path))
    task = auth_client.post("/api/tasks", json={
        "title": "Observed task", "assignee_id": users["assignee"].id,
        "watcher_ids": [watcher.id, watcher.id], "tags": ["Observed"],
    }).json()
    assert [user["id"] for user in task["watchers"]] == [watcher.id]
    hidden = auth_client.post("/api/tasks", json={"title": "Private", "tags": ["Private"]}).json()
    attachment = auth_client.post(f"/api/tasks/{task['id']}/attachments", files={"file": ("evidence.txt", b"proof", "text/plain")}).json()["attachments"][0]
    authenticate(auth_client, watcher)
    assert auth_client.get(f"/api/tasks/{task['id']}").status_code == 200
    listing = auth_client.get("/api/tasks?participation=watching").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == task["id"]
    assert auth_client.get(f"/api/tasks/{hidden['id']}").status_code == 404
    assert [tag["name"] for tag in auth_client.get("/api/tags").json()] == ["Observed"]
    assert auth_client.get(f"/api/tasks/{task['id']}/attachments/{attachment['id']}/download").content == b"proof"
    assert auth_client.post(f"/api/tasks/{task['id']}/comments", json={"body": "Following progress"}).status_code == 201
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"title": "No"}).status_code == 403
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"watcher_ids": []}).status_code == 403
    assert auth_client.post(f"/api/tasks/{task['id']}/complete").status_code == 403
    assert auth_client.post(f"/api/tasks/{task['id']}/assign", json={"assignee_id": watcher.id}).status_code == 403
    authenticate(auth_client, users["assignee"])
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"watcher_ids": []}).status_code == 403
    authenticate(auth_client, users["creator"])
    removed = auth_client.patch(f"/api/tasks/{task['id']}", json={"watcher_ids": []})
    assert removed.status_code == 200
    assert removed.json()["events"][-1]["event_metadata"] == {"added": [], "removed": [watcher.username]}
    authenticate(auth_client, watcher)
    assert auth_client.get(f"/api/tasks/{task['id']}").status_code == 404
    assert auth_client.get("/api/tasks?participation=watching").json()["total"] == 0
    assert auth_client.get(f"/api/tasks/{task['id']}/attachments/{attachment['id']}/download").status_code == 404


@pytest.mark.parametrize("access_mode", [AccessMode.ASSIGNED, AccessMode.TAGS, AccessMode.ASSIGNED_OR_TAGS])
def test_watchers_and_creators_are_additive_and_revocable(auth_client, db, users, access_mode):
    user = users["other"]
    user.access_mode = access_mode
    user.view_created_tasks = True
    task = Task(title="Participant", creator=users["creator"], watchers=[user])
    created = Task(title="Author", creator=user)
    db.add_all([task, created])
    db.commit()
    authenticate(auth_client, user)
    assert auth_client.get("/api/tasks").json()["total"] == 2
    assert can_view_task(user, task) and can_view_task(user, created)
    user.view_watched_tasks = False
    user.view_created_tasks = False
    db.commit()
    assert auth_client.get("/api/tasks").json()["total"] == 0
    assert not can_view_task(user, task) and not can_view_task(user, created)
    user.view_watched_tasks = True
    user.view_created_tasks = True
    user.access_mode = AccessMode.NONE
    db.commit()
    assert auth_client.get("/api/tasks").json()["total"] == 0
    assert not can_view_task(user, task) and not can_view_task(user, created)


def test_watcher_validation_candidates_and_csrf(auth_client, db, users):
    watcher = users["other"]
    assert auth_client.post("/api/tasks", json={"title": "Denied watcher", "watcher_ids": [watcher.id]}).status_code == 422
    watcher.access_mode = AccessMode.ASSIGNED
    watcher.view_watched_tasks = False
    db.commit()
    assert auth_client.post("/api/tasks", json={"title": "Not enabled", "watcher_ids": [watcher.id]}).status_code == 422
    watcher.view_watched_tasks = True
    db.commit()
    assert watcher.id in [user["id"] for user in auth_client.get("/api/users?watcher_candidates=true").json()]
    for ids in [[999999], [-1], list(range(1, 52)), None]:
        assert auth_client.post("/api/tasks", json={"title": "Invalid", "watcher_ids": ids}).status_code == 422
    task = auth_client.post("/api/tasks", json={"title": "CSRF"}).json()
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"watcher_ids": [watcher.id]}, headers={"X-CSRF-Token": "bad"}).status_code == 403
    watcher.is_active = False
    db.commit()
    assert watcher.id not in [user["id"] for user in auth_client.get("/api/users?watcher_candidates=true").json()]
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"watcher_ids": [watcher.id]}).status_code == 422


def test_observer_only_cannot_take_unassigned_task(auth_client, db, users):
    watcher = users["other"]
    watcher.access_mode = AccessMode.ASSIGNED
    db.commit()
    task = auth_client.post("/api/tasks", json={"title": "Unassigned", "watcher_ids": [watcher.id]}).json()
    authenticate(auth_client, watcher)
    assert auth_client.post(f"/api/tasks/{task['id']}/take").status_code == 403


def test_forbidden_transition_does_not_partially_change_watchers(auth_client, db, users):
    watcher = users["other"]
    watcher.access_mode = AccessMode.ASSIGNED
    db.commit()
    task = auth_client.post("/api/tasks", json={"title": "Atomic permission check", "assignee_id": users["assignee"].id}).json()
    response = auth_client.patch(f"/api/tasks/{task['id']}", json={"status": "DONE", "watcher_ids": [watcher.id]})
    assert response.status_code == 403
    assert auth_client.get(f"/api/tasks/{task['id']}").json()["watchers"] == []


def test_participant_notifications_are_private_deduplicated_and_access_checked(db, users, monkeypatch):
    watcher = users["other"]
    watcher.access_mode = AccessMode.ASSIGNED
    task = Task(title="Follow progress", creator=users["creator"], assignee=users["assignee"],
                watchers=[watcher, users["creator"], users["assignee"]])
    db.add(task)
    db.commit()
    calls = []
    monkeypatch.setattr(RocketChatClient, "post_message", lambda _client, room, text: calls.append((room, text)))
    settings = get_settings().model_copy(update={"notify_creator_updates": True, "notify_task_completed": True})
    notify_comment(task, task.creator, "News", settings)
    assert sorted(room for room, _ in calls) == ["@alex", "@john"]
    calls.clear()
    task.status = TaskStatus.DONE
    notify_status(task, task.assignee, TaskStatus.REVIEW, settings)
    assert sorted(room for room, _ in calls) == ["@alex", "@john", "@peter"]
    calls.clear()
    notify_watchers_added(task, task.creator, {task.assignee_id}, settings)
    assert [room for room, _ in calls] == ["@john"]
    calls.clear()
    watcher.access_mode = AccessMode.NONE
    notify_comment(task, task.creator, "Restricted", settings)
    assert [room for room, _ in calls] == ["@alex"]
    calls.clear()
    task.watchers = []
    notify_comment(task, task.creator, "Removed", settings)
    assert [room for room, _ in calls] == ["@alex"]
