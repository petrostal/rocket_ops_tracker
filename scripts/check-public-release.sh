#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: ripgrep (rg) is required" >&2
  exit 2
fi

failed=0
secret_pattern='(-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{16,}|sk_(live|test)_[A-Za-z0-9]{16,})'
report_file() {
  echo "ERROR: $1: $2" >&2
  failed=1
}

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  while IFS= read -r path; do
    case "$path" in
      .env.example) ;;
      .env|.env.*) report_file "tracked environment file" "$path" ;;
      *.pem|*.key|*.p12|*.pfx|*.jks|*.keystore|*.dump|*.sqlite|*.sqlite3|*.db)
        report_file "tracked sensitive artifact" "$path"
        ;;
      rocketchat/app/dist/*|frontend/dist/*|*/node_modules/*)
        report_file "tracked generated artifact" "$path"
        ;;
    esac
  done < <(git ls-files)
fi

while IFS= read -r path; do
  if git check-ignore -q "$path" 2>/dev/null; then
    continue
  fi
  report_file "unignored sensitive-looking file" "$path"
done < <(
  find . -type f \
    \( -name '.env' -o -name '.env.*' -o -name '*.pem' -o -name '*.key' \
       -o -name '*.p12' -o -name '*.pfx' -o -name '*.jks' -o -name '*.keystore' \
       -o -name '*.dump' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' \) \
    -not -path './.git/*' -not -path './.venv/*' -not -name '.env.example'
)

secret_files="$({
  rg -l --hidden \
    -g '!.git/**' -g '!.venv/**' -g '!**/node_modules/**' -g '!**/dist/**' \
    -g '!package-lock.json' \
    "$secret_pattern" . || true
} | sort -u)"
if [[ -n "$secret_files" ]]; then
  while IFS= read -r path; do
    report_file "credential-shaped content" "$path"
  done <<< "$secret_files"
fi

if git rev-parse --verify HEAD >/dev/null 2>&1; then
  history_secret_files="$({
    git grep -l -E "$secret_pattern" $(git rev-list HEAD) -- 2>/dev/null || true
  } | sort -u)"
  if [[ -n "$history_secret_files" ]]; then
    while IFS= read -r path; do
      report_file "credential-shaped content in HEAD history" "$path"
    done <<< "$history_secret_files"
  fi
fi

if [[ -n "${PUBLIC_RELEASE_DENY_PATTERN:-}" ]]; then
  deny_files="$({
    rg -l --hidden \
      -g '!.git/**' -g '!.venv/**' -g '!**/node_modules/**' -g '!**/dist/**' \
      -g '!package-lock.json' "$PUBLIC_RELEASE_DENY_PATTERN" . || true
  } | sort -u)"
  if [[ -n "$deny_files" ]]; then
    while IFS= read -r path; do
      report_file "private deny-pattern match" "$path"
    done <<< "$deny_files"
  fi
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    history_deny_files="$({
      git grep -l -E "$PUBLIC_RELEASE_DENY_PATTERN" $(git rev-list HEAD) -- 2>/dev/null || true
    } | sort -u)"
    if [[ -n "$history_deny_files" ]]; then
      while IFS= read -r path; do
        report_file "private deny-pattern match in HEAD history" "$path"
      done <<< "$history_deny_files"
    fi
  fi
fi

if [[ "$failed" -ne 0 ]]; then
  exit 1
fi

echo "Public-release checks passed."
