#!/usr/bin/env bash
# Run a private copy of this branch on the owner's PC, with a copy of live data.
#
#   scripts/preview.sh up            build, copy live data if needed, print the link
#   scripts/preview.sh up --phone    the same, and open it to your home Wi-Fi as well
#   scripts/preview.sh down          stop it and delete its data copy
#   scripts/preview.sh status        show what's running
#   scripts/preview.sh refresh-data  start again from a fresh copy of live data
#
# Server details live in ~/.config/safe-change/preview.env, never in this repo:
#   PREVIEW_PROD_HOST, PREVIEW_PROD_USER, PREVIEW_LAN_ADDRESS (optional)
# The live server is only ever asked for a read-only pg_dump. Mood photos aren't copied.
set -euo pipefail

PROJECT=sleep-wellness-preview
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PREVIEWS_ROOT="$HOME/.local/share/safe-change/previews"
DATA_DIR=${PREVIEW_DATA_DIR:-$PREVIEWS_ROOT/sleep-tracker}
SETTINGS="$HOME/.config/safe-change/preview.env"
SECRETS="$DATA_DIR/preview.secrets.env"
DUMP="$DATA_DIR/dump.sql"
PROD_DB_CONTAINER=${PREVIEW_PROD_DB_CONTAINER:-sleep_db}
PORT=18510

die() { echo "Preview stopped: $*" >&2; exit 1; }

check_safe_to_run() {
    case "${DOCKER_HOST:-}" in
        "" | unix://*) ;;
        *) die "DOCKER_HOST points at another machine. Previews only run on this PC." ;;
    esac
    case "$DATA_DIR" in
        *..*) die "the data folder path can't contain '..'." ;;
        "$PREVIEWS_ROOT"/*) ;;
        *) die "the data folder must be inside $PREVIEWS_ROOT." ;;
    esac
}

compose() {
    local env_args=()
    if [ -f "$SECRETS" ]; then
        env_args=(--env-file "$SECRETS")
    fi
    docker compose -p "$PROJECT" -f "$ROOT/docker-compose.preview.yml" "${env_args[@]}" "$@"
}

copy_live_data() {
    [ -f "$DUMP" ] && return 0
    # shellcheck disable=SC2016  # $POSTGRES_* expand inside the container
    local remote='pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges'
    echo "Copying live data (read-only)..."
    if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$PREVIEW_PROD_USER@$PREVIEW_PROD_HOST" \
        "docker exec $PROD_DB_CONTAINER sh -c '$remote'" > "$DUMP.partial" 2>/dev/null \
        || ! tail -n 5 "$DUMP.partial" | grep -q 'database dump complete'; then
        rm -f "$DUMP.partial"
        die "couldn't copy live data, so nothing was started. Check the server is reachable."
    fi
    mv "$DUMP.partial" "$DUMP"
}

write_secrets() {
    [ -f "$SECRETS" ] && return 0
    (
        umask 077
        python3 - "$DATA_DIR" > "$SECRETS" <<'PY'
import secrets, sys
for name in ("POSTGRES_PASSWORD", "APP_SESSION_SECRET"):
    print(f"{name}={secrets.token_hex(32)}")
print(f"APP_PASSWORD={secrets.token_urlsafe(16)}")
print(f"PREVIEW_DATA_DIR={sys.argv[1]}")
PY
    )
}

load_data_once() {
    [ -f "$DATA_DIR/restored" ] && return 0
    compose up -d --wait db
    if ! compose exec -T db psql -q -v ON_ERROR_STOP=1 --single-transaction \
        -U preview -d preview < "$DUMP" > /dev/null; then
        compose down -v --remove-orphans > /dev/null 2>&1 || true
        die "couldn't load the live data copy, so the preview was removed."
    fi
    touch "$DATA_DIR/restored"
}

cmd_up() {
    # Private to this PC unless asked: signing in shows real health data.
    export PREVIEW_BIND=127.0.0.1
    [ -f "$SETTINGS" ] || die "add the server details to $SETTINGS first (see the top of this script)."
    # shellcheck disable=SC1090
    . "$SETTINGS"
    if [ -z "${PREVIEW_PROD_HOST:-}" ] || [ -z "${PREVIEW_PROD_USER:-}" ]; then
        die "$SETTINGS needs PREVIEW_PROD_HOST and PREVIEW_PROD_USER."
    fi
    export PREVIEW_ORIGIN="http://localhost:$PORT"
    if [ "${1:-}" = "--phone" ]; then
        [ -n "${PREVIEW_LAN_ADDRESS:-}" ] || die "$SETTINGS needs PREVIEW_LAN_ADDRESS for phone access."
        export PREVIEW_BIND=0.0.0.0
        export PREVIEW_ORIGIN="http://$PREVIEW_LAN_ADDRESS:$PORT"
    fi
    mkdir -p "$DATA_DIR/images"
    chmod 700 "$DATA_DIR"
    copy_live_data
    write_secrets
    load_data_once
    compose up -d --build --wait backend frontend_web

    echo
    echo "Preview is running (commit $(git -C "$ROOT" rev-parse --short HEAD), branch $(git -C "$ROOT" branch --show-current))."
    if [ "$PREVIEW_BIND" = 0.0.0.0 ]; then
        echo "  On your phone (home Wi-Fi): $PREVIEW_ORIGIN"
        echo "  Use that link on this PC too. Anyone on your Wi-Fi could reach it, so stop the preview when you are done."
    else
        echo "  On this PC: $PREVIEW_ORIGIN"
        echo "  Private to this PC. For your phone, run: scripts/preview.sh up --phone"
    fi
    echo "  Password: $(sed -n 's/^APP_PASSWORD=//p' "$SECRETS")"
    echo "  This is a copy, cut off from Garmin and other outside services. Mood photos aren't included."
    echo "  When finished: scripts/preview.sh down"
}

cmd_down() {
    compose down -v --remove-orphans
    rm -rf -- "$DATA_DIR"
    echo "Preview stopped and its data copy deleted."
}

cmd_status() {
    compose ps
    if [ -f "$DUMP" ]; then
        echo "Data copy taken: $(date -r "$DUMP" '+%Y-%m-%d %H:%M')"
    else
        echo "No data copy on this PC."
    fi
}

check_safe_to_run
case "${1:-}" in
    up) cmd_up "${2:-}" ;;
    down) cmd_down ;;
    status) cmd_status ;;
    refresh-data)
        cmd_down
        cmd_up
        ;;
    *) die "use: scripts/preview.sh up|up --phone|down|status|refresh-data" ;;
esac
