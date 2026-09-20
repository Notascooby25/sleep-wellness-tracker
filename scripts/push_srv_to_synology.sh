#!/usr/bin/env bash
# push_srv_to_synology.sh — mirror the NUC's /srv tree to the Synology NAS.
#
# The NAS layout mirrors /srv under NAS_TARGET:
#
#   shared/backups/         append-only: DB dumps, archives, manifests (never deleted on the NAS)
#   shared/mood-images/     mirror
#   shared/garmin-tokens/   mirror
#   shared/logs/            mirror (no version history)
#   sleepwell/  audio-scrobbler-app/  UK-Expense-Tracker/    mirrors
#
# shared/postgres-data is deliberately NOT copied: it is unreadable to this user,
# and a file-level copy of a live Postgres directory is not a usable backup. The
# pg_dump files in shared/backups are the database backup.
#
# Mirrors use --delete, but every file that is changed or removed is first moved to
# NAS_TARGET/_versions/<UTC timestamp>/<dir>/ and pruned after VERSION_DAYS.
# A mirror whose source is missing or empty is skipped rather than emptied.
#
# Usage:
#   ./scripts/push_srv_to_synology.sh [--dry-run]
#
# Config comes from NAS_ENV_FILE (default ~/.config/nas-sync.env, chmod 600, not in git):
#   NAS_USER                 required
#   NAS_HOST                 required
#   NAS_PORT                 default 8022
#   NAS_TARGET               default /volume1/Backups/nuc-server
#   SSH_KEY                  default ~/.ssh/id_ed25519_synology
#   NAS_HEALTHCHECK_URL      optional healthchecks.io ping URL (pings /fail on failure)
# Optional tuning (environment): SRC_ROOT=/srv  VERSION_DAYS=30  MAX_DELETE=200
#   LOG_RETENTION_DAYS=14 (old per-run synology_sync_*.log files in shared/backups)
#
# Output goes to stdout; run it from cron with `>> .../synology_backup_cron.log 2>&1`.

set -euo pipefail

NAS_ENV_FILE="${NAS_ENV_FILE:-$HOME/.config/nas-sync.env}"
if [[ -f "$NAS_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$NAS_ENV_FILE"
    set +a
fi

: "${NAS_USER:?Set NAS_USER in $NAS_ENV_FILE}"
: "${NAS_HOST:?Set NAS_HOST in $NAS_ENV_FILE}"
NAS_PORT="${NAS_PORT:-8022}"
NAS_TARGET="${NAS_TARGET:-/volume1/Backups/nuc-server}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_synology}"
SRC_ROOT="${SRC_ROOT:-/srv}"
VERSION_DAYS="${VERSION_DAYS:-30}"
MAX_DELETE="${MAX_DELETE:-200}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-14}"
NAS_HEALTHCHECK_URL="${NAS_HEALTHCHECK_URL:-}"
DRY_RUN=0

log() { echo "[push_srv_to_synology] $*"; }
die() { echo "ERROR: $*" >&2; ping_healthcheck /fail; exit 1; }

ping_healthcheck() {
    if [[ -n "$NAS_HEALTHCHECK_URL" && "$DRY_RUN" -eq 0 ]]; then
        curl -fsS -m 10 --retry 3 "${NAS_HEALTHCHECK_URL}${1:-}" >/dev/null 2>&1 \
            || echo "[push_srv_to_synology] Warning: failed to ping NAS_HEALTHCHECK_URL" >&2
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run|-n) DRY_RUN=1; shift ;;
        *) echo "Usage: $0 [--dry-run]" >&2; exit 2 ;;
    esac
done

# NAS_TARGET is used in a remote `rm -rf`, so keep it to a plain absolute path.
[[ "$NAS_TARGET" =~ ^/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)+$ ]] \
    || die "NAS_TARGET must be a plain absolute path at least two levels deep (got: $NAS_TARGET)"
[[ "$VERSION_DAYS" =~ ^[0-9]+$ && "$MAX_DELETE" =~ ^[0-9]+$ && "$LOG_RETENTION_DAYS" =~ ^[0-9]+$ ]] \
    || die "VERSION_DAYS, MAX_DELETE and LOG_RETENTION_DAYS must be non-negative integers"

RSYNC="$(command -v rsync)" || die "rsync not found in PATH"
[[ -f "$SSH_KEY" ]] || die "SSH key not found: $SSH_KEY"

LOCK_DIR="$SRC_ROOT/shared/backups"
[[ -d "$LOCK_DIR" ]] || die "Backup directory not found: $LOCK_DIR"
exec 9>"$LOCK_DIR/.synology_sync.lock"
if ! flock -n 9; then
    echo "Another synology sync process is already running." >&2
    exit 1
fi

RSH="ssh -i ${SSH_KEY} -p ${NAS_PORT} -o BatchMode=yes -o ConnectTimeout=15"
nas_ssh() { ssh -i "$SSH_KEY" -p "$NAS_PORT" -o BatchMode=yes -o ConnectTimeout=15 "${NAS_USER}@${NAS_HOST}" "$@"; }

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
VERSIONS_DIR="$NAS_TARGET/_versions/$STAMP"
FAILED=()

COMMON=(
    -az --no-o --no-g --itemize-changes --info=stats1
    --exclude='@eaDir/' --exclude='#recycle/'
    --exclude='postgres-data/' --exclude='pgdata/'
)
(( DRY_RUN )) && COMMON+=(--dry-run)

APP_EXCLUDES=(
    --exclude='.git/' --exclude='.venv/' --exclude='venv/' --exclude='node_modules/'
    --exclude='__pycache__/' --exclude='*.pyc' --exclude='.pytest_cache/'
    --exclude='.ruff_cache/' --exclude='.history/'
)
BACKUP_EXCLUDES=(
    --exclude='*.lock' --exclude='*.tmp' --exclude='synology_sync_*.log' --exclude='.env*'
)

# sync_dir <append|mirror|mirror-nover> <path relative to SRC_ROOT> [extra rsync args...]
# Failures are recorded, not fatal, so one bad target does not skip the rest.
sync_dir() {
    local mode="$1" rel="$2"; shift 2
    local src="$SRC_ROOT/$rel" dest="$NAS_TARGET/$rel"
    local -a opts=("${COMMON[@]}")
    local rc=0

    if [[ ! -d "$src" ]]; then
        log "FAILED $rel: source directory missing: $src"
        FAILED+=("$rel"); return 0
    fi

    if [[ "$mode" != "append" ]]; then
        if [[ -z "$(find "$src" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
            log "FAILED $rel: source is empty, refusing to mirror it over the NAS copy"
            FAILED+=("$rel"); return 0
        fi
        opts+=(--delete --max-delete="$MAX_DELETE")
        [[ "$mode" == "mirror" ]] && opts+=(--backup --backup-dir="$VERSIONS_DIR/$rel")
    fi

    log "Syncing $rel/ ($mode) -> ${NAS_USER}@${NAS_HOST}:${dest}/"
    if (( ! DRY_RUN )); then
        nas_ssh mkdir -p "$dest" || { log "FAILED $rel: cannot create $dest on the NAS"; FAILED+=("$rel"); return 0; }
    fi
    "$RSYNC" "${opts[@]}" "$@" -e "$RSH" "$src/" "${NAS_USER}@${NAS_HOST}:${dest}/" || rc=$?
    # 24 = source files vanished mid-transfer (live logs, rotated dumps): not an error.
    if (( rc != 0 && rc != 24 )); then
        log "FAILED $rel: rsync exit $rc"
        FAILED+=("$rel")
    fi
}

log "Starting: $(date -u) (dry-run=$DRY_RUN)"
nas_ssh true || die "Cannot reach ${NAS_USER}@${NAS_HOST}:${NAS_PORT} with key $SSH_KEY"

# Backup artifacts are append-only on the NAS: local rotation must not delete NAS history.
sync_dir append shared/backups "${BACKUP_EXCLUDES[@]}"

sync_dir mirror       shared/mood-images
sync_dir mirror       shared/garmin-tokens
sync_dir mirror-nover shared/logs
sync_dir mirror       sleepwell           "${APP_EXCLUDES[@]}"
sync_dir mirror       audio-scrobbler-app "${APP_EXCLUDES[@]}"
sync_dir mirror       UK-Expense-Tracker  "${APP_EXCLUDES[@]}"

if (( ! DRY_RUN )); then
    log "Pruning NAS version history older than ${VERSION_DAYS} days"
    nas_ssh "if [ -d '$NAS_TARGET/_versions' ]; then find '$NAS_TARGET/_versions' -mindepth 1 -maxdepth 1 -type d -mtime +$VERSION_DAYS -exec rm -rf -- {} +; fi" \
        || log "Warning: pruning NAS version history failed"
    # The previous script wrote a new log per run into shared/backups; keep only recent ones.
    find "$LOCK_DIR" -maxdepth 1 -type f -name 'synology_sync_*.log' -mtime +"$LOG_RETENTION_DAYS" -delete || true
fi

if (( ${#FAILED[@]} > 0 )); then
    echo "ERROR: ${#FAILED[@]} target(s) failed: ${FAILED[*]}" >&2
    ping_healthcheck /fail
    exit 1
fi

log "Completed: $(date -u)"
ping_healthcheck
