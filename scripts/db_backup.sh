#!/usr/bin/env bash
# db_backup.sh — create a timestamped pg_dump of the sleep-wellness-tracker database.
#
# Run this on the NUC BEFORE pulling and restarting containers after a code update.
#
# Usage:
#   ./scripts/db_backup.sh [/path/to/.env]
#
# Defaults:
#   ENV_FILE   = .env in the project root (same directory as this script's parent)
#   OUTPUT_DIR = ~/sleep-db-backups
#   CONTAINER  = sleep_db   (the postgres container name set in docker-compose.prod.yml)
#   RUNTIME    = auto-detected: docker or podman (whichever is available)
#
# The dump is created inside the running container via pg_dump and written to
# OUTPUT_DIR/<db>_<timestamp>.dump  (custom pg_dump format — use pg_restore to restore).
# A plain-SQL copy (<db>_<timestamp>.sql.gz) is also created for easy inspection.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_FILE="${1:-$ROOT_DIR/.env}"
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/sleep-db-backups}"
CONTAINER="${CONTAINER:-sleep_db}"

# ── helpers ──────────────────────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[db_backup] $*"; }

# ── resolve container runtime ─────────────────────────────────────────────────

if [[ -n "${RUNTIME:-}" ]]; then
    EXEC="$RUNTIME"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    EXEC="docker"
elif command -v podman >/dev/null 2>&1; then
    EXEC="podman"
else
    die "Neither docker nor podman found in PATH."
fi
info "Using container runtime: $EXEC"

# ── load env file ─────────────────────────────────────────────────────────────

[[ -f "$ENV_FILE" ]] || die "Env file not found: $ENV_FILE"

POSTGRES_USER=""
POSTGRES_PASSWORD=""
POSTGRES_DB=""

while IFS='=' read -r key value; do
    [[ -z "$key" ]] && continue
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    # strip inline comments and surrounding quotes
    value="${value%%#*}"
    value="${value#\"}" value="${value%\"}"
    value="${value#\'}" value="${value%\'}"
    value="${value%"${value##*[! ]}"}"   # rtrim
    case "$key" in
        POSTGRES_USER)     POSTGRES_USER="$value" ;;
        POSTGRES_PASSWORD) POSTGRES_PASSWORD="$value" ;;
        POSTGRES_DB)       POSTGRES_DB="$value" ;;
    esac
done < "$ENV_FILE"

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-sleepdb}"

[[ -n "$POSTGRES_PASSWORD" ]] || die "POSTGRES_PASSWORD not found in $ENV_FILE"

# ── check container is running ────────────────────────────────────────────────

if ! "$EXEC" inspect --format '{{.State.Status}}' "$CONTAINER" 2>/dev/null | grep -q "running"; then
    die "Container '$CONTAINER' is not running. Start it first with: $EXEC compose -f docker-compose.prod.yml up -d db"
fi
info "Container '$CONTAINER' is running."

# ── prepare output directory ──────────────────────────────────────────────────

mkdir -p "$OUTPUT_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="$OUTPUT_DIR/${POSTGRES_DB}_${TIMESTAMP}.dump"
SQL_FILE="$OUTPUT_DIR/${POSTGRES_DB}_${TIMESTAMP}.sql.gz"

# ── run pg_dump (custom format) ───────────────────────────────────────────────

info "Creating custom-format dump: $DUMP_FILE"
PGPASSWORD="$POSTGRES_PASSWORD" "$EXEC" exec -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$CONTAINER" \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
    > "$DUMP_FILE"

# ── run pg_dump (plain SQL, gzipped) ─────────────────────────────────────────

info "Creating plain-SQL dump: $SQL_FILE"
PGPASSWORD="$POSTGRES_PASSWORD" "$EXEC" exec -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$CONTAINER" \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-password \
    | gzip -9 > "$SQL_FILE"

# ── report ────────────────────────────────────────────────────────────────────

DUMP_SIZE="$(du -sh "$DUMP_FILE" | cut -f1)"
SQL_SIZE="$(du -sh "$SQL_FILE" | cut -f1)"

info "Backup complete."
info "  Custom dump : $DUMP_FILE  ($DUMP_SIZE)"
info "  SQL (gzip)  : $SQL_FILE  ($SQL_SIZE)"
info ""
info "To restore the custom dump on a fresh container:"
info "  PGPASSWORD=<password> $EXEC exec -e PGPASSWORD=<password> $CONTAINER \\"
info "    pg_restore -U $POSTGRES_USER -d $POSTGRES_DB -Fc --clean --if-exists /path/to/$(basename "$DUMP_FILE")"
info "(Copy the .dump file into the container first with: $EXEC cp <dump> ${CONTAINER}:/tmp/)"
