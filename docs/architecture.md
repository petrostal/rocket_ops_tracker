# Architecture

```text
Rocket.Chat clients
  |  private app: message/room actions, slash command, UIKit
  |  HTTPS + integration secret + timestamp + nonce
  v
FastAPI task service <---- OAuth authorization code ---- Rocket.Chat OAuth
  |        |
  |        +---- bot REST API: identity sync and direct messages
  v
PostgreSQL + attachment volume
  ^
  |
React/Vite UI (same origin, HttpOnly session + CSRF)
```

## Components

- `frontend`: React UI and an Nginx runtime template.
- `backend`: API, OAuth client, signed sessions, authorization, task events, attachments and notification policy.
- `tasks-postgres`: task, identity, integration nonce and launch-code state.
- `tasks-worker`: overdue notification checks.
- `rocketchat/app`: private Apps Engine adapter without a task database or long-lived user token.
- `docker-compose.yml`: parameterized Traefik deployment.
- `nginx/opstracker.conf.template`: parameterized standalone Nginx alternative.

## Trust boundaries

| Boundary | Decision |
|---|---|
| Browser → API | Signed HttpOnly session; CSRF cookie/header required for mutations. |
| Rocket.Chat app → integration API | Dedicated secret, timestamp window and one-use nonce over HTTPS. App fields never grant administrator roles. |
| App button → browser | Redirect to normal OAuth login; the app payload cannot mint a browser identity. |
| API → Rocket.Chat | Deployment-supplied HTTPS origin and server-only OAuth/bot credentials. |
| API → PostgreSQL/filesystem | SQLAlchemy binding, task authorization, opaque stored filenames and bounded files. |
| UI framing | Deployment-supplied single `ALLOWED_FRAME_ORIGIN`; no wildcard. |

## Identity

OAuth and explicit server-side synchronization are authoritative for administrator roles. App-originated user records default to non-admin and cannot submit role fields. This keeps compromise of the integration secret scoped away from browser administrator sessions.

## Source provenance

Browser task creation accepts only ordinary task fields. Rocket.Chat room/message/author metadata is represented by `IntegrationTaskCreate` and can only enter through authenticated integration handlers.

## Task participation and visibility

The existing per-user visibility profile remains the base policy. Administrators can additionally enable `view_created_tasks` (off by default) and `view_watched_tasks` (on by default). These flags add tasks authored or watched by the user to their permitted tasks. `NONE` denies all tasks regardless of participation; inactive users are denied as well. Lists, counts, direct links, tags, comments and attachment routes use the same backend policy.

Authors and administrators can select up to 50 active, eligible watchers when creating or editing a task. Watchers are stored in `task_watchers`, with indexes for both task and user lookups. Adding/removing watchers is recorded in activity history. Watching grants viewing, discussion and attachment access, not task editing, reassignment or status changes. Removing a watcher revokes only this participation grant; another base rule may still permit access.

New watchers receive a direct message in Rocket.Chat. Status changes and comments also notify watchers, with one message per recipient per event and comment authors excluded. Notification delivery checks current visibility and active status; disabled/no-access users receive no task content. Notifications use the existing `NOTIFY_CREATOR_UPDATES` switch and never post to shared channels.

The My Tasks view offers Assigned to me, Created by me and Watching filters, intersected with the user's visibility policy. The same participation filter is available on the Kanban board and All Tasks; filters persist across reloads. Existing visibility profiles are unchanged by migration. To enable authorship access for a user, an administrator checks “Видеть созданные мной задачи” under Access and saves.

## Realtime updates

The UI refreshes after mutations and polls while visible. This avoids an additional Redis dependency; SSE can be added if polling load warrants it.
