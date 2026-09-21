#!/usr/bin/env bash
# Fixture tests: sleepwell scripts/sync_backups_to_google.sh
#
# Hermetic: every external tool the script talks to (rclone, curl, ssh, rsync, crontab,
# verify script...) is replaced by a stub on PATH, and all state lives in a temp dir that
# is removed on exit. Nothing here touches a real remote, crontab or backup directory.
# Needs: bash, GNU coreutils/find/date (Linux), flock.
# Run:   scripts/tests/test_sync_backups_to_google.sh
set -uo pipefail
SP=$(cd "$(dirname "$0")" && pwd); . "$SP/lib.sh"
SCRIPT="$(cd "$SP/.." && pwd)/sync_backups_to_google.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home/.config/rclone"; : > "$T/home/.config/rclone/rclone.conf"

# stubs: rclone logs its args (fails for the subcommand named in STUB_RCLONE_FAIL); curl logs the URL
cat > "$T/bin/rclone" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG_DIR/rclone.log"
[[ "${STUB_RCLONE_FAIL:-}" == "$1" ]] && { echo "stub rclone: $1 failing" >&2; exit 1; }
exit 0
EOF
cat > "$T/bin/curl" <<'EOF'
#!/usr/bin/env bash
echo "${@: -1}" >> "$STUB_LOG_DIR/pings.log"
exit 0
EOF
chmod +x "$T/bin/rclone" "$T/bin/curl"
export PATH="$T/bin:$PATH" STUB_LOG_DIR="$T"

fresh_fixture() {   # everything present and fresh
    rm -rf "$T/b"; mkdir -p "$T/b/mood-images" "$T/b/host-config"
    touch -d '2 hours ago'  "$T/b/sleepdb_20260921T000000Z.dump"
    touch -d '2 hours ago'  "$T/b/mood-images/mood_images_20260921T000000Z.tar.gz"
    touch -d '2 hours ago'  "$T/b/expense_tracker_data_20260921_030000.tar.gz"
    touch -d '2 hours ago'  "$T/b/host-config/host_config_20260921T000000Z.tar.gz"
}
run() {   # run [VAR=val ...]  -> sets RC, leaves $T/out.txt, $T/pings.log, $T/rclone.log
    rm -f "$T/pings.log" "$T/rclone.log" "$T/out.txt"; : > "$T/pings.log"
    env HOME="$T/home" BACKUP_DIR="$T/b" GOOGLE_ENV_FILE="$T/none.env" RCLONE_REMOTE=x:y "$@" "$SCRIPT" > "$T/out.txt" 2>&1
    RC=$?
}

echo "== healthy run"
fresh_fixture; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc
check "exits 0"                                   test $RC -eq 0
check "exactly one ping, the success URL"         bash -c "[[ \$(cat '$T/pings.log') == 'https://hc.example/abc' ]]"
check "rclone copy ran with excludes"             has "$T/rclone.log" "copy $T/b x:y"
check "delete has no --rmdirs (the old bug)"      bash -c "grep '^delete ' '$T/rclone.log' | grep -qv -- '--rmdirs'"
check "delete keeps --min-age 90d"                bash -c "grep '^delete ' '$T/rclone.log' | grep -q -- '--min-age 90d'"
check "empty dirs removed via separate rmdirs --leave-root" bash -c "grep '^rmdirs ' '$T/rclone.log' | grep -q -- '--leave-root'"
check "logs OK for all four producers"            bash -c "[[ \$(grep -c '^\[sync_backups_to_google\] OK:' '$T/out.txt') -eq 4 ]]"

echo "== stale / missing producers -> /fail + non-zero"
fresh_fixture; touch -d '20 hours ago' "$T/b/mood-images/mood_images_20260921T000000Z.tar.gz"; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc
check "mood archive 20h old (limit 13) -> exit 1"  test $RC -eq 1
check "-> pings /fail, not success"               bash -c "[[ \$(cat '$T/pings.log') == 'https://hc.example/abc/fail' ]]"
check "-> names the stale producer"               has "$T/out.txt" "mood image archive"
fresh_fixture; rm "$T/b/expense_tracker_data_20260921_030000.tar.gz"; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc
check "no expense archive at all -> fails closed" test $RC -eq 1
fresh_fixture; touch -d '30 hours ago' "$T/b/sleepdb_20260921T000000Z.dump"; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc
check "DB dump 30h old (limit 26) -> exit 1"      test $RC -eq 1
fresh_fixture; rm -rf "$T/b/host-config"; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc
check "host-config snapshot missing -> exit 1"    test $RC -eq 1
fresh_fixture; touch -d '25 hours ago' "$T/b/sleepdb_20260921T000000Z.dump"; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc
check "DB dump 25h old (within 26h) -> still ok"  test $RC -eq 0
fresh_fixture; touch -d '2 hours ago' "$T/b/sleepdb_old.dump"; touch -d '40 hours ago' "$T/b/sleepdb_20260919T000000Z.dump"; run
check "newest of several is what counts"          test $RC -eq 0

echo "== rclone failures"
fresh_fixture; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc STUB_RCLONE_FAIL=copy
check "failed upload -> non-zero"                 test $RC -ne 0
check "failed upload -> exactly one /fail ping"   bash -c "[[ \$(cat '$T/pings.log') == 'https://hc.example/abc/fail' ]]"
fresh_fixture; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc STUB_RCLONE_FAIL=lsd
check "unreachable remote (lsd) -> /fail once"    bash -c "[[ $RC -ne 0 && \$(cat '$T/pings.log') == 'https://hc.example/abc/fail' ]]"
fresh_fixture; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc STUB_RCLONE_FAIL=delete
check "prune failure is only a warning -> exit 0" test $RC -eq 0
check "prune failure still sends success ping"    bash -c "[[ \$(cat '$T/pings.log') == 'https://hc.example/abc' ]]"
fresh_fixture; run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc STUB_RCLONE_FAIL=rmdirs
check "rmdirs failure is only a warning"          test $RC -eq 0

echo "== config precedence: caller env > env file > default"
fresh_fixture; touch -d '2 hours ago' "$T/b/mood-images/mood_images_20260921T000000Z.tar.gz"
printf 'GOOGLE_HEALTHCHECK_URL=https://file.example/F\nFRESH_MOOD_HOURS=100\n' > "$T/g.env"
run GOOGLE_ENV_FILE="$T/g.env"
check "env file alone supplies the URL"           bash -c "[[ \$(cat '$T/pings.log') == 'https://file.example/F' ]]"
run GOOGLE_ENV_FILE="$T/g.env" GOOGLE_HEALTHCHECK_URL=https://caller.example/C
check "caller URL beats the env file"             bash -c "[[ \$(cat '$T/pings.log') == 'https://caller.example/C' ]]"
run GOOGLE_ENV_FILE="$T/g.env" FRESH_MOOD_HOURS=1
check "caller threshold beats the file's (2h > 1h -> stale)" test $RC -eq 1
run GOOGLE_ENV_FILE="$T/g.env"
check "file threshold applies when caller silent" test $RC -eq 0

echo "== knobs and validation"
fresh_fixture; rm "$T/b/expense_tracker_data_20260921_030000.tar.gz"; run FRESH_EXPENSE_HOURS=0
check "FRESH_EXPENSE_HOURS=0 disables that check" test $RC -eq 0
fresh_fixture; run FRESH_DB_HOURS=08
check "leading-zero value ('08') is not read as octal" test $RC -eq 0
fresh_fixture; run FRESH_DB_HOURS=abc GOOGLE_HEALTHCHECK_URL=https://hc.example/abc
check "non-numeric threshold rejected + /fail"    bash -c "[[ $RC -eq 1 && \$(cat '$T/pings.log') == 'https://hc.example/abc/fail' ]]"
fresh_fixture; run
check "no URL configured -> no pings, still works" bash -c "[[ $RC -eq 0 && ! -s '$T/pings.log' ]]"
fresh_fixture; touch -d '20 hours ago' "$T/b/mood-images/mood_images_20260921T000000Z.tar.gz"; run
check "no URL + stale -> still exits 1 (cron log shows it)" test $RC -eq 1

echo "== lock contention"
fresh_fixture; mkdir -p "$T/b"; ( exec 9>"$T/b/.google_sync.lock"; flock 9; sleep 4 ) & sleep 0.5
run GOOGLE_HEALTHCHECK_URL=https://hc.example/abc
check "second concurrent run refuses (exit 1)"    test $RC -eq 1
check "-> mentions already running"               has "$T/out.txt" "already running"
wait

summary
