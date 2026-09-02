#!/usr/bin/env bash
# Copy completed backups to an rclone crypt remote without deleting remote history.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive-crypt:backups/sleep-wellness}"
RCLONE_CONFIG="${RCLONE_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/rclone/rclone.conf}"
LOG_DIR="${LOG_DIR:-$BACKUP_DIR}"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[sync_backups_to_google] $*"; }

[[ -d "$BACKUP_DIR" ]] || die "Backup directory not found: $BACKUP_DIR"
[[ -f "$RCLONE_CONFIG" ]] || die "rclone config not found: $RCLONE_CONFIG"
command -v rclone >/dev/null 2>&1 || die "rclone not found in PATH"

mkdir -p "$LOG_DIR"

log "Checking encrypted remote: $RCLONE_REMOTE"
rclone lsd "$RCLONE_REMOTE" --config "$RCLONE_CONFIG" >/dev/null

log "Copying completed backups to $RCLONE_REMOTE"
rclone copy "$BACKUP_DIR" "$RCLONE_REMOTE" \
  --config "$RCLONE_CONFIG" \
  --exclude '*.tmp' \
  --exclude '*.lock' \
  --exclude '*.log' \
  --create-empty-src-dirs

log "Backup copy completed"