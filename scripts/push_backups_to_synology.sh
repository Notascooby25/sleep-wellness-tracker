#!/usr/bin/env bash
# Safe push of completed backup snapshots and mood-image archives to Synology NAS.
# Designed to be run as the backup user (same user that owns /srv/shared/backups).

set -euo pipefail

NAS_USER="Congreve202"
NAS_HOST="192.168.68.107"
NAS_PORT="8022"
NAS_TARGET="/volume1/Backups/nuc-server"
SSH_KEY="/home/andy/.ssh/id_ed25519_synology"
RSYNC="/usr/bin/rsync"
LOG_DIR="/srv/shared/backups"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# rsync options:
# -a: archive
# -z: compress during transfer
# --no-o --no-g: don't preserve owner/group (avoid permission issues)
# --prune-empty-dirs: avoid creating empty dirs on remote
# --exclude: avoid copying sensitive/runtime paths
RSYNC_OPTS=( -az --no-o --no-g --prune-empty-dirs --partial --progress --inplace )
EXCLUDES=( --exclude='.env*' --exclude='postgres-data/' )

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/synology_sync_${TIMESTAMP}.log"

exec >>"$LOG_FILE" 2>&1
echo "[push_backups_to_synology] Starting: $(date -u)"

# Copy only completed DB snapshot files (top-level files in backup dir)
echo "[push_backups_to_synology] Syncing backups/ -> ${NAS_USER}@${NAS_HOST}:${NAS_TARGET}/backups/"
"$RSYNC" "${RSYNC_OPTS[@]}" "${EXCLUDES[@]}" "/srv/shared/backups/" "${NAS_USER}@${NAS_HOST}:${NAS_TARGET}/backups/" -e "ssh -i ${SSH_KEY} -p ${NAS_PORT} -o BatchMode=yes"

# Copy mood-image archives if present
if [[ -d "/srv/shared/backups/mood-images" ]]; then
  echo "[push_backups_to_synology] Syncing mood-images/ -> ${NAS_USER}@${NAS_HOST}:${NAS_TARGET}/mood-images/"
  "$RSYNC" "${RSYNC_OPTS[@]}" --exclude='.env*' "/srv/shared/backups/mood-images/" "${NAS_USER}@${NAS_HOST}:${NAS_TARGET}/mood-images/" -e "ssh -i ${SSH_KEY} -p ${NAS_PORT} -o BatchMode=yes"
else
  echo "[push_backups_to_synology] No mood-image backup directory found; skipping."
fi

echo "[push_backups_to_synology] Completed: $(date -u)"
