#!/usr/bin/env bash
# Fixture tests: the database backup schedule and retention
#   scripts/setup_db_backup_cron.sh, scripts/run_db_backup_rotation.sh, scripts/db_cleanup.sh,
#   scripts/db_backup.sh
#
# Hermetic: crontab and docker are replaced by stubs on PATH, and all state lives in a temp dir
# removed on exit. Nothing here touches a real crontab, container or backup directory.
# Needs: bash, GNU coreutils (touch -d, find -mmin), flock, gzip.
# Run:   scripts/tests/test_db_backup_schedule.sh
set -uo pipefail
SP=$(cd "$(dirname "$0")" && pwd); . "$SP/lib.sh"
SD="$(cd "$SP/.." && pwd)"
T=$(mktemp -d) || exit 1
[[ -n "$T" && -d "$T" ]] || { echo "mktemp failed; refusing to run (stubs would be written to the real /bin)" >&2; exit 1; }
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"

# ── stub crontab: -l prints the file (or fails when there is none), otherwise installs a file ──
CT=$T/crontab.txt
cat > "$T/bin/crontab" <<EOF
#!/usr/bin/env bash
if [[ "\${1:-}" == "-l" ]]; then [[ -f "$CT" ]] || { echo "no crontab for test" >&2; exit 1; }; cat "$CT"; else cp "\$1" "$CT"; fi
EOF
chmod +x "$T/bin/crontab"
export PATH="$T/bin:$PATH"
# If mktemp failed, PATH would fall through to the REAL crontab and the installer would rewrite it.
[[ -n "$T" && -d "$T" && "$(command -v crontab)" == "$T/bin/crontab" ]] || { echo "crontab stub is not in effect; refusing to run" >&2; exit 1; }

install_cron() { env -u SCHEDULE -u MAX_BACKUPS BACKUP_DIR="$T/bk" "$@" "$SD/setup_db_backup_cron.sh" >/dev/null 2>&1; }

# ── a copy of scripts/ with a stub db_backup.sh, so the real rotation + cleanup can run ──
fake_repo() {   # fake_repo <dir>
    rm -rf "$1"; mkdir -p "$1/scripts"
    cp "$SD/run_db_backup_rotation.sh" "$SD/db_cleanup.sh" "$1/scripts/"
    cat > "$1/scripts/db_backup.sh" <<'EOF'
#!/usr/bin/env bash
[[ -n "${STUB_BACKUP_FAIL:-}" ]] && { echo "stub db_backup failing" >&2; exit 1; }
exit 0
EOF
    chmod +x "$1/scripts/"*.sh
}
make_snapshots() {   # make_snapshots <dir> <count> <with-sql: yes|no> : oldest first, one per day
    local dir=$1 n=$2 sql=$3 i ts
    rm -rf "$dir"; mkdir -p "$dir"
    for ((i = 1; i <= n; i++)); do
        ts=$(printf '202610%02dT000000Z' "$i")
        : > "$dir/sleepdb_$ts.dump"; touch -d "$((n + 10 - i)) days ago" "$dir/sleepdb_$ts.dump"
        if [[ "$sql" == yes ]]; then : > "$dir/sleepdb_$ts.sql.gz"; touch -d "$((n + 10 - i)) days ago" "$dir/sleepdb_$ts.sql.gz"; fi
    done
}
n_dumps() { ls -1 "$1"/*.dump 2>/dev/null | wc -l; }
n_sql()   { ls -1 "$1"/*.sql.gz 2>/dev/null | wc -l; }
rotate() {   # rotate <repo> <backupdir> [VAR=val ...] -> sets RC
    local repo=$1 dir=$2; shift 2
    # GARMIN_TOKENS_DIR defaults to a path that does not exist, so a machine that really has
    # /srv/shared/garmin-tokens never has its tokens read by these tests.
    env -u MAX_BACKUPS -u HEALTHCHECK_URL GARMIN_TOKENS_DIR="$T/no-garmin-tokens" BACKUP_DIR="$dir" "$@" "$repo/scripts/run_db_backup_rotation.sh" > "$T/rot.out" 2>&1
    RC=$?
}

echo "== cron installer defaults"
rm -f "$CT"; install_cron
LINE="0 */6 * * * MAX_BACKUPS=28 BACKUP_DIR=$T/bk $SD/run_db_backup_rotation.sh >> $T/bk/db_backup_cron.log 2>&1"
check "default line is 6-hourly, keeps 28 snapshots"  has "$CT" "$LINE"

printf '%s\n%s\n' "0 */12 * * * MAX_BACKUPS=14 BACKUP_DIR=$T/bk $SD/run_db_backup_rotation.sh >> $T/bk/db_backup_cron.log 2>&1" "5 5 * * * /usr/bin/true" > "$CT"
install_cron
check "old 12-hourly line replaced by the 6-hourly line" has "$CT" "$LINE"
check "exactly one rotation line remains"             count "$CT" "run_db_backup_rotation.sh" 1
check "old 12-hourly schedule is gone"                hasnt "$CT" "0 */12 * * *"
check "unrelated job preserved"                       has "$CT" "/usr/bin/true"
cp "$CT" "$T/c1.txt"; install_cron
check "re-running the installer changes nothing"      cmp -s "$CT" "$T/c1.txt"
printf '%s\n' "0 */12 * * * MAX_BACKUPS=14 BACKUP_DIR=$T/bk $SD/run_db_backup_rotation.sh >> $T/bk/db_backup_cron.log 2>&1" > "$CT"
install_cron
check "crontab holding ONLY the old rotation line is updated (installer must not abort)" has "$CT" "$LINE"
check "-> exactly one rotation line afterwards"       count "$CT" "run_db_backup_rotation.sh" 1
rm -f "$CT"; install_cron SCHEDULE='15 2 * * *' MAX_BACKUPS=5
check "SCHEDULE and MAX_BACKUPS overrides still work" has "$CT" "15 2 * * * MAX_BACKUPS=5 BACKUP_DIR=$T/bk"

echo "== rotation retention"
fake_repo "$T/fr"
make_snapshots "$T/b1" 31 yes; rotate "$T/fr" "$T/b1"
check "no MAX_BACKUPS: rotation exits 0"              test $RC -eq 0
check "no MAX_BACKUPS: keeps 28 dumps"                test "$(n_dumps "$T/b1")" -eq 28
check "no MAX_BACKUPS: keeps 28 sql.gz"               test "$(n_sql "$T/b1")" -eq 28
check "the 3 oldest snapshots are the ones removed"   bash -c "[[ ! -e '$T/b1/sleepdb_20261001T000000Z.dump' && ! -e '$T/b1/sleepdb_20261003T000000Z.sql.gz' && -e '$T/b1/sleepdb_20261004T000000Z.dump' && -e '$T/b1/sleepdb_20261031T000000Z.dump' ]]"
make_snapshots "$T/b2" 31 yes; rotate "$T/fr" "$T/b2" MAX_BACKUPS=5
check "MAX_BACKUPS=5 is honoured"                     test "$(n_dumps "$T/b2")" -eq 5
make_snapshots "$T/b3" 30 no; rotate "$T/fr" "$T/b3"
check ".dump-only snapshots are counted: 30 -> 28"    test "$(n_dumps "$T/b3")" -eq 28
make_snapshots "$T/b4" 31 yes; rotate "$T/fr" "$T/b4" STUB_BACKUP_FAIL=1
check "failing dump -> rotation exits non-zero"       test $RC -ne 0
check "failing dump -> nothing pruned"                bash -c "[[ \$(ls -1 '$T/b4'/*.dump | wc -l) -eq 31 && \$(ls -1 '$T/b4'/*.sql.gz | wc -l) -eq 31 ]]"

echo "== db_cleanup.sh run by hand (default retention)"
make_snapshots "$T/c1d" 31 yes
env -u MAX_BACKUPS "$SD/db_cleanup.sh" --backup-dir "$T/c1d" > "$T/clean.out" 2>&1
check "bare db_cleanup.sh keeps 28 snapshots, not 4"  test "$(n_dumps "$T/c1d")" -eq 28
make_snapshots "$T/c2d" 31 yes
"$SD/db_cleanup.sh" --backup-dir "$T/c2d" --max-backups 10 > "$T/clean.out" 2>&1
check "--max-backups 10 still honoured"               test "$(n_dumps "$T/c2d")" -eq 10

echo "== rotation reads only the paths it is told about"
mkdir -p "$T/gt"; echo '{"token":"fake"}' > "$T/gt/tokens.json"
make_snapshots "$T/r1" 3 yes; rotate "$T/fr" "$T/r1" GARMIN_TOKENS_DIR="$T/gt"
check "GARMIN_TOKENS_DIR override is used: a tarball is written" bash -c "ls '$T/r1'/garmin_tokens_*.tar.gz >/dev/null 2>&1"
make_snapshots "$T/r2" 3 yes; rotate "$T/fr" "$T/r2"
check "no tokens dir -> no garmin tarball and no error" bash -c "[[ \$(ls -1 '$T/r2'/garmin_tokens_*.tar.gz 2>/dev/null | wc -l) -eq 0 ]]"
make_snapshots "$T/r3" 3 yes; mkdir -p "$T/r3/mood-images"; echo x > "$T/r3/mood-images/mood_images_20261101T000000Z.tar.gz"
rotate "$T/fr" "$T/r3"
check "mood-image archives under BACKUP_DIR are in the manifest" bash -c "grep -q 'mood-images/mood_images_20261101T000000Z.tar.gz' '$T/r3'/manifest_*.sha256"

# ── db_backup.sh with a stub docker: custom-format dump every run, plain SQL gated ──
cat > "$T/bin/docker" <<'EOF'
#!/usr/bin/env bash
# stub docker: `inspect` reports running; `exec ... pg_dump -Fc` writes fixed bytes; the plain-SQL
# pg_dump writes text, or fails when STUB_DUMP_FAIL is set.
case "$1" in
    info) exit 0 ;;
    inspect) echo running; exit 0 ;;
    exec)
        if [[ "$*" == *" -Fc"* ]]; then printf 'PGDMP-fake-custom-dump'; exit 0; fi
        [[ -n "${STUB_DUMP_FAIL:-}" ]] && { echo "stub pg_dump failing" >&2; exit 1; }
        printf 'SELECT 1;\n'; exit 0 ;;
esac
exit 0
EOF
chmod +x "$T/bin/docker"
printf 'POSTGRES_USER=sleepuser\nPOSTGRES_PASSWORD=x\nPOSTGRES_DB=sleepdb\n' > "$T/env"
backup() {   # backup <outdir> [VAR=val ...] -> sets RC, output in $T/bk.out
    local out=$1; shift
    env -u PLAIN_SQL RUNTIME=docker OUTPUT_DIR="$out" "$@" "$SD/db_backup.sh" "$T/env" > "$T/bk.out" 2>&1
    RC=$?
}
old_sql() {  # old_sql <dir> <touch -d age> : an existing plain-SQL copy of that age
    mkdir -p "$1"; : > "$1/sleepdb_20260101T000000Z.sql.gz"; touch -d "$2" "$1/sleepdb_20260101T000000Z.sql.gz"
}

echo "== plain-SQL copy: once a day (default), custom dump every run"
backup "$T/p1"
check "daily, none present: exits 0"                  test $RC -eq 0
check "daily, none present: .dump written"            test "$(n_dumps "$T/p1")" -eq 1
check "daily, none present: .sql.gz written"          test "$(n_sql "$T/p1")" -eq 1
check "the .dump holds the dump bytes"                bash -c "grep -q PGDMP '$T/p1'/*.dump"
old_sql "$T/p2" "2 hours ago"; backup "$T/p2"
check "daily, 2h-old copy present: exits 0"           test $RC -eq 0
check "daily, 2h-old copy present: new .dump still written" test "$(n_dumps "$T/p2")" -eq 1
check "daily, 2h-old copy present: no new .sql.gz"    test "$(n_sql "$T/p2")" -eq 1
check "-> logs why the plain copy was skipped"        has "$T/bk.out" "Skipping plain-SQL"
old_sql "$T/p3" "25 hours ago"; backup "$T/p3"
check "daily, 25h-old copy present: new .sql.gz written" test "$(n_sql "$T/p3")" -eq 2
old_sql "$T/p4" "2 hours ago"; backup "$T/p4" PLAIN_SQL=always
check "always: .sql.gz written despite a fresh one"   test "$(n_sql "$T/p4")" -eq 2
backup "$T/p5" PLAIN_SQL=never
check "never: .dump written"                          test "$(n_dumps "$T/p5")" -eq 1
check "never: no .sql.gz"                             test "$(n_sql "$T/p5")" -eq 0
backup "$T/p6" PLAIN_SQL=weekly
check "invalid PLAIN_SQL -> exit 1"                   test $RC -eq 1
check "-> message names PLAIN_SQL"                    has "$T/bk.out" "PLAIN_SQL"
check "-> nothing was dumped"                         test "$(n_dumps "$T/p6")" -eq 0
backup "$T/p7" STUB_DUMP_FAIL=1
check "plain-SQL pg_dump failing -> exit non-zero"    test $RC -ne 0
check "-> the custom .dump is kept, non-empty"        bash -c "[[ \$(ls -1 '$T/p7'/*.dump | wc -l) -eq 1 && -s \$(ls -1 '$T/p7'/*.dump) ]]"
check "-> no .sql.gz left behind"                     test "$(n_sql "$T/p7")" -eq 0
check "-> no .tmp file left behind"                   bash -c "! find '$T/p7' -name '*.tmp' | grep -q ."

summary
