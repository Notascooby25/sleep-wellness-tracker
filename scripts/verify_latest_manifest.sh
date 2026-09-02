#!/usr/bin/env bash
# Wrapper to find the latest local manifest and verify it against the remote via rclone.
# Intended to be run from the backup user's crontab.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive-crypt:backups/sleep-wellness}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_SCRIPT="${VERIFY_SCRIPT:-$SCRIPT_DIR/verify_remote_manifest.sh}"

# Find the newest manifest file (if any)
LATEST="$(ls -1t "${BACKUP_DIR}"/manifest_*.sha256 2>/dev/null | head -n1 || true)"

if [[ -z "$LATEST" ]]; then
  echo "[verify_latest_manifest] No manifest found in ${BACKUP_DIR}"
  exit 0
fi

BASENAME="$(basename "$LATEST")"
REMOTE="${RCLONE_REMOTE}/${BASENAME}"

echo "[verify_latest_manifest] Verifying ${LATEST} -> ${REMOTE}"
"$VERIFY_SCRIPT" "$LATEST" "$REMOTE"

