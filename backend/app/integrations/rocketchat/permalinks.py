from __future__ import annotations

from urllib.parse import quote


def message_permalink(
    base_url: str,
    room_name: str,
    room_type: str,
    message_id: str,
    author_username: str | None = None,
) -> str:
    """Build the Rocket.Chat 8.7 client jump-to-message route in one versioned seam."""
    route = {"c": "channel", "p": "group", "d": "direct"}.get(room_type, "channel")
    target = author_username if room_type == "d" and author_username else room_name
    return f"{base_url.rstrip('/')}/{route}/{quote(target, safe='')}?msg={quote(message_id, safe='')}"

