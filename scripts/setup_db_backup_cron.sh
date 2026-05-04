#!/usr/bin/env bash
# Install/update a user cron job for DB backups every 12 hours.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"
MAX_BACKUPS="${MAX_BACKUPS:-4}"
SCHEDULE="${SCHEDULE:-0 */12 * * *}"
JOB_SCRIPT="$ROOT_DIR/scripts/run_db_backup_rotation.sh"
LOG_FILE="$BACKUP_DIR/db_backup_cron.log"

if ! mkdir -p "$BACKUP_DIR" 2>/dev/null; then
    echo "Warning: Could not create $BACKUP_DIR as current user."
    echo "         Cron entry will still be installed; ensure the directory exists and is writable at runtime."
fi

CRON_LINE="$SCHEDULE MAX_BACKUPS=$MAX_BACKUPS BACKUP_DIR=$BACKUP_DIR $JOB_SCRIPT >> $LOG_FILE 2>&1"

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

if crontab -l >/dev/null 2>&1; then
    crontab -l | grep -vF "$JOB_SCRIPT" > "$tmpfile"
fi

echo "$CRON_LINE" >> "$tmpfile"
crontab "$tmpfile"

echo "Installed cron job:"
echo "  $CRON_LINE"