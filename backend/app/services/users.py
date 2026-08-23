from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.rocketchat.client import RocketChatClient, RocketChatError
from app.models.user import User
from app.schemas.integration import AppUserContext


def _email(identity: dict[str, Any]) -> str | None:
    emails = identity.get("emails") or []
    if emails and isinstance(emails[0], dict):
        return emails[0].get("address")
    return None


def _is_admin(username: str, roles: list[str], settings: Settings) -> bool:
    return bool({"admin", "owner"}.intersection(roles)) or username.lower() in settings.task_admin_usernames


def upsert_oauth_user(db: Session, identity: dict[str, Any], settings: Settings) -> User:
    rc_id = str(identity.get("_id") or identity.get("id") or "")
    username = str(identity.get("username") or "")
    if not rc_id or not username:
        raise ValueError("Rocket.Chat identity is missing _id or username")
    roles_value = identity.get("roles")
    roles = [str(role) for role in roles_value or []]
    user = db.scalar(select(User).where(User.rocket_chat_user_id == rc_id))
    if user is None:
        user = User(rocket_chat_user_id=rc_id, username=username, display_name=username)
        db.add(user)
    user.username = username
    user.display_name = str(identity.get("name") or username)
    user.email = _email(identity)
    user.avatar_url = f"{settings.rocketchat_url.rstrip('/')}/avatar/{username}"
    if roles_value is not None or username.lower() in settings.task_admin_usernames:
        user.is_admin = _is_admin(username, roles, settings)
    user.is_active = bool(identity.get("active", True))
    db.commit()
    db.refresh(user)
    return user


def upsert_app_user(db: Session, context: AppUserContext, settings: Settings) -> User:
    user = db.scalar(select(User).where(User.rocket_chat_user_id == context.rocket_chat_user_id))
    if user is None:
        user = User(
            rocket_chat_user_id=context.rocket_chat_user_id,
            username=context.username,
            display_name=context.display_name,
            avatar_url=f"{settings.rocketchat_url.rstrip('/')}/avatar/{context.username}",
            is_admin=False,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def sync_users(db: Session, client: RocketChatClient, settings: Settings) -> int:
    offset = 0
    count = 100
    seen: set[str] = set()
    while True:
        payload = client.list_users(offset=offset, count=count)
        users = payload.get("users") or []
        for identity in users:
            if identity.get("type", "user") != "user" or not identity.get("username"):
                continue
            if identity.get("roles") is None and identity.get("_id"):
                try:
                    detailed = client.user_info(str(identity["_id"])).get("user") or {}
                    identity = {**identity, **detailed}
                except RocketChatError:
                    pass
            user = upsert_oauth_user(db, identity, settings)
            seen.add(user.rocket_chat_user_id)
        total = int(payload.get("total") or len(users))
        offset += len(users)
        if not users or offset >= total:
            break
    return len(seen)
