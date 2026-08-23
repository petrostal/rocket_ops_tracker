# Public release checklist

1. Copy `.env.example` to a private `.env` only on the deployment host. Never commit it.
2. Generate independent application, integration and database secrets; do not reuse values from tests or examples.
3. Keep private DNS names, SSH aliases, user names, Docker network names and certificate paths in deployment configuration or a private runbook.
4. Run `scripts/check-public-release.sh`.
5. Run it again with a private regular expression, for example:

   ```bash
   PUBLIC_RELEASE_DENY_PATTERN='private-domain|private-user|private-host' scripts/check-public-release.sh
   ```

6. Configure the same expression as the GitHub repository variable `PUBLIC_RELEASE_DENY_PATTERN` so CI can enforce it without committing the private terms.
7. Inspect `git status --short` and `git ls-files` before the first push. Generated Rocket.Chat packages must stay under ignored `rocketchat/app/dist/`.
8. Use a dedicated secret scanner such as Gitleaks against the entire Git history before making an existing repository public.
9. If a real secret ever entered Git history, remove it from history and rotate it. Rewriting history without rotation is insufficient.
10. Choose and add an explicit open-source license before announcing the repository. No license has been selected automatically.

Push the intended branch explicitly, for example `git push origin main`. Do not use `git push --mirror`: local tool/capture refs are not release branches and can retain private working snapshots.

The stable Rocket.Chat application UUID is public application metadata, not a credential. Keep it for releases of this application; forks published as different applications should generate their own identity.
