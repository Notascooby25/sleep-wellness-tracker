#!/usr/bin/env bash
# Fixture test: scripts/push_srv_to_synology.sh mirrors /srv/runsync/backups and nothing else of runsync.
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

echo "== runsync/backups is mirrored"
run > "$T/run.log" 2>&1; RC=$?
check "exits 0"                                          test $RC -eq 0
RS=$(grep -F "$S/runsync/backups/" "$LOG" || true)
check "rsync called for runsync/backups"                 test -n "$RS"
check "destination is runsync/backups on the NAS"        grep -qF "u@nas.invalid:/volume1/test/nuc/runsync/backups/" <<<"$RS"
check "uses --delete (a mirror)"                         grep -qF -- "--delete" <<<"$RS"
check "keeps replaced files in _versions"                grep -qF -- "/_versions/" <<<"$RS"
check "excludes .env*"                                   grep -qF -- "--exclude=.env*" <<<"$RS"
echo "$RS" > "$T/rs.txt"

echo "== the rest of /srv/runsync is NOT copied"
check "no rsync from the runsync folder itself"          bash -c "! grep -qF -- '$S/runsync/ ' '$LOG'"
check "no rsync from runsync/other"                      bash -c "! grep -qF -- 'runsync/other' '$LOG'"
check "no rsync destination of runsync/ alone"           bash -c "! grep -qE ':/volume1/test/nuc/runsync/\$' '$LOG'"

echo "== other targets still synced"
for d in shared/backups shared/mood-images shared/garmin-tokens shared/logs sleepwell audio-scrobbler-app UK-Expense-Tracker; do
  check "still syncs $d"                                 grep -qF "$S/$d/" "$LOG"
done

echo "== missing runsync/backups is reported, others still run"
rm -rf "$S/runsync/backups"; : > "$LOG"
run > "$T/run2.log" 2>&1; RC=$?
check "exits non-zero"                                   test $RC -ne 0
check "failure names runsync/backups"                    has "$T/run2.log" "FAILED runsync/backups: source directory missing"
check "other targets still synced after the failure"     grep -qF "$S/UK-Expense-Tracker/" "$LOG"

summary
