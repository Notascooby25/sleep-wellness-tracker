# NUC Backup Runbook

## Protection Layout

1. Database dumps and mood-image archives are created on the NUC at `/srv/shared/backups`.
2. The completed artifacts are copied to the DS223 at `/volume1/Backups/nuc-server`.
3. The same artifacts are copied through the `gdrive-crypt` rclone crypt remote to Google Drive. File names and contents stored in Drive are encrypted by the crypt remote.

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
./scripts/push_backups_to_synology.sh
./scripts/sync_backups_to_google.sh
./scripts/verify_latest_manifest.sh
```

## Accepted Missing Image Baseline

If historical mood images are confirmed unrecoverable, capture them once as an accepted-loss baseline. This preserves the mood records while keeping checks strict for every newly missing image:

```bash
WRITE_ACCEPTED_BASELINE=1 ./scripts/mood_images_verify.sh
./scripts/mood_images_verify.sh
```

The baseline is stored at `/srv/shared/mood-images/accepted_missing_images.txt` with permissions restricted to its owner. It is included in mood-image archives. The creation command refuses to overwrite an existing baseline; review and remove that file manually only when intentionally replacing the accepted-loss record.

Check the DS223 contains current files and validate its latest manifest over SSH:

```bash
ssh -p 8022 Congreve202@192.168.68.107 'find /volume1/Backups/nuc-server -type f -printf "%TY-%Tm-%Td %TH:%TM %s %p\\n" | sort -r | head -n 30'
```

For the Google copy, `verify_latest_manifest.sh` must exit zero. It downloads the encrypted remote manifest and compares it byte-for-byte with the current local manifest.

Review ongoing health after each scheduled cycle:

```bash
tail -n 100 /srv/shared/backups/db_backup_cron.log
tail -n 100 /srv/shared/backups/synology_backup_cron.log
tail -n 100 /srv/shared/backups/google_backup_cron.log
tail -n 100 /srv/shared/backups/google_verify_cron.log
sha256sum -c "$(ls -1t /srv/shared/backups/manifest_*.sha256 | head -n 1)"
```