#!/usr/bin/env bash
# Automates a DR drill: spins up an ephemeral Postgres container, restores the latest
# .dump into it, checks the result, and destroys the container.
#
# The drill FAILS (non-zero exit, no "DR Test Passed") when:
#   - there is no dump, it is empty, or it is older than DRILL_MAX_AGE_HOURS
#   - pg_restore reports any error
#   - the restored database has a different number of tables to the dump's table list
#   - moods or activities is empty after the restore
#   - the live database container is running and a restored count is below
#     DRILL_MIN_LIVE_FRACTION of the live count (the dump lags live, it must not be tiny)
#
# It never writes to the live container: that is only asked for its Postgres version and,
# read-only, for row counts.
#
# Environment (all optional):
#   BACKUP_DIR               dumps directory (default /srv/shared/backups)
#   LIVE_CONTAINER           live database container (default sleep_db)
#   PG_IMAGE                 image for the throwaway container
#                            (default postgres:<major version of the live container>, else postgres:15)
#   DRILL_MAX_AGE_HOURS      newest dump must be younger than this (default 14)
#   DRILL_MIN_LIVE_FRACTION  restored count / live count must be at least this (default 0.9)

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"
LIVE_CONTAINER="${LIVE_CONTAINER:-sleep_db}"
DRILL_MAX_AGE_HOURS="${DRILL_MAX_AGE_HOURS:-14}"
DRILL_MIN_LIVE_FRACTION="${DRILL_MIN_LIVE_FRACTION:-0.9}"
DB_USER="sleepuser"
DB_NAME="sleepdb"
DB_PASS="dr_test_pass"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[test_restore] $*"; }

command -v docker >/dev/null 2>&1 || die "Docker is required for this script."
[[ "$DRILL_MAX_AGE_HOURS" =~ ^[0-9]+$ ]] || die "DRILL_MAX_AGE_HOURS must be a whole number (got: $DRILL_MAX_AGE_HOURS)"

# ── 1. the dump: exists, is not empty, is recent ─────────────────────────────

LATEST_DUMP="$(ls -1t "$BACKUP_DIR"/*.dump 2>/dev/null | head -n1 || true)"
[[ -f "$LATEST_DUMP" ]] || die "No .dump file found in $BACKUP_DIR"
[[ -s "$LATEST_DUMP" ]] || die "Newest dump is empty: $LATEST_DUMP"

age_hours=$(( ( $(date +%s) - $(stat -c %Y "$LATEST_DUMP") ) / 3600 ))
if (( age_hours > DRILL_MAX_AGE_HOURS )); then
    die "Newest dump $(basename "$LATEST_DUMP") is ${age_hours}h old (limit ${DRILL_MAX_AGE_HOURS}h): the backup job may have stopped."
fi
log "Latest dump found: $LATEST_DUMP (${age_hours}h old)"

# ── 2. which Postgres to restore into ────────────────────────────────────────

resolve_image() {
    if [[ -n "${PG_IMAGE:-}" ]]; then
        echo "$PG_IMAGE"
        return
    fi
    local ver major
    ver="$(docker exec "$LIVE_CONTAINER" postgres --version 2>/dev/null || true)"
    major="$(sed -nE 's/.*PostgreSQL\) ([0-9]+).*/\1/p' <<<"$ver")"
    echo "postgres:${major:-15}"
}
IMAGE="$(resolve_image)"
log "Using image $IMAGE"

# ── 3. throwaway container ───────────────────────────────────────────────────

log "Starting ephemeral Postgres container for DR test..."
CONTAINER_ID="$(docker run --rm -d -e POSTGRES_USER="$DB_USER" -e POSTGRES_PASSWORD="$DB_PASS" -e POSTGRES_DB="$DB_NAME" "$IMAGE")"

cleanup() {
    log "Stopping ephemeral container $CONTAINER_ID..."
    docker stop "$CONTAINER_ID" >/dev/null || true
}
trap cleanup EXIT

log "Waiting for Postgres to become ready..."
ready=false
for _ in {1..30}; do
    # Over TCP on purpose: while the image initialises, a temporary server listens on the unix
    # socket only, so a socket probe can succeed before the real database exists.
    if docker exec "$CONTAINER_ID" pg_isready -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
[[ "$ready" == "true" ]] || die "Postgres failed to become ready in time."

log "Copying dump to container..."
docker cp "$LATEST_DUMP" "$CONTAINER_ID:/tmp/restore.dump"

# ── 4. restore: any error fails the drill ────────────────────────────────────

# How many tables the dump says it holds (TABLE entries, not TABLE DATA).
DUMP_TABLES="$(docker exec "$CONTAINER_ID" pg_restore -l /tmp/restore.dump | grep -c ' TABLE public ' || true)"
[[ "$DUMP_TABLES" =~ ^[0-9]+$ && "$DUMP_TABLES" -gt 0 ]] || die "The dump lists no tables: it is not a usable archive."

log "Restoring database ($DUMP_TABLES tables in the dump)..."
if ! docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER_ID" \
        pg_restore -U "$DB_USER" -d "$DB_NAME" -Fc --clean --if-exists --exit-on-error --no-owner --no-privileges /tmp/restore.dump; then
    die "DR Test Failed: pg_restore failed, so this backup cannot be restored cleanly."
fi

# ── 5. sanity checks on the restored copy ────────────────────────────────────

restored_query() {  # restored_query <sql> -> prints the single value
    docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER_ID" psql -U "$DB_USER" -d "$DB_NAME" -Atc "$1"
}

log "Running sanity checks..."
DB_TABLES="$(restored_query "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")" \
    || die "DR Test Failed: could not count the restored tables."
MOODS_COUNT="$(restored_query 'SELECT COUNT(*) FROM moods;')" \
    || die "DR Test Failed: could not read the restored moods table."
ACTIVITIES_COUNT="$(restored_query 'SELECT COUNT(*) FROM activities;')" \
    || die "DR Test Failed: could not read the restored activities table."

for v in "$DB_TABLES" "$MOODS_COUNT" "$ACTIVITIES_COUNT"; do
    [[ "$v" =~ ^[0-9]+$ ]] || die "DR Test Failed: unexpected non-numeric answer from the restored database: '$v'"
done

log "Restored $DB_TABLES tables (dump lists $DUMP_TABLES)."
log "Found $MOODS_COUNT moods."
log "Found $ACTIVITIES_COUNT activities."

[[ "$DB_TABLES" -eq "$DUMP_TABLES" ]] \
    || die "DR Test Failed: restored $DB_TABLES tables but the dump lists $DUMP_TABLES tables."
if [[ "$MOODS_COUNT" -eq 0 ]] || [[ "$ACTIVITIES_COUNT" -eq 0 ]]; then
    die "DR Test Failed: Restored database appears empty or incomplete!"
fi

# ── 6. compare with the live database (read-only), when it is reachable ──────

live_running() {
    docker inspect --format '{{.State.Status}}' "$LIVE_CONTAINER" 2>/dev/null | grep -q running
}

live_count() {  # live_count <table> -> prints the live row count (read-only SELECT)
    docker exec "$LIVE_CONTAINER" sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -Atc 'SELECT COUNT(*) FROM $1;'"
}

at_least_fraction() {  # at_least_fraction <restored> <live>
    awk -v r="$1" -v l="$2" -v f="$DRILL_MIN_LIVE_FRACTION" 'BEGIN { exit !(l == 0 || r >= l * f) }'
}

if live_running; then
    for table in moods activities; do
        live="$(live_count "$table")" || die "DR Test Failed: could not read $table from the live database."
        [[ "$live" =~ ^[0-9]+$ ]] || die "DR Test Failed: unexpected live $table count: '$live'"
        if [[ "$table" == moods ]]; then restored="$MOODS_COUNT"; else restored="$ACTIVITIES_COUNT"; fi
        at_least_fraction "$restored" "$live" \
            || die "DR Test Failed: restored $table ($restored) is below ${DRILL_MIN_LIVE_FRACTION} of live ($live)."
        log "Live check: $table restored $restored vs live $live."
    done
else
    log "Note: skipping live comparison (live container not running)."
fi

log "DR Test Passed successfully. Backups are healthy."
