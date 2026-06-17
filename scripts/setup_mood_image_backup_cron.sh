#!/usr/bin/env bash
# Install/update cron jobs for mood image backup and verification.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE_DIR="${SOURCE_DIR:-/srv/shared/mood-images/mood_images}"
BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups/mood-images}"
MAX_BACKUPS="${MAX_BACKUPS:-14}"
BACKUP_SCHEDULE="${BACKUP_SCHEDULE:-15 */6 * * *}"
VERIFY_SCHEDULE="${VERIFY_SCHEDULE:-45 * * * *}"
BACKUP_JOB="$ROOT_DIR/scripts/mood_images_backup.sh"
VERIFY_JOB="$ROOT_DIR/scripts/mood_images_verify_hook.sh"
BACKUP_LOG="${BACKUP_LOG:-/srv/shared/backups/mood_images_backup_cron.log}"
VERIFY_LOG="${VERIFY_LOG:-/srv/shared/backups/mood_images_verify_cron.log}"
HOOK_LOG="${HOOK_LOG:-/srv/shared/backups/mood_images_hook.log}"

mkdir -p "$BACKUP_DIR" >/dev/null 2>&1 || true
mkdir -p "$(dirname "$BACKUP_LOG")" >/dev/null 2>&1 || true

backup_line="$BACKUP_SCHEDULE SOURCE_DIR=$SOURCE_DIR BACKUP_DIR=$BACKUP_DIR MAX_BACKUPS=$MAX_BACKUPS $BACKUP_JOB >> $BACKUP_LOG 2>&1"
verify_line="$VERIFY_SCHEDULE SOURCE_DIR=$SOURCE_DIR HOOK_LOG=$HOOK_LOG $VERIFY_JOB >> $VERIFY_LOG 2>&1"

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

if crontab -l >/dev/null 2>&1; then
  crontab -l | grep -vF "$BACKUP_JOB" | grep -vF "$VERIFY_JOB" > "$tmpfile"
fi

echo "$backup_line" >> "$tmpfile"
echo "$verify_line" >> "$tmpfile"
crontab "$tmpfile"

echo "Installed cron jobs:"
echo "  $backup_line"
echo "  $verify_line"
