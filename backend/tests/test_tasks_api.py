from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.models.task import Tag, Task, TaskAttachment, TaskStatus
from app.models.user import AccessMode, User
from tests.conftest import authenticate


def test_task_crud_and_status_flow(auth_client: TestClient, users: dict[str, User]) -> None:
    response = auth_client.post(
        "/api/tasks",
        json={
            "title": "  Replace   UPS battery  ",
            "description": "Server room",
            "priority": "HIGH",
            "assignee_id": users["assignee"].id,
        },
    )
    assert response.status_code == 201
    task = response.json()
    assert task["title"] == "Replace UPS battery"
    assert task["events"][0]["event_type"] == "task_created"

    authenticate(auth_client, users["assignee"])
    started = auth_client.post(f"/api/tasks/{task['id']}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "IN_PROGRESS"
    review = auth_client.post(f"/api/tasks/{task['id']}/review")
    assert review.status_code == 200
    assert review.json()["status"] == "REVIEW"
    completed = auth_client.post(f"/api/tasks/{task['id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "REVIEW"
    assert completed.json()["completed_at"] is None
    assert auth_client.patch(f"/api/tasks/{task['id']}", json={"status": "DONE"}).status_code == 403

    authenticate(auth_client, users["admin"])
    completed = auth_client.post(f"/api/tasks/{task['id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "DONE"
    assert completed.json()["completed_at"]

    authenticate(auth_client, users["assignee"])
    forbidden = auth_client.post(f"/api/tasks/{task['id']}/reopen")
    assert forbidden.status_code == 403
    authenticate(auth_client, users["admin"])
    reopened = auth_client.post(f"/api/tasks/{task['id']}/reopen")
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "TODO"


def test_authorization_is_server_side(auth_client: TestClient, users: dict[str, User]) -> None:
    created = auth_client.post("/api/tasks", json={"title": "Configure laptop"}).json()
    authenticate(auth_client, users["other"])
    response = auth_client.patch(f"/api/tasks/{created['id']}", json={"description": "should fail"})
    assert response.status_code == 404
    delete = auth_client.delete(f"/api/tasks/{created['id']}")
    assert delete.status_code == 404


def test_browser_cannot_set_rocketchat_source_metadata(auth_client: TestClient) -> None:
    payload = {"title": "Printer stopped", "rocket_chat_message_id": "message-42"}
    response = auth_client.post("/api/tasks", json=payload)
    assert response.status_code == 422


def test_csrf_is_required(client: TestClient, users: dict[str, User]) -> None:
    authenticate(client, users["creator"])
    response = client.post("/api/tasks", json={"title": "Forged request"})
    assert response.status_code == 403


def test_filters(auth_client: TestClient, users: dict[str, User]) -> None:
    auth_client.post("/api/tasks", json={"title": "First", "priority": "HIGH", "assignee_id": users["creator"].id})
    auth_client.post("/api/tasks", json={"title": "Second", "priority": "LOW"})
    response = auth_client.get("/api/tasks?priority=HIGH&assignee=me")
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["First"]
    assert "comments" not in response.json()["items"][0]
    assert "events" not in response.json()["items"][0]
    assert "attachments" not in response.json()["items"][0]


def test_completed_tasks_are_paginated_by_completion_time(
    auth_client: TestClient,
    db,
    users: dict[str, User],
) -> None:
    now = datetime.now(timezone.utc)
    tasks = [
        Task(
            title=f"Completed {index}",
            creator_id=users["creator"].id,
            status=TaskStatus.DONE,
            completed_at=now - timedelta(hours=index),
        )
        for index in range(12)
    ]
    db.add_all(tasks)
    db.commit()

    first_page = auth_client.get("/api/tasks?status=DONE&limit=10&offset=0")
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["total"] == 12
    assert [item["title"] for item in first_payload["items"]] == [
        f"Completed {index}" for index in range(10)
    ]

    second_page = auth_client.get("/api/tasks?status=DONE&limit=10&offset=10")
    assert second_page.status_code == 200
    assert [item["title"] for item in second_page.json()["items"]] == [
        "Completed 10",
        "Completed 11",
    ]


def test_task_tags_are_reused_editable_and_filterable(auth_client: TestClient) -> None:
    first = auth_client.post(
        "/api/tasks",
        json={"title": "Patch API", "tags": ["Backend", "Срочно", "backend", "#срочно"]},
    )
    second = auth_client.post(
        "/api/tasks",
        json={"title": "Update docs", "tags": ["Backend", "Документация"]},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert [tag["name"] for tag in first.json()["tags"]] == ["Backend", "Срочно"]

    filtered = auth_client.get("/api/tasks?tag=backend&tag=%D1%81%D1%80%D0%BE%D1%87%D0%BD%D0%BE")
    assert filtered.status_code == 200
    assert [item["title"] for item in filtered.json()["items"]] == ["Patch API"]

    updated = auth_client.patch(
        f"/api/tasks/{first.json()['id']}",
        json={"tags": ["Security"]},
    )
    assert updated.status_code == 200
    assert [tag["name"] for tag in updated.json()["tags"]] == ["Security"]
    assert updated.json()["events"][-1]["event_type"] == "tags_changed"

    catalog = auth_client.get("/api/tags")
    assert catalog.status_code == 200
    assert {tag["name"] for tag in catalog.json()} == {
        "Backend", "Документация", "Security", "Срочно"
    }


def test_task_comments_show_author_and_date(auth_client: TestClient, users: dict[str, User]) -> None:
    users["other"].access_mode = AccessMode.ASSIGNED
    task = auth_client.post(
        "/api/tasks",
        json={"title": "Check backup server", "assignee_id": users["other"].id},
    ).json()
    authenticate(auth_client, users["other"])
    response = auth_client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"body": "  Backup completed successfully.  "},
    )
    assert response.status_code == 201
    updated = response.json()
    assert updated["comments"][0]["body"] == "Backup completed successfully."
    assert updated["comments"][0]["author"]["username"] == "john"
    assert updated["comments"][0]["created_at"]
    assert updated["events"][-1]["event_type"] == "comment_added"

    empty = auth_client.post(f"/api/tasks/{task['id']}/comments", json={"body": "   "})
    assert empty.status_code == 422


def test_task_attachments_are_persistent_and_access_controlled(
    auth_client: TestClient,
    db,
    users: dict[str, User],
    monkeypatch,
    tmp_path,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "attachments_dir", str(tmp_path))
    task = auth_client.post("/api/tasks", json={"title": "Attach diagnostics"}).json()

    uploaded = auth_client.post(
        f"/api/tasks/{task['id']}/attachments",
        files={"file": ("../../diagnostics.txt", b"healthy\n", "text/plain")},
    )
    assert uploaded.status_code == 201
    attachment = uploaded.json()["attachments"][0]
    assert attachment["original_name"] == "diagnostics.txt"
    assert attachment["size_bytes"] == 8
    assert attachment["uploaded_by"]["username"] == "peter"
    assert uploaded.json()["events"][-1]["event_type"] == "attachment_added"

    record = db.get(TaskAttachment, attachment["id"])
    assert record is not None
    stored_file = tmp_path / record.stored_name[:2] / record.stored_name
    assert stored_file.read_bytes() == b"healthy\n"

    downloaded = auth_client.get(
        f"/api/tasks/{task['id']}/attachments/{attachment['id']}/download"
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"healthy\n"
    assert "attachment" in downloaded.headers["content-disposition"]
    assert "diagnostics.txt" in downloaded.headers["content-disposition"]
    assert downloaded.headers["cache-control"] == "private, no-store"

    authenticate(auth_client, users["other"])
    hidden = auth_client.get(
        f"/api/tasks/{task['id']}/attachments/{attachment['id']}/download"
    )
    assert hidden.status_code == 404

    users["other"].access_mode = AccessMode.ALL
    db.commit()
    forbidden = auth_client.delete(
        f"/api/tasks/{task['id']}/attachments/{attachment['id']}"
    )
    assert forbidden.status_code == 403

    authenticate(auth_client, users["creator"])
    deleted = auth_client.delete(
        f"/api/tasks/{task['id']}/attachments/{attachment['id']}"
    )
    assert deleted.status_code == 200
    assert deleted.json()["attachments"] == []
    assert deleted.json()["events"][-1]["event_type"] == "attachment_deleted"
    assert not stored_file.exists()


def test_task_attachment_size_limit_cleans_up_partial_file(
    auth_client: TestClient,
    db,
    monkeypatch,
    tmp_path,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "attachments_dir", str(tmp_path))
    monkeypatch.setattr(settings, "attachment_max_bytes", 4)
    task = auth_client.post("/api/tasks", json={"title": "Too large upload"}).json()

    response = auth_client.post(
        f"/api/tasks/{task['id']}/attachments",
        files={"file": ("large.bin", b"12345", "application/octet-stream")},
    )

    assert response.status_code == 413
    assert db.scalar(select(TaskAttachment)) is None
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_task_attachment_count_quota(
    auth_client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "attachments_dir", str(tmp_path))
    monkeypatch.setattr(settings, "attachment_max_per_task", 1)
    task = auth_client.post("/api/tasks", json={"title": "Bounded attachments"}).json()

    first = auth_client.post(
        f"/api/tasks/{task['id']}/attachments",
        files={"file": ("first.txt", b"first", "text/plain")},
    )
    second = auth_client.post(
        f"/api/tasks/{task['id']}/attachments",
        files={"file": ("second.txt", b"second", "text/plain")},
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_task_comment_count_quota(auth_client: TestClient, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "comment_max_per_task", 1)
    task = auth_client.post("/api/tasks", json={"title": "Bounded comments"}).json()

    first = auth_client.post(f"/api/tasks/{task['id']}/comments", json={"body": "First"})
    second = auth_client.post(f"/api/tasks/{task['id']}/comments", json={"body": "Second"})

    assert first.status_code == 201
    assert second.status_code == 409


def test_visibility_modes_are_enforced_for_lists_and_details(
    auth_client: TestClient,
    db,
    users: dict[str, User],
) -> None:
    assigned = auth_client.post(
        "/api/tasks",
        json={"title": "Assigned only", "assignee_id": users["assignee"].id},
    ).json()
    tagged = auth_client.post(
        "/api/tasks",
        json={"title": "Server access", "tags": ["Серверы"]},
    ).json()
    hidden = auth_client.post("/api/tasks", json={"title": "Hidden task"}).json()

    authenticate(auth_client, users["assignee"])
    assigned_list = auth_client.get("/api/tasks").json()["items"]
    assert [item["id"] for item in assigned_list] == [assigned["id"]]
    assert auth_client.get(f"/api/tasks/{hidden['id']}").status_code == 404

    server_tag = db.scalar(select(Tag).where(Tag.normalized_name == "серверы"))
    assert server_tag is not None
    users["other"].access_mode = AccessMode.TAGS
    users["other"].access_tags = [server_tag]
    db.commit()
    authenticate(auth_client, users["other"])
    tagged_list = auth_client.get("/api/tasks").json()["items"]
    assert [item["id"] for item in tagged_list] == [tagged["id"]]
    assert auth_client.get(f"/api/tasks/{assigned['id']}").status_code == 404

    users["other"].access_mode = AccessMode.NONE
    db.commit()
    assert auth_client.get("/api/tasks").json()["items"] == []
    assert auth_client.get(f"/api/tasks/{tagged['id']}").status_code == 404

    authenticate(auth_client, users["admin"])
    assert auth_client.get("/api/tasks").json()["total"] == 3


def test_admin_can_configure_user_access(
    auth_client: TestClient,
    users: dict[str, User],
) -> None:
    created = auth_client.post(
        "/api/tasks", json={"title": "Tagged access", "tags": ["Security"]}
    ).json()
    tag_id = created["tags"][0]["id"]
    authenticate(auth_client, users["admin"])

    updated = auth_client.patch(
        f"/api/access/users/{users['other'].id}",
        json={"access_mode": "ASSIGNED_OR_TAGS", "tag_ids": [tag_id]},
    )
    assert updated.status_code == 200
    assert updated.json()["access_mode"] == "ASSIGNED_OR_TAGS"
    assert updated.json()["access_tags"] == [{"id": tag_id, "name": "Security"}]

    listing = auth_client.get("/api/access/users")
    assert listing.status_code == 200
    assert any(item["username"] == "john" for item in listing.json())

    invalid = auth_client.patch(
        f"/api/access/users/{users['other'].id}",
        json={"access_mode": "TAGS", "tag_ids": [999999]},
    )
    assert invalid.status_code == 422

    authenticate(auth_client, users["creator"])
    assert auth_client.get("/api/access/users").status_code == 403
