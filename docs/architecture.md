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

## Realtime

The UI refreshes after mutations and polls while visible. This avoids an additional Redis dependency; SSE can be added if polling load warrants it.
