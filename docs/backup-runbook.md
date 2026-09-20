# NUC Backup Runbook

## Protection Layout

1. Database dumps and mood-image archives are created on the NUC at `/srv/shared/backups`.
2. `push_srv_to_synology.sh` mirrors the `/srv` tree to the DS223 at `/volume1/Backups/nuc-server` (see [NAS Mirror](#nas-mirror)): the backup artifacts plus the three app folders and `shared/{mood-images,garmin-tokens,logs}`.
3. The backup artifacts (only) are copied through the `gdrive-crypt` rclone crypt remote to Google Drive. File names and contents stored in Drive are encrypted by the crypt remote. App folders and secrets are never sent to Google.

Google copy uses `rclone copy`, not `rclone sync`, so Google retention is independent of local retention and an accidental local deletion does not delete remote copies.

## One-Time NUC Setup

Run these commands on the NUC as the account that owns and runs the application. Do not put NAS or Google credentials in this repository.

```bash
sudo mkdir -p /srv/shared/backups /srv/shared/mood-images/mood_images
sudo chown -R "$USER":"$USER" /srv/shared
findmnt -T /srv/shared/backups
```

If `/srv/shared` should be a NAS-mounted filesystem, configure its persistent system mount before installing cron. `findmnt -T /srv/shared/backups` must show the expected mount source after reboot.

Install and configure rclone interactively:

```bash
rclone config
rclone listremotes
rclone lsd gdrive-crypt:
```

Create a Google Drive remote first, then create `gdrive-crypt` as an rclone `crypt` remote whose underlying target is a directory in that Drive remote. Select filename and directory-name encryption. Keep the rclone config and its password material outside the repository.

Install the application backup jobs:

```bash
cd /home/andyl/sleep-wellness-tracker
chmod +x scripts/*.sh
./scripts/setup_db_backup_cron.sh
./scripts/setup_mood_image_backup_cron.sh
./scripts/setup_offsite_backup_cron.sh
crontab -l
```

## Initial Verification

Create local data, then replicate it and verify both destinations:

```bash
./scripts/run_db_backup_rotation.sh
./scripts/mood_images_backup.sh
./scripts/mood_images_verify.sh
./scripts/push_srv_to_synology.sh --dry-run   # review, then run without --dry-run
./scripts/sync_backups_to_google.sh
./scripts/verify_latest_manifest.sh
```

## NAS Mirror

`scripts/push_srv_to_synology.sh` runs every 6 hours (`30 */6 * * *`, installed by `setup_offsite_backup_cron.sh`). The NAS layout mirrors `/srv`:

```text
/volume1/Backups/nuc-server/
  shared/backups/          append-only: dumps, archives, manifests (never deleted on the NAS)
  shared/mood-images/      mirror of the raw images + accepted_missing_images.txt
  shared/garmin-tokens/    mirror
  shared/logs/             mirror, no version history
  sleepwell/  audio-scrobbler-app/  UK-Expense-Tracker/    mirrors
  _versions/<UTC time>/    files changed or deleted by a mirror run, pruned after 30 days
```

- `shared/postgres-data` is **never** copied. It is owned by the container's postgres user (mode 700, unreadable to the cron user), and a file copy of a live database is not a usable backup. Restore the database from the `.dump` files in `shared/backups`.
- Mirrors delete files on the NAS that were deleted on the NUC, but the old version is moved to `_versions/` first. A mirror whose source is missing or empty is skipped and reported as a failure, and a run that would delete more than `MAX_DELETE` (200) files aborts that target.
- Mirrors include secrets (`.env`, `.env.production`, `secrets.toml`, `garmin_tokens.json`) with their permissions preserved. This is a convenience copy on the NAS only; the scrobbler's `.env.production` must still be kept in your password manager (see its DISASTER_RECOVERY.md).
- The audio-scrobbler backup pipeline (systemd timer, `gdrive-crypt:AudioScrobblerBackups`) is separate and untouched. Mirroring its folder just gives its dumps a second copy on the NAS under `audio-scrobbler-app/backups/`.
- Live restore of a mirrored folder: `rsync -a <nas>:/volume1/Backups/nuc-server/<name>/ /srv/<name>/`. To get back a deleted or overwritten file, look in `_versions/`.

### NAS settings (not in git)

Create `~/.config/nas-sync.env` on the NUC, `chmod 600`:

```bash
NAS_USER=<nas-user>
NAS_HOST=<nas-ip>
# optional: NAS_PORT=8022  NAS_TARGET=/volume1/Backups/nuc-server  SSH_KEY=~/.ssh/id_ed25519_synology
# optional dead-man's switch (a separate healthchecks.io check, every 6h + grace):
# NAS_HEALTHCHECK_URL=https://hc-ping.com/<uuid>
```

### One-time NAS migration (old layout to new)

The previous job wrote to `nuc-server/backups` and `nuc-server/mood-images`. Move those under `shared/` on the NAS itself (same volume, nothing is re-uploaded). Run from the NUC; substitute your NAS user/host:

```bash
ssh -i ~/.ssh/id_ed25519_synology -p 8022 "${NAS_USER}@${NAS_HOST}"
cd /volume1/Backups/nuc-server

# 1. Merge old backups/ into shared/backups/ (--update: never overwrite newer files)
rsync -a --update --exclude='@eaDir' backups/ shared/backups/

# 2. Every archive in the old mood-images/ must already exist in shared/backups/mood-images/ (expect NO output)
( cd mood-images && ls | grep -E '\.tar\.gz(\.sha256)?$' | sort ) > /tmp/old_mood.txt
( cd shared/backups/mood-images && ls | grep -E '\.tar\.gz(\.sha256)?$' | sort ) > /tmp/new_mood.txt
comm -23 /tmp/old_mood.txt /tmp/new_mood.txt

# 3. Park the old directories; delete _old-layout once you are happy (about a month)
mkdir -p _old-layout && mv backups _old-layout/backups && mv mood-images _old-layout/mood-images
```

If step 2 prints anything, stop and copy those files into `shared/backups/mood-images/` first. The stale top-level copies (`/volume1/Backups/{sleepwell,shared,UK-Expense-Tracker}` and the old `nuc-server/{sleepwell,UK-Expense-Tracker,shared}` snapshots from before) are not touched by this job apart from `nuc-server/sleepwell` and `nuc-server/UK-Expense-Tracker`, which the mirror now updates in place (replaced files go to `_versions/`).

### First run and monitoring

```bash
./scripts/push_srv_to_synology.sh --dry-run | less    # nothing is changed
./scripts/push_srv_to_synology.sh                     # real run
./scripts/setup_offsite_backup_cron.sh                # swaps the old NAS cron line for the new one
tail -n 50 /srv/shared/backups/synology_backup_cron.log
```

The script exits non-zero and lists the failed targets if anything goes wrong. Each run logs to `synology_backup_cron.log` (the old per-run `synology_sync_*.log` files are pruned after 14 days). Once the new job has run cleanly for a few cycles, `push_backups_to_synology.sh` can be deleted.

## Accepted Missing Image Baseline

If historical mood images are confirmed unrecoverable, capture them once as an accepted-loss baseline. This preserves the mood records while keeping checks strict for every newly missing image:

```bash
WRITE_ACCEPTED_BASELINE=1 ./scripts/mood_images_verify.sh
./scripts/mood_images_verify.sh
```

The baseline is stored at `/srv/shared/mood-images/accepted_missing_images.txt` with permissions restricted to its owner. It is included in mood-image archives. The creation command refuses to overwrite an existing baseline; review and remove that file manually only when intentionally replacing the accepted-loss record.

Check the DS223 contains current files and validate its latest manifest over SSH (substitute your own NAS user/host):

```bash
ssh -p 8022 "${NAS_USER}@${NAS_HOST}" 'find /volume1/Backups/nuc-server -type f -not -path '*/@eaDir/*' -printf "%TY-%Tm-%Td %TH:%TM %s %p\\n" | sort -r | head -n 30'
```

For the Google copy, `verify_latest_manifest.sh` must exit zero. It downloads the encrypted remote manifest and compares it byte-for-byte with the current local manifest.

Review ongoing health after each scheduled cycle:

```bash
tail -n 100 /srv/shared/backups/db_backup_cron.log
tail -n 100 /srv/shared/backups/synology_backup_cron.log   # NAS mirror
tail -n 100 /srv/shared/backups/google_backup_cron.log
tail -n 100 /srv/shared/backups/google_verify_cron.log
sha256sum -c "$(ls -1t /srv/shared/backups/manifest_*.sha256 | head -n 1)"
```