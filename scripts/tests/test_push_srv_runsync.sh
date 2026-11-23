#!/usr/bin/env bash
# Fixture test: scripts/push_srv_to_synology.sh mirrors the whole /srv/runsync folder like the other apps.
#
# Hermetic: ssh, rsync and curl are replaced by stubs on PATH that only record their arguments,
# and all state lives in a temp dir that is removed on exit. Nothing contacts a NAS.
# Needs: bash, flock (util-linux).
# Run:   scripts/tests/test_push_srv_runsync.sh
# (PUSH_SCRIPT can point at another copy of the script, to prove the test fails without the change.)
set -uo pipefail
SP=$(cd "$(dirname "$0")" && pwd); . "$SP/lib.sh"
PUSH_SCRIPT="${PUSH_SCRIPT:-$SP/../push_srv_to_synology.sh}"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

S=$T/srv; H=$T/home; BIN=$T/bin; LOG=$T/rsync.log
mkdir -p "$BIN" "$H/.ssh" "$H/.config" "$S/shared/backups" "$S/shared/mood-images" "$S/shared/garmin-tokens" \
         "$S/shared/logs" "$S/sleepwell" "$S/audio-scrobbler-app" "$S/UK-Expense-Tracker" \
         "$S/runsync/backups" "$S/runsync/other"
for d in shared/mood-images shared/garmin-tokens shared/logs sleepwell audio-scrobbler-app UK-Expense-Tracker; do echo x > "$S/$d/f"; done
echo dump > "$S/runsync/backups/runsync_1.dump"
echo SECRET > "$S/runsync/.env"
echo other > "$S/runsync/other/f"
echo k > "$H/.ssh/key"

printf '#!/bin/sh\nexit 0\n' > "$BIN/ssh"
printf '#!/bin/sh\nexit 0\n' > "$BIN/curl"
printf '#!/bin/sh\nprintf "%%s\\n" "$*" >> "%s"\nexit 0\n' "$LOG" > "$BIN/rsync"
chmod +x "$BIN/ssh" "$BIN/curl" "$BIN/rsync"

run() { env -i HOME="$H" PATH="$BIN:/usr/bin:/bin" NAS_ENV_FILE=/nonexistent NAS_USER=u NAS_HOST=nas.invalid \
            SSH_KEY="$H/.ssh/key" SRC_ROOT="$S" NAS_TARGET=/volume1/test/nuc "$PUSH_SCRIPT" "$@"; }

echo "== the whole runsync folder is mirrored, like the other apps"
run > "$T/run.log" 2>&1; RC=$?
check "exits 0"                                          test $RC -eq 0
RS=$(grep -F -- "$S/runsync/ " "$LOG" || true)
check "rsync called for the runsync folder"              test -n "$RS"
check "destination is runsync/ on the NAS"               grep -qF "u@nas.invalid:/volume1/test/nuc/runsync/" <<<"$RS"
check "uses --delete (a mirror)"                         grep -qF -- "--delete" <<<"$RS"
check "keeps replaced files in _versions"                grep -qF -- "/_versions/" <<<"$RS"
check "does NOT exclude .env (copied like other apps)"   bash -c "! grep -qF -- '--exclude=.env' <<<\"\$1\"" _ "$RS"
check "skips .git/ and node_modules/ like other apps"    bash -c "grep -qF -- '--exclude=.git/' <<<\"\$1\" && grep -qF -- '--exclude=node_modules/' <<<\"\$1\"" _ "$RS"
check "never copies a postgres data directory"           grep -qF -- "--exclude=postgres-data/" <<<"$RS"
check "one runsync call only (no separate backups call)" test "$(grep -cF -- "$S/runsync" "$LOG")" -eq 1

echo "== other targets still synced"
for d in shared/backups shared/mood-images shared/garmin-tokens shared/logs sleepwell audio-scrobbler-app UK-Expense-Tracker; do
  check "still syncs $d"                                 grep -qF "$S/$d/" "$LOG"
done

echo "== missing runsync is reported, others still run"
rm -rf "$S/runsync"; : > "$LOG"
run > "$T/run2.log" 2>&1; RC=$?
check "exits non-zero"                                   test $RC -ne 0
check "failure names runsync"                            has "$T/run2.log" "FAILED runsync: source directory missing"
check "other targets still synced after the failure"     grep -qF "$S/UK-Expense-Tracker/" "$LOG"

summary
