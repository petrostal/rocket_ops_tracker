# Validation

Project checks are intentionally environment-neutral. Run them in CI and before every release:

```bash
PYTHONPATH=backend .venv/bin/pytest -q backend/tests
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix rocketchat/app ci
npm --prefix rocketchat/app run package
scripts/check-public-release.sh
```

Production-only smoke tests require deployment credentials and are not recorded in this public repository. Validate OAuth callback equality, private-app HTTPS connectivity, direct-message delivery, migrations, attachment persistence, reverse-proxy CSP and container restart behavior in a private deployment runbook.

Design images under `docs/design/` contain fictional task and user data. They do not contain production URLs or credentials.
