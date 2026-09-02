#!/usr/bin/env bash
# Install/update off-host backup and integrity-verification jobs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive-crypt:backups/sleep-wellness}"
NAS_SCHEDULE="${NAS_SCHEDULE:-30 */6 * * *}"
GOOGLE_SCHEDULE="${GOOGLE_SCHEDULE:-35 */6 * * *}"
VERIFY_SCHEDULE="${VERIFY_SCHEDULE:-50 */6 * * *}"
NAS_JOB="$ROOT_DIR/scripts/push_backups_to_synology.sh"
GOOGLE_JOB="$ROOT_DIR/scripts/sync_backups_to_google.sh"
VERIFY_JOB="$ROOT_DIR/scripts/verify_latest_manifest.sh"

mkdir -p "$BACKUP_DIR" 2>/dev/null || true

nas_line="$NAS_SCHEDULE $NAS_JOB >> $BACKUP_DIR/synology_backup_cron.log 2>&1"
google_line="$GOOGLE_SCHEDULE BACKUP_DIR=$BACKUP_DIR RCLONE_REMOTE=$RCLONE_REMOTE $GOOGLE_JOB >> $BACKUP_DIR/google_backup_cron.log 2>&1"
verify_line="$VERIFY_SCHEDULE BACKUP_DIR=$BACKUP_DIR RCLONE_REMOTE=$RCLONE_REMOTE $VERIFY_JOB >> $BACKUP_DIR/google_verify_cron.log 2>&1"

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

if crontab -l >/dev/null 2>&1; then
  crontab -l | grep -vF "$NAS_JOB" | grep -vF "$GOOGLE_JOB" | grep -vF "$VERIFY_JOB" > "$tmpfile"
fi

printf '%s\n%s\n%s\n' "$nas_line" "$google_line" "$verify_line" >> "$tmpfile"
crontab "$tmpfile"

echo "Installed off-host backup jobs:"
printf '  %s\n  %s\n  %s\n' "$nas_line" "$google_line" "$verify_line"