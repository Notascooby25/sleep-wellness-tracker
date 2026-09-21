#!/usr/bin/env bash
# Install/update off-host backup and integrity-verification jobs, plus the daily
# host-config snapshot that those jobs then carry off the host.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive-crypt:backups/sleep-wellness}"
NAS_SCHEDULE="${NAS_SCHEDULE:-30 */6 * * *}"
GOOGLE_SCHEDULE="${GOOGLE_SCHEDULE:-35 */6 * * *}"
VERIFY_SCHEDULE="${VERIFY_SCHEDULE:-50 */6 * * *}"
# 04:10 daily: ahead of the 06:30 NAS mirror and 06:35 Google copy, so each day's
# snapshot is off the host within a few hours.
HOST_CONFIG_SCHEDULE="${HOST_CONFIG_SCHEDULE:-10 4 * * *}"
NAS_JOB="$ROOT_DIR/scripts/push_srv_to_synology.sh"
OLD_NAS_JOB="$ROOT_DIR/scripts/push_backups_to_synology.sh"
GOOGLE_JOB="$ROOT_DIR/scripts/sync_backups_to_google.sh"
VERIFY_JOB="$ROOT_DIR/scripts/verify_latest_manifest.sh"
HOST_CONFIG_JOB="$ROOT_DIR/scripts/backup_host_config.sh"

mkdir -p "$BACKUP_DIR" 2>/dev/null || true

nas_line="$NAS_SCHEDULE $NAS_JOB >> $BACKUP_DIR/synology_backup_cron.log 2>&1"
google_line="$GOOGLE_SCHEDULE BACKUP_DIR=$BACKUP_DIR RCLONE_REMOTE=$RCLONE_REMOTE $GOOGLE_JOB >> $BACKUP_DIR/google_backup_cron.log 2>&1"
verify_line="$VERIFY_SCHEDULE BACKUP_DIR=$BACKUP_DIR RCLONE_REMOTE=$RCLONE_REMOTE $VERIFY_JOB >> $BACKUP_DIR/google_verify_cron.log 2>&1"
host_config_line="$HOST_CONFIG_SCHEDULE $HOST_CONFIG_JOB >> $BACKUP_DIR/host_config_cron.log 2>&1"

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

if crontab -l >/dev/null 2>&1; then
  # `|| true`: grep -v exits 1 when it filters out every line (a crontab holding only
  # these jobs), which under pipefail + set -e would abort before anything is installed.
  crontab -l | grep -vF "$NAS_JOB" | grep -vF "$OLD_NAS_JOB" | grep -vF "$GOOGLE_JOB" \
    | grep -vF "$VERIFY_JOB" | grep -vF "$HOST_CONFIG_JOB" > "$tmpfile" || true
fi

printf '%s\n%s\n%s\n%s\n' "$nas_line" "$google_line" "$verify_line" "$host_config_line" >> "$tmpfile"
crontab "$tmpfile"

echo "Installed off-host backup jobs:"
printf '  %s\n  %s\n  %s\n  %s\n' "$nas_line" "$google_line" "$verify_line" "$host_config_line"