# Security notes

- Production rejects blank, published placeholder and development secrets.
- `PUBLIC_URL`, `ROCKETCHAT_URL`, CORS origins and frame origin must be clean HTTPS origins in production.
- Production requires deployment-specific database credentials and refuses SQLite.
- OAuth state and local sessions are signed with `APP_SECRET`.
- Browser mutations require double-submit CSRF validation.
- Integration requests use a distinct secret, constant-time comparison, timestamp window and nonce replay storage.
- App actions enter the browser through OAuth; app-provided roles are rejected.
- Launch codes retained for compatibility are random, hash-stored, one-use and short-lived.
- CORS uses an explicit list; credentials are never combined with `*`.
- Rocket.Chat provenance fields are integration-only.
- Attachment paths use server-generated UUID names; downloads are authorized, forced to attachment disposition and returned with `nosniff`/`no-store` headers.
- Untrusted task/comment text is escaped before insertion into Rocket.Chat Markdown.
- Proxy CSP is generated from deployment settings; organization-specific origins are not compiled into the image.
- Rate limiting and aggregate storage monitoring should also be enforced at the reverse proxy and platform layers.

Rotate `APP_SECRET`, `ROCKETCHAT_APP_SECRET`, OAuth credentials, bot token and database password after any suspected environment or app-setting exposure. Rotating `APP_SECRET` invalidates local sessions.
