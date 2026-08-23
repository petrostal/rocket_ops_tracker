from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class RocketChatError(RuntimeError):
    pass


class RocketChatClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.rocketchat_url.rstrip("/")

    def _bot_headers(self) -> dict[str, str]:
        if not self.settings.rocketchat_bot_user_id or not self.settings.rocketchat_bot_token:
            raise RocketChatError("Rocket.Chat bot credentials are not configured")
        return {
            "X-User-Id": self.settings.rocketchat_bot_user_id,
            "X-Auth-Token": self.settings.rocketchat_bot_token,
        }

    def exchange_oauth_code(self, code: str) -> str:
        response = httpx.post(
            f"{self.base_url}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{self.settings.public_url.rstrip('/')}/api/auth/callback",
                "client_id": self.settings.rocketchat_client_id,
                "client_secret": self.settings.rocketchat_client_secret,
            },
            timeout=10,
        )
        if response.status_code >= 400:
            raise RocketChatError(f"OAuth token exchange failed ({response.status_code})")
        token = response.json().get("access_token")
        if not token:
            raise RocketChatError("OAuth token response did not contain access_token")
        return str(token)

    def oauth_identity(self, access_token: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/api/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if response.status_code >= 400:
            raise RocketChatError(f"Rocket.Chat identity request failed ({response.status_code})")
        return dict(response.json())

    def list_users(self, offset: int = 0, count: int = 100) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/api/v1/users.list",
            headers=self._bot_headers(),
            params={"offset": offset, "count": count},
            timeout=15,
        )
        if response.status_code >= 400:
            raise RocketChatError(f"Rocket.Chat users.list failed ({response.status_code})")
        return dict(response.json())

    def user_info(self, user_id: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/api/v1/users.info",
            headers=self._bot_headers(),
            params={"userId": user_id},
            timeout=10,
        )
        if response.status_code >= 400:
            raise RocketChatError(f"Rocket.Chat users.info failed ({response.status_code})")
        return dict(response.json())

    def post_message(self, room_id: str, text: str, thread_message_id: str | None = None) -> None:
        payload: dict[str, Any] = {"channel": room_id, "text": text, "parseUrls": False}
        if thread_message_id:
            payload["tmid"] = thread_message_id
        response = httpx.post(
            f"{self.base_url}/api/v1/chat.postMessage",
            headers={**self._bot_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        if response.status_code >= 400:
            raise RocketChatError(f"Rocket.Chat chat.postMessage failed ({response.status_code})")
