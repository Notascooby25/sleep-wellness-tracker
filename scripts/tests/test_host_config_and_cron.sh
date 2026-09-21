#!/usr/bin/env bash
# Fixture tests: sleepwell scripts/backup_host_config.sh + scripts/setup_offsite_backup_cron.sh
#
# Hermetic: every external tool the script talks to (rclone, curl, ssh, rsync, crontab,
# verify script...) is replaced by a stub on PATH, and all state lives in a temp dir that
# is removed on exit. Nothing here touches a real remote, crontab or backup directory.
# Needs: bash, GNU coreutils/find/date (Linux), git. It only *reads* the host's real crontab/docker/tailscale state (to capture it); it writes nothing outside its temp dir.
# Run:   scripts/tests/test_host_config_and_cron.sh
set -uo pipefail
SP=$(cd "$(dirname "$0")" && pwd); . "$SP/lib.sh"
SD="$(cd "$SP/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# ---- fake host: home with secrets, /srv with a git checkout that has a token in its remote ----
H=$T/home; S=$T/srv; O=$T/out
mkdir -p "$H/.config/rclone" "$H/.ssh" "$H/.docker" "$H/.config/systemd/user" "$S/shared" "$S/appA"
echo 'password = SENTINEL_RCLONE_PASSWORD_12345' > "$H/.config/rclone/rclone.conf"
echo 'password2 = SENTINEL_RCLONE_PASSWORD2_54321' >> "$H/.config/rclone/rclone.conf"
echo '-----BEGIN OPENSSH PRIVATE KEY----- SENTINEL_SSH_KEY_67890' > "$H/.ssh/id_ed25519_synology"
echo '{"auths":{"ghcr.io":{"auth":"SENTINEL_DOCKER_AUTH_abc"}}}' > "$H/.docker/config.json"
printf 'NAS_USER=alice\nNAS_HOST=nas.lan\nNAS_PORT=8022\nNAS_TARGET=/volume1/Backups/nuc\nNAS_HEALTHCHECK_URL=https://hc-ping.com/SENTINEL-HC-NAS-1111\nSSH_KEY=/home/x/.ssh/k\n' > "$H/.config/nas-sync.env"
printf 'GOOGLE_HEALTHCHECK_URL=https://hc-ping.com/SENTINEL-HC-GOOGLE-2222\nFRESH_DB_HOURS=26\n' > "$H/.config/google-sync.env"
printf '[Service]\nExecStart=/bin/true\nEnvironment=API_TOKEN=SENTINEL_UNIT_TOKEN_999\n' > "$H/.config/systemd/user/x.service"
printf '[Timer]\nOnCalendar=daily\n' > "$H/.config/systemd/user/x.timer"
(cd "$S/appA" && git init -q && git config user.email t@t && git config user.name t \
  && echo one > f.txt && git add f.txt && git commit -qm init \
  && git remote add origin "https://SENTINEL_GIT_USER:SENTINEL_GIT_TOKEN@github.com/o/r.git" \
  && echo "local NUC-only edit password=SENTINEL_INLINE_PW" >> f.txt)
echo 'UUID=abc /mnt/nas cifs credentials=/root/.smb,password=SENTINEL_FSTAB_PW 0 0' > "$T/fstab"

run() { env -i HOME="$H" PATH="/usr/bin:/bin" OUT_DIR="$O" SRV_ROOT="$S" "$@" "$SD/backup_host_config.sh"; }

echo "== backup_host_config.sh (run under a cron-like empty environment)"
run > "$T/run.log" 2>&1; RC=$?
check "exits 0"                                    test $RC -eq 0
A=$(ls "$O"/host_config_*.tar.gz 2>/dev/null | head -1)
check "archive created"                            test -n "$A"
check "archive mode is 600"                        test "$(stat -c %a "$A")" = 600
check "output dir mode is 700"                     test "$(stat -c %a "$O")" = 700
check "no .tmp left behind"                        bash -c "! ls '$O'/*.tmp 2>/dev/null"
mkdir "$T/x"; tar -xzf "$A" -C "$T/x"
ALL=$(cd "$T/x" && find . -type f | sort)
echo "$ALL" > "$T/files.txt"
for want in ./crontab.txt ./README.txt ./system/versions.txt ./system/os-release.txt ./docker/ps.txt ./rclone/remote-names.txt \
            ./nas-sync.env.redacted ./google-sync.env.redacted ./git/appA.txt ./systemd-user/units/x.service ./systemd-user/units/x.timer; do
  check "contains $want"                           has "$T/files.txt" "$want"
done
# only meaningful where a systemd user session exists (skipped in containers/CI)
if systemctl --user list-timers >/dev/null 2>&1; then
  check "systemctl --user works without XDG_RUNTIME_DIR (cron-like env)" bash -c "! grep -q 'Failed to connect' '$T/x/systemd-user/list-timers.txt'"
else
  echo "  skip  systemctl --user check (no systemd user session here)"
fi

echo "== secrets must NOT be in the archive"
DUMP=$(cd "$T/x" && find . -type f -print0 | xargs -0 cat)
check "PRECONDITION: something was actually captured (else the absent-checks below are vacuous)" test "${#DUMP}" -gt 500
for s in SENTINEL_RCLONE_PASSWORD_12345 SENTINEL_RCLONE_PASSWORD2_54321 SENTINEL_SSH_KEY_67890 SENTINEL_DOCKER_AUTH_abc \
         SENTINEL-HC-NAS-1111 SENTINEL-HC-GOOGLE-2222 SENTINEL_UNIT_TOKEN_999 SENTINEL_GIT_USER SENTINEL_GIT_TOKEN SENTINEL_INLINE_PW; do
  check "absent: $s"                               bash -c "! grep -q '$s' <<<\"\$1\"" _ "$DUMP"
done
check "rclone.conf itself not captured"            bash -c "! grep -q 'rclone.conf' '$T/files.txt'"
check "SSH private key file not captured"          bash -c "! grep -q 'id_ed25519' '$T/files.txt'"
echo "== but the useful, non-secret facts ARE there"
check "NAS host kept (needed to rebuild)"          has "$T/x/nas-sync.env.redacted" "NAS_HOST=nas.lan"
check "NAS port kept"                              has "$T/x/nas-sync.env.redacted" "NAS_PORT=8022"
check "healthcheck URL key present but redacted"   has "$T/x/nas-sync.env.redacted" "NAS_HEALTHCHECK_URL=<redacted>"
check "google env threshold kept"                  has "$T/x/google-sync.env.redacted" "FRESH_DB_HOURS=26"
check "git: HEAD recorded"                         has "$T/x/git/appA.txt" "# HEAD"
check "git: NUC-only local edit captured (diff)"   has "$T/x/git/appA.txt" "local NUC-only edit"
check "git: remote host kept, credentials redacted" has "$T/x/git/appA.txt" "<redacted>@github.com/o/r.git"
check "unit file token value redacted"             has "$T/x/systemd-user/units/x.service" "API_TOKEN=<redacted>"

echo "== retention + validation"
for _ in 1 2 3 4; do sleep 1.1; run KEEP=2 >/dev/null 2>&1; done
check "KEEP=2 leaves exactly 2 snapshots"          test "$(ls "$O"/host_config_*.tar.gz | wc -l)" -eq 2
run KEEP=0 >/dev/null 2>&1;   check "KEEP=0 rejected"   test $? -ne 0
run KEEP=abc >/dev/null 2>&1; check "KEEP=abc rejected" test $? -ne 0
# a section that cannot be captured must not abort the run
run SRV_ROOT="$T/does-not-exist" >/dev/null 2>&1; check "missing SRV_ROOT -> still exits 0" test $? -eq 0

echo "== setup_offsite_backup_cron.sh (stub crontab)"
mkdir -p "$T/bin"; CT=$T/crontab.txt
cat > "$T/bin/crontab" <<EOF
#!/usr/bin/env bash
if [[ "\${1:-}" == "-l" ]]; then [[ -f "$CT" ]] || { echo "no crontab" >&2; exit 1; }; cat "$CT"; else cp "\$1" "$CT"; fi
EOF
chmod +x "$T/bin/crontab"
inst() { PATH="$T/bin:$PATH" BACKUP_DIR="$T/bk" "$SD/setup_offsite_backup_cron.sh" >/dev/null 2>&1; }
managed() { grep -c -E "push_srv_to_synology|sync_backups_to_google|verify_latest_manifest|backup_host_config" "$CT"; }

rm -f "$CT"; inst
check "empty crontab: 4 managed jobs installed"    test "$(managed)" -eq 4
check "host-config job scheduled 04:10 daily"      bash -c "grep -q '^10 4 \* \* \* .*backup_host_config.sh' '$CT'"
check "host-config log goes next to the others"    has "$CT" "host_config_cron.log"

cat > "$CT" <<EOF
0 */12 * * * MAX_BACKUPS=14 /srv/sleepwell/scripts/run_db_backup_rotation.sh >> /x.log 2>&1
20 0,12 * * * /usr/bin/rclone copy /srv/shared/backups gdrive-crypt:backups/sleep-wellness >> /r.log 2>&1
30 */6 * * * /home/andyl/sleep-wellness-tracker/scripts/push_backups_to_synology.sh >> /old.log 2>&1
EOF
inst
check "unrelated jobs preserved"                   has "$CT" "run_db_backup_rotation.sh"
check "unmanaged raw rclone line left alone (manual cleanup)" has "$CT" "/usr/bin/rclone copy"
check "old NAS job line removed"                   hasnt "$CT" "push_backups_to_synology.sh"
check "4 managed jobs present"                     test "$(managed)" -eq 4
cp "$CT" "$T/c1.txt"; inst; check "re-run is idempotent" cmp -s "$CT" "$T/c1.txt"

# regression: crontab that holds ONLY managed lines used to abort (grep -v exit 1 + pipefail)
grep -E "push_srv_to_synology|sync_backups_to_google|verify_latest_manifest|backup_host_config" "$CT" > "$T/only.txt"; cp "$T/only.txt" "$CT"
inst; check "crontab holding only managed lines no longer aborts" test "$(managed)" -eq 4

summary
