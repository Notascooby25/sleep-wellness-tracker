#!/usr/bin/env bash
# Run a database backup and then enforce retention.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

MAX_BACKUPS="${MAX_BACKUPS:-4}"
BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"

"$ROOT_DIR/scripts/db_backup.sh"
"$ROOT_DIR/scripts/db_cleanup.sh" --backup-dir "$BACKUP_DIR" --max-backups "$MAX_BACKUPS"

# ── create a checksum manifest for the produced snapshots and archives ──
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MANIFEST_FILE="$BACKUP_DIR/manifest_${TIMESTAMP}.sha256"

# Find top-level db dumps and gzipped SQL files and checksum them.
# Use find + sort to produce stable ordering.
{
  find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.dump' -o -name '*.sql.gz' \) -print0 | sort -z | xargs -0 sha256sum 2>/dev/null || true

  # Include mood-image archives if present
  if [[ -d "/srv/shared/backups/mood-images" ]]; then
    find /srv/shared/backups/mood-images -type f -name '*.tar.gz' -print0 | sort -z | xargs -0 sha256sum 2>/dev/null || true
  fi
} > "$MANIFEST_FILE" || true

# Make the manifest readable by the backup user only
chmod 600 "$MANIFEST_FILE" || true

echo "[run_db_backup_rotation] Manifest created: $MANIFEST_FILE"
