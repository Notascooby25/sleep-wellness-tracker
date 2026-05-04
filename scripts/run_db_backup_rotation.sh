#!/usr/bin/env bash
# Run a database backup and then enforce retention.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

MAX_BACKUPS="${MAX_BACKUPS:-4}"
BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"

"$ROOT_DIR/scripts/db_backup.sh"
"$ROOT_DIR/scripts/db_cleanup.sh" --backup-dir "$BACKUP_DIR" --max-backups "$MAX_BACKUPS"