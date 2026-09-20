#!/usr/bin/env bash
# Automates a DR drill by spinning up an ephemeral Postgres container,
# restoring the latest .dump, running sanity queries, and destroying it.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"
DB_USER="sleepuser"
DB_NAME="sleepdb"
DB_PASS="dr_test_pass"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[test_restore] $*"; }

if ! command -v docker >/dev/null 2>&1; then
    die "Docker is required for this script."
fi

LATEST_DUMP="$(ls -1t "$BACKUP_DIR"/*.dump 2>/dev/null | head -n1 || true)"
[[ -f "$LATEST_DUMP" ]] || die "No .dump file found in $BACKUP_DIR"

log "Latest dump found: $LATEST_DUMP"
log "Starting ephemeral Postgres container for DR test..."

CONTAINER_ID="$(docker run --rm -d -e POSTGRES_USER="$DB_USER" -e POSTGRES_PASSWORD="$DB_PASS" -e POSTGRES_DB="$DB_NAME" postgres:15)"

cleanup() {
    log "Stopping ephemeral container $CONTAINER_ID..."
    docker stop "$CONTAINER_ID" >/dev/null || true
}
trap cleanup EXIT

log "Waiting for Postgres to become ready..."
ready=false
for i in {1..30}; do
    if docker exec "$CONTAINER_ID" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done

if [[ "$ready" == "false" ]]; then
    die "Postgres failed to become ready in time."
fi

log "Copying dump to container..."
docker cp "$LATEST_DUMP" "$CONTAINER_ID:/tmp/restore.dump"

log "Restoring database..."
docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER_ID" pg_restore -U "$DB_USER" -d "$DB_NAME" -Fc --clean --if-exists /tmp/restore.dump || true

log "Running sanity checks..."
# Verify moods table has rows
MOODS_COUNT="$(docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER_ID" psql -U "$DB_USER" -d "$DB_NAME" -Atc 'SELECT COUNT(*) FROM moods;' 2>/dev/null || echo '0')"
# Verify activities table has rows
ACTIVITIES_COUNT="$(docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER_ID" psql -U "$DB_USER" -d "$DB_NAME" -Atc 'SELECT COUNT(*) FROM activities;' 2>/dev/null || echo '0')"

log "Sanity check complete."
log "Found $MOODS_COUNT moods."
log "Found $ACTIVITIES_COUNT activities."

if [[ "$MOODS_COUNT" -eq 0 ]] || [[ "$ACTIVITIES_COUNT" -eq 0 ]]; then
    die "DR Test Failed: Restored database appears empty or incomplete!"
fi

log "DR Test Passed successfully. Backups are healthy."

