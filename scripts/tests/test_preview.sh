#!/usr/bin/env bash
# Fixture tests: scripts/preview.sh
#
# Hermetic: docker and ssh are stubs on PATH and HOME is a temp folder, so
# nothing here can reach a real container or the production server.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SCRIPT="$ROOT/scripts/preview.sh"
# shellcheck source=/dev/null
. "$HERE/lib.sh"

setup() {
    T=$(mktemp -d)
    export HOME="$T/home"
    DATA="$HOME/.local/share/safe-change/previews/sleep-tracker"
    mkdir -p "$HOME/.config/safe-change" "$T/bin"
    cat > "$HOME/.config/safe-change/preview.env" <<'EOF'
PREVIEW_PROD_HOST=fake-host
PREVIEW_PROD_USER=fake-user
PREVIEW_LAN_ADDRESS=10.0.0.5
EOF
    cat > "$T/bin/docker" <<EOF
#!/usr/bin/env bash
echo "docker \$*" >> "$T/docker.log"
echo "PREVIEW_BIND=\${PREVIEW_BIND:-} PREVIEW_ORIGIN=\${PREVIEW_ORIGIN:-}" >> "$T/env.log"
case "\$*" in
  *"exec -T db psql"*) cat > "$T/restored.sql"; exit "\${FAKE_RESTORE_RC:-0}" ;;
esac
exit 0
EOF
    cat > "$T/bin/ssh" <<EOF
#!/usr/bin/env bash
echo "ssh \$*" >> "$T/ssh.log"
if [ "\${FAKE_SSH_MODE:-ok}" = fail ]; then exit 1; fi
if [ "\${FAKE_SSH_MODE:-ok}" = partial ]; then echo "CREATE TABLE half"; exit 1; fi
if [ "\${FAKE_SSH_MODE:-ok}" = truncated ]; then echo "CREATE TABLE half"; exit 0; fi
echo "CREATE TABLE mood;"
echo "-- PostgreSQL database dump complete"
EOF
    chmod +x "$T/bin/docker" "$T/bin/ssh"
    export PATH="$T/bin:$PATH"
    unset DOCKER_HOST PREVIEW_DATA_DIR FAKE_SSH_MODE FAKE_RESTORE_RC
}

run() { bash "$SCRIPT" "$@" > "$T/out.txt" 2>&1; }
every_compose_call_uses_preview_project() {
    ! grep 'compose' "$T/docker.log" | grep -qv -- '-p sleep-wellness-preview'
}

echo "down only targets the preview project"
setup; mkdir -p "$DATA"; touch "$DATA/dump.sql"
run down
check "exits cleanly" test $? -eq 0
check "called compose" grep -q compose "$T/docker.log"
check "every call names the preview project" every_compose_call_uses_preview_project
check "data folder removed" test ! -e "$DATA"

echo "down refuses a data folder outside the previews area"
setup; mkdir -p "$T/precious"; touch "$T/precious/keep"
PREVIEW_DATA_DIR="$T/precious" run down; rc=$?
check "exits non-zero" test "$rc" -ne 0
check "file kept" test -e "$T/precious/keep"
check "docker not called" test ! -e "$T/docker.log"
PREVIEW_DATA_DIR="$DATA/../../../../../precious" run down; rc=$?
check "refuses .. in the path" test "$rc" -ne 0

echo "up stops plainly when the server can't be reached"
setup
FAKE_SSH_MODE=fail run up; rc=$?
check "exits non-zero" test "$rc" -ne 0
check "plain message" grep -qi "couldn't copy" "$T/out.txt"
check "nothing restored" test ! -e "$T/restored.sql"

echo "a partial or truncated copy is never used"
for mode in partial truncated; do
    setup
    FAKE_SSH_MODE=$mode run up; rc=$?
    check "$mode: exits non-zero" test "$rc" -ne 0
    check "$mode: no dump left" test ! -e "$DATA/dump.sql"
    check "$mode: no temp file left" test ! -e "$DATA/dump.sql.partial"
done

echo "a failed restore doesn't leave a preview that looks fine"
setup
FAKE_RESTORE_RC=3 run up; rc=$?
check "exits non-zero" test "$rc" -ne 0
check "backend never started" bash -c "! grep -q 'up .*backend' '$T/docker.log'"
check "plain message" grep -qi "couldn't load" "$T/out.txt"

echo "refuses a remote docker"
setup
DOCKER_HOST=tcp://10.0.0.9:2375 run up; rc=$?
check "exits non-zero" test "$rc" -ne 0
check "docker not called" test ! -e "$T/docker.log"

echo "a missing server setting stops plainly"
setup; rm "$HOME/.config/safe-change/preview.env"
run up; rc=$?
check "exits non-zero" test "$rc" -ne 0
check "names the settings file" grep -q preview.env "$T/out.txt"

echo "a good run"
setup
run up; rc=$?
check "exits cleanly" test "$rc" -eq 0
check "every call names the preview project" every_compose_call_uses_preview_project
check "server only asked for a dump" bash -c "[ \$(grep -c . '$T/ssh.log') -eq 1 ] && grep -q 'docker exec sleep_db' '$T/ssh.log' && grep -q pg_dump '$T/ssh.log'"
check "PC link printed" grep -q "http://localhost:18510" "$T/out.txt"
check "commit printed" grep -qi "commit" "$T/out.txt"
check "secrets file is private" test "$(stat -c %a "$DATA/preview.secrets.env")" = 600
check "data folder is private" test "$(stat -c %a "$DATA")" = 700
check "image folder exists for the mount" test -d "$DATA/images"
secret=$(sed -n 's/^APP_SESSION_SECRET=//p' "$DATA/preview.secrets.env")
check "session secret generated" test -n "$secret"
check "session secret never printed" hasnt "$T/out.txt" "$secret"
pw=$(sed -n 's/^APP_PASSWORD=//p' "$DATA/preview.secrets.env")
check "throwaway password shown once to sign in" grep -qF "$pw" "$T/out.txt"

echo "private to this PC unless the phone is asked for"
setup
PREVIEW_BIND=wrong run up
check "no phone link by default" hasnt "$T/out.txt" "http://10.0.0.5"
check "says how to get a phone link" grep -q -- "--phone" "$T/out.txt"
check "binds to this PC only" grep -q "PREVIEW_BIND=127.0.0.1" "$T/env.log"
setup
run up --phone
check "phone link when asked" grep -q "http://10.0.0.5:18510" "$T/out.txt"
check "warns about the Wi-Fi" grep -qi "anyone on your Wi-Fi" "$T/out.txt"
check "binds to the network" grep -q "PREVIEW_BIND=0.0.0.0" "$T/env.log"
check "site origin follows the address" grep -q "PREVIEW_ORIGIN=http://10.0.0.5:18510" "$T/env.log"

echo "the preview stack is isolated"
C="$ROOT/docker-compose.preview.yml"
check "own project name" grep -q '^name: sleep-wellness-preview' "$C"
check "no shared server folders" hasnt "$C" "/srv/shared"
check "no watchtower" hasnt "$C" "watchtower"
check "no real settings file" hasnt "$C" "env_file"
check "no Garmin tokens" hasnt "$C" "garmin_tokens"
check "Garmin sync off" grep -q 'GARMIN_AUTOSYNC_ENABLED: "false"' "$C"
check "database publishes no port" bash -c "! sed -n '/^  db:/,/^  backend:/p' '$C' | grep -q ports"
check "backend publishes no port" bash -c "! sed -n '/^  backend:/,/^  frontend_web:/p' '$C' | grep -q ports"
check "backend has no internet route" grep -q 'internal: true' "$C"
check "port follows the chosen address" grep -q 'PREVIEW_BIND' "$C"

summary
