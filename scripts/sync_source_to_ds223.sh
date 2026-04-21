#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

: "${DS223_HOST:?Set DS223_HOST, e.g. DS223_HOST=192.168.68.107}"
DS223_USER="${DS223_USER:-admin}"
DS223_PORT="${DS223_PORT:-8022}"
DS223_SSH_TARGET="${DS223_USER}@${DS223_HOST}"
REMOTE_PROJECT_DIR="${REMOTE_PROJECT_DIR:-/volume1/docker/sleepwell/project/sleep-wellness-tracker-main}"
DRY_RUN="${DRY_RUN:-0}"
SYNC_METHOD="${SYNC_METHOD:-tar}"
SSH_CONTROL_PATH="${SSH_CONTROL_PATH:-$HOME/.ssh/cm-%r@%h:%p}"

EXCLUDE_PATTERNS=(
  .git/
  .venv/
  .history/
  .vscode/
  .idea/
  __pycache__/
  dist/
  build/
  backups/
  logs/
  .env
  .env.local
  .env.*
  docker-compose.yml.local
  *.db
  *.db.bak
  *.sql
  *.sql.bak
  *.dump
  *.bak
  *.tar
  *.tar.gz
  *.zip
  *.crdownload
  backend/garmin_tokens.json
)

SSH_BASE_ARGS=(
  -p "$DS223_PORT"
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=$SSH_CONTROL_PATH"
)

RSYNC_RSH="ssh -p $DS223_PORT -o ControlMaster=auto -o ControlPersist=5m -o ControlPath=$SSH_CONTROL_PATH"

TAR_EXCLUDE_ARGS=()
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
  TAR_EXCLUDE_ARGS+=("--exclude=$pattern")
done

echo "Ensuring remote project directory exists: $REMOTE_PROJECT_DIR"
ssh "${SSH_BASE_ARGS[@]}" "$DS223_SSH_TARGET" "mkdir -p '$REMOTE_PROJECT_DIR'"

echo "Syncing source to DS223: $DS223_SSH_TARGET:$REMOTE_PROJECT_DIR"

if [[ "$SYNC_METHOD" == "rsync" ]]; then
  if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is required for SYNC_METHOD=rsync" >&2
    exit 1
  fi

  RSYNC_ARGS=(
    -az
    --delete
    --human-readable
    --progress
  )

  for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    RSYNC_ARGS+=("--exclude=$pattern")
  done

  if [[ "$DRY_RUN" == "1" ]]; then
    RSYNC_ARGS+=(--dry-run)
  fi

  rsync -e "$RSYNC_RSH" "${RSYNC_ARGS[@]}" "$ROOT_DIR/" "$DS223_SSH_TARGET:$REMOTE_PROJECT_DIR/"
else
  if [[ "$DRY_RUN" == "1" ]]; then
    tar "${TAR_EXCLUDE_ARGS[@]}" -C "$ROOT_DIR" -cf - . | tar -tf - | sed 's#^\./##'
    echo "Dry run only; no files were changed."
    exit 0
  fi

  tar "${TAR_EXCLUDE_ARGS[@]}" -C "$ROOT_DIR" -cf - . \
    | ssh "${SSH_BASE_ARGS[@]}" "$DS223_SSH_TARGET" "tar -xf - -C '$REMOTE_PROJECT_DIR'"
fi

echo "Source sync complete."
