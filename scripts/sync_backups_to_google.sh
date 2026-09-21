#!/usr/bin/env bash
# Copy completed backups to an rclone crypt remote without deleting remote history,
# then prove the backups are actually current and report to a dead-man's-switch.
#
# Freshness matters because `rclone copy` succeeds happily when the local job that
# should have produced a new archive silently died: it just re-uploads yesterday's
# files. So after the upload this script also checks that the newest DB dump, mood
# image archive, expense tracker archive and host-config snapshot are recent, and
# pings /fail if not. One healthchecks.io check therefore covers the four producers
# *and* the upload.
#
# Config: optional ~/.config/google-sync.env (chmod 600, not in git):
#   GOOGLE_HEALTHCHECK_URL   healthchecks.io ping URL (pings <url>/fail on failure)
#   FRESH_DB_HOURS           default 26  (sleepdb_*.dump, made every 12h)
#   FRESH_MOOD_HOURS         default 13  (mood-images/mood_images_*.tar.gz, every 6h)
#   FRESH_EXPENSE_HOURS      default 26  (expense_tracker_data_*.tar.gz, daily)
#   FRESH_HOSTCONFIG_HOURS   default 26  (host-config/host_config_*.tar.gz, daily)
#   Set a FRESH_*_HOURS value to 0 to switch that one check off.
# Precedence: variables already in the environment (e.g. an inline VAR=... in the
# cron line) win over the env file, which wins over the defaults above.
#
# Other environment: BACKUP_DIR, RCLONE_REMOTE, RCLONE_CONFIG, LOG_DIR,
#   GOOGLE_ENV_FILE (default ~/.config/google-sync.env)

set -Eeuo pipefail

# Captured before the env file is sourced: `set -a; . file` overwrites exported
# variables outright, which would let the file silently beat the caller.
env_url="${GOOGLE_HEALTHCHECK_URL:-}"
env_fresh_db="${FRESH_DB_HOURS:-}"
env_fresh_mood="${FRESH_MOOD_HOURS:-}"
env_fresh_expense="${FRESH_EXPENSE_HOURS:-}"
env_fresh_hostconfig="${FRESH_HOSTCONFIG_HOURS:-}"

GOOGLE_ENV_FILE="${GOOGLE_ENV_FILE:-$HOME/.config/google-sync.env}"
if [[ -f "$GOOGLE_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$GOOGLE_ENV_FILE"
    set +a
fi

GOOGLE_HEALTHCHECK_URL="${env_url:-${GOOGLE_HEALTHCHECK_URL:-}}"
FRESH_DB_HOURS="${env_fresh_db:-${FRESH_DB_HOURS:-26}}"
FRESH_MOOD_HOURS="${env_fresh_mood:-${FRESH_MOOD_HOURS:-13}}"
FRESH_EXPENSE_HOURS="${env_fresh_expense:-${FRESH_EXPENSE_HOURS:-26}}"
FRESH_HOSTCONFIG_HOURS="${env_fresh_hostconfig:-${FRESH_HOSTCONFIG_HOURS:-26}}"

BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive-crypt:backups/sleep-wellness}"
RCLONE_CONFIG="${RCLONE_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/rclone/rclone.conf}"
LOG_DIR="${LOG_DIR:-$BACKUP_DIR}"

log() { echo "[sync_backups_to_google] $*"; }

ping_healthcheck() {
    if [[ -n "$GOOGLE_HEALTHCHECK_URL" ]]; then
        curl -fsS -m 10 --retry 3 -o /dev/null "${GOOGLE_HEALTHCHECK_URL}${1:-}" \
            || echo "[sync_backups_to_google] Warning: failed to ping GOOGLE_HEALTHCHECK_URL${1:-}" >&2
    fi
}

die() { echo "ERROR: $*" >&2; ping_healthcheck /fail; exit 1; }

# An unexpected command failure (rclone copy, lsd, ...) under `set -e` lands here.
# Explicit `die` calls exit directly and send their own ping.
trap 'ping_healthcheck /fail' ERR

for v in FRESH_DB_HOURS FRESH_MOOD_HOURS FRESH_EXPENSE_HOURS FRESH_HOSTCONFIG_HOURS; do
    [[ "${!v}" =~ ^[0-9]+$ ]] || die "$v must be a non-negative integer (got: ${!v})"
done

[[ -d "$BACKUP_DIR" ]] || die "Backup directory not found: $BACKUP_DIR"
[[ -f "$RCLONE_CONFIG" ]] || die "rclone config not found: $RCLONE_CONFIG"
command -v rclone >/dev/null 2>&1 || die "rclone not found in PATH"

mkdir -p "$LOG_DIR"

LOCK_FILE="${LOG_DIR}/.google_sync.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    die "Another google sync process is already running."
fi

log "Checking encrypted remote: $RCLONE_REMOTE"
rclone lsd "$RCLONE_REMOTE" --config "$RCLONE_CONFIG" >/dev/null

log "Copying completed backups to $RCLONE_REMOTE"
rclone copy "$BACKUP_DIR" "$RCLONE_REMOTE" \
  --config "$RCLONE_CONFIG" \
  --exclude '*.tmp' \
  --exclude '*.lock' \
  --exclude '*.log' \
  --create-empty-src-dirs

log "Pruning backups older than 90 days from $RCLONE_REMOTE"
# No --rmdirs on the delete: combined with --min-age it appears to make rclone try
# to remove directories that still hold newer files (the age filter hides them from
# its emptiness check), which logged "directory not empty" on every run. Empty
# directories are removed separately below, unfiltered, where "empty" is true.
rclone delete "$RCLONE_REMOTE" \
  --config "$RCLONE_CONFIG" \
  --min-age 90d \
  || log "Warning: pruning old backups failed, continuing."
rclone rmdirs "$RCLONE_REMOTE" \
  --config "$RCLONE_CONFIG" \
  --leave-root \
  || log "Warning: removing empty remote directories failed, continuing."

# ── freshness ────────────────────────────────────────────────────────────────
STALE=()

# newest_age_seconds <dir> <name-glob>: prints the age in seconds of the newest
# matching file directly inside <dir>, or nothing when there is none. awk (not
# `sort | head`) does the max so no pipe is closed early: SIGPIPE from an early
# `head` would trip pipefail. `|| true` covers a file vanishing mid-scan.
newest_age_seconds() {
    local dir="$1" pattern="$2"
    [[ -d "$dir" ]] || return 0
    { find "$dir" -maxdepth 1 -type f -name "$pattern" -printf '%T@\n' 2>/dev/null || true; } \
        | awk -v now="$(date +%s)" '$1 > m { m = $1 } END { if (NR) printf "%d\n", now - m }'
}

# check_fresh <label> <dir> <name-glob> <max-hours>
check_fresh() {
    local label="$1" dir="$2" pattern="$3" max_hours age
    max_hours=$(( 10#$4 ))   # 10#: a value like "08" must not be read as octal
    if (( max_hours == 0 )); then
        log "Freshness check for $label is disabled"
        return 0
    fi
    age="$(newest_age_seconds "$dir" "$pattern")"
    if [[ -z "$age" ]]; then
        log "STALE: no $label found ($dir/$pattern)"
        STALE+=("$label: none found")
    elif (( age > max_hours * 3600 )); then
        log "STALE: newest $label is $(( age / 3600 ))h old (limit ${max_hours}h)"
        STALE+=("$label: $(( age / 3600 ))h old")
    else
        log "OK: newest $label is $(( age / 3600 ))h old (limit ${max_hours}h)"
    fi
}

check_fresh "sleepwell DB dump"        "$BACKUP_DIR"             'sleepdb_*.dump'                  "$FRESH_DB_HOURS"
check_fresh "mood image archive"       "$BACKUP_DIR/mood-images" 'mood_images_*.tar.gz'            "$FRESH_MOOD_HOURS"
check_fresh "expense tracker archive"  "$BACKUP_DIR"             'expense_tracker_data_*.tar.gz'   "$FRESH_EXPENSE_HOURS"
check_fresh "host config snapshot"     "$BACKUP_DIR/host-config" 'host_config_*.tar.gz'            "$FRESH_HOSTCONFIG_HOURS"

if (( ${#STALE[@]} > 0 )); then
    echo "ERROR: stale or missing backups: ${STALE[*]}" >&2
    ping_healthcheck /fail
    exit 1
fi

log "Backup copy completed"
ping_healthcheck
