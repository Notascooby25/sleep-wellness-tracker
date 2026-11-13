#!/usr/bin/env bash
# Fixture tests: sleepwell scripts/test_restore_dump.sh (the restore drill)
#
# Hermetic: `docker` is replaced by a stub on PATH, and all state lives in a temp dir that
# is removed on exit. Nothing here touches real Docker, a real database or a real backup dir.
# Needs: bash, GNU coreutils (touch -d).
# Run:   scripts/tests/test_restore_dump.sh
set -uo pipefail
SP=$(cd "$(dirname "$0")" && pwd); . "$SP/lib.sh"
SCRIPT="$(cd "$SP/.." && pwd)/test_restore_dump.sh"
T=$(mktemp -d) || exit 1
[[ -n "$T" && -d "$T" ]] || { echo "mktemp failed; refusing to run (stubs would be written to the real /bin)" >&2; exit 1; }
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"

# Stub docker. Every call is logged ("<subcommand> <args...>") to $T/docker.log.
# Behaviour is driven by env vars:
#   STUB_RESTORE_RC       exit code of the restoring `pg_restore` (default 0)
#   STUB_MOODS/ACTIVITIES counts the RESTORED database returns (default 1862 / 144)
#   STUB_TOC_TABLES       TABLE entries listed by `pg_restore -l` (default 12)
#   STUB_DB_TABLES        base tables the restored database reports (default 12)
#   STUB_LIVE             "absent" (live container not running) or "moods=<n>,activities=<n>"
#   STUB_LIVE_VERSION     text printed by `postgres --version` in the live container; empty = unreadable
cat > "$T/bin/docker" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG_DIR/docker.log"
A="$*"
live_count() {   # live_count <moods|activities> -> value from STUB_LIVE
    local v; v=$(tr ',' '\n' <<<"${STUB_LIVE:-}" | sed -n "s/^$1=//p")
    echo "${v:-0}"
}
case "$1" in
    inspect) [[ "${STUB_LIVE:-absent}" == "absent" ]] && exit 1; echo running; exit 0 ;;
    run)     echo "stubcid"; exit 0 ;;
    stop|cp) exit 0 ;;
    exec)
        case "$A" in
            *"postgres --version"*)
                [[ "${STUB_LIVE:-absent}" == "absent" || -z "${STUB_LIVE_VERSION:-}" ]] && exit 1
                echo "$STUB_LIVE_VERSION"; exit 0 ;;
            *pg_isready*) exit 0 ;;
            *"pg_restore -l"*)
                if [[ "${STUB_TOC_TABLES:-12}" -eq 0 ]]; then   # not a Postgres archive at all
                    echo "pg_restore: error: input file does not appear to be a valid archive" >&2; exit 1
                fi
                for ((i = 1; i <= ${STUB_TOC_TABLES:-12}; i++)); do
                    echo "; $i; 1259 16$i TABLE public t$i sleepuser"
                    echo "; $i; 0 16$i TABLE DATA public t$i sleepuser"
                done
                echo "; 99; 1259 17000 SEQUENCE public some_seq sleepuser"
                exit 0 ;;
            *pg_restore*) exit "${STUB_RESTORE_RC:-0}" ;;
            *information_schema*) echo "${STUB_DB_TABLES:-12}"; exit 0 ;;
            *moods*)
                if [[ "$A" == *stubcid* ]]; then echo "${STUB_MOODS:-1862}"; else live_count moods; fi; exit 0 ;;
            *activities*)
                if [[ "$A" == *stubcid* ]]; then echo "${STUB_ACTIVITIES:-144}"; else live_count activities; fi; exit 0 ;;
        esac
        exit 0 ;;
esac
exit 0
EOF
chmod +x "$T/bin/docker"
export PATH="$T/bin:$PATH" STUB_LOG_DIR="$T"

fresh_fixture() {   # one recent, non-empty dump
    rm -rf "$T/b"; mkdir -p "$T/b"
    echo "PGDMP-fake-archive" > "$T/b/sleepdb_20261113T120001Z.dump"
    touch -d '2 hours ago' "$T/b/sleepdb_20261113T120001Z.dump"
}
run() {   # run [VAR=val ...]  -> sets RC, leaves $T/out.txt and $T/docker.log
    rm -f "$T/docker.log" "$T/out.txt"; : > "$T/docker.log"
    env -u DRILL_MAX_AGE_HOURS BACKUP_DIR="$T/b" \
        STUB_LIVE="moods=1862,activities=144" \
        STUB_LIVE_VERSION="postgres (PostgreSQL) 15.19 (Debian 15.19-1.pgdg13+2)" \
        "$@" "$SCRIPT" > "$T/out.txt" 2>&1
    RC=$?
}

echo "== healthy run"
fresh_fixture; run
check "exits 0"                                    test $RC -eq 0
check "reports DR Test Passed"                     has "$T/out.txt" "DR Test Passed"
check "ephemeral container was stopped"            bash -c "grep -q '^stop stubcid' '$T/docker.log'"

echo "== restore errors must fail the drill"
fresh_fixture; run STUB_RESTORE_RC=1
check "pg_restore exit 1 (counts still look fine) -> exit 1" test $RC -eq 1
check "-> output names the restore failure"        has "$T/out.txt" "pg_restore failed"
check "-> never reports success"                   hasnt "$T/out.txt" "DR Test Passed"
check "-> container still cleaned up"              bash -c "grep -q '^stop stubcid' '$T/docker.log'"

echo "== how the restore is invoked (real-Postgres pitfalls the stub cannot show)"
fresh_fixture; run
check "restore uses --exit-on-error"               bash -c "grep -E '^exec .*pg_restore .*-d sleepdb' '$T/docker.log' | grep -q -- '--exit-on-error'"
check "restore uses --no-owner (live role may differ)" bash -c "grep -E '^exec .*pg_restore .*-d sleepdb' '$T/docker.log' | grep -q -- '--no-owner'"
check "restore uses --no-privileges"               bash -c "grep -E '^exec .*pg_restore .*-d sleepdb' '$T/docker.log' | grep -q -- '--no-privileges'"
check "restore targets the throwaway container"    bash -c "grep -E '^exec .*pg_restore .*-d sleepdb' '$T/docker.log' | grep -q 'stubcid'"
check "readiness probed over TCP, not the init-time socket" bash -c "grep '^exec .*pg_isready' '$T/docker.log' | grep -q -- '-h 127.0.0.1'"

echo "== dump file problems"
fresh_fixture; rm "$T/b"/*.dump; run
check "no dump -> exit 1"                          test $RC -eq 1
check "no dump -> no container started"            bash -c "! grep -q '^run ' '$T/docker.log'"
fresh_fixture; : > "$T/b/sleepdb_20261113T120001Z.dump"; run
check "empty dump -> exit 1"                       test $RC -eq 1
check "empty dump -> no container started"         bash -c "! grep -q '^run ' '$T/docker.log'"
fresh_fixture; touch -d '20 hours ago' "$T/b/sleepdb_20261113T120001Z.dump"; run
check "dump 20h old (default limit 8) -> exit 1"   test $RC -eq 1
check "-> message says the dump is old"            has "$T/out.txt" "old"
check "-> no container started"                    bash -c "! grep -q '^run ' '$T/docker.log'"
fresh_fixture; touch -d '2 hours ago' "$T/b/sleepdb_20261113T120001Z.dump"; run
check "dump 2h old (default limit 8) -> exit 0"    test $RC -eq 0
fresh_fixture; touch -d '7 hours ago' "$T/b/sleepdb_20261113T120001Z.dump"; run
check "dump 7h old (inside the default 8h) -> exit 0" test $RC -eq 0
fresh_fixture; touch -d '9 hours ago' "$T/b/sleepdb_20261113T120001Z.dump"; run
check "dump 9h old (outside the default 8h) -> exit 1" test $RC -eq 1
fresh_fixture; touch -d '9 hours ago' "$T/b/sleepdb_20261113T120001Z.dump"; run DRILL_MAX_AGE_HOURS=14
check "DRILL_MAX_AGE_HOURS=14 override lets a 9h dump pass" test $RC -eq 0

echo "== sanity checks on the restored database"
fresh_fixture; run STUB_MOODS=0
check "zero moods -> exit 1"                       test $RC -eq 1
fresh_fixture; run STUB_ACTIVITIES=0
check "zero activities -> exit 1"                  test $RC -eq 1
fresh_fixture; run STUB_TOC_TABLES=12 STUB_DB_TABLES=11
check "restored 11 tables vs 12 in dump -> exit 1" test $RC -eq 1
check "-> message states both counts"              has "$T/out.txt" "restored 11 tables but the dump lists 12 tables"
fresh_fixture; run STUB_TOC_TABLES=0
check "file that is not a pg archive (no tables listed) -> exit 1" test $RC -eq 1
check "-> message says no tables"                  has "$T/out.txt" "lists no tables"
check "-> never reports success"                   hasnt "$T/out.txt" "DR Test Passed"
check "-> restore was never attempted"             bash -c "! grep -E '^exec .*pg_restore .*-d sleepdb' '$T/docker.log'"
fresh_fixture; run STUB_TOC_TABLES=12 STUB_DB_TABLES=12
check "12 vs 12 tables -> exit 0"                  test $RC -eq 0

echo "== live comparison"
fresh_fixture; run STUB_LIVE=absent
check "live container absent -> still exit 0"      test $RC -eq 0
check "-> says it skipped the live comparison"     has "$T/out.txt" "skipping live comparison"
fresh_fixture; run STUB_LIVE="moods=1000,activities=100" STUB_MOODS=800
check "restored moods 80% of live (min 90%) -> exit 1" test $RC -eq 1
check "-> message mentions live"                   has "$T/out.txt" "live"
fresh_fixture; run STUB_LIVE="moods=1000,activities=100" STUB_MOODS=950 STUB_ACTIVITIES=100
check "restored moods 95% of live -> exit 0"       test $RC -eq 0
fresh_fixture; run STUB_LIVE="moods=1000,activities=100" STUB_MOODS=800 DRILL_MIN_LIVE_FRACTION=0.5
check "fraction override 0.5 lets 80% pass"        test $RC -eq 0

echo "== image selection"
fresh_fixture; run STUB_LIVE_VERSION="postgres (PostgreSQL) 16.2"
check "live major 16 -> postgres:16 container"     bash -c "grep '^run ' '$T/docker.log' | grep -q 'postgres:16'"
fresh_fixture; run PG_IMAGE=postgres:14-alpine
check "PG_IMAGE override wins"                     bash -c "grep '^run ' '$T/docker.log' | grep -q 'postgres:14-alpine'"
fresh_fixture; run STUB_LIVE_VERSION=""
check "live version unreadable -> postgres:15"     bash -c "grep '^run ' '$T/docker.log' | grep -q 'postgres:15'"

echo "== the live container is only ever read"
fresh_fixture; run
check "no stop/rm/restart/cp aimed at live"        bash -c "! grep -E '^(stop|rm|restart|cp|kill) .*sleep_db' '$T/docker.log'"
check "no write-type command executed in live"     bash -c "! grep -E '^exec .*sleep_db.*(pg_restore|dropdb|createdb|DROP|INSERT|UPDATE|DELETE|TRUNCATE)' '$T/docker.log'"

summary
