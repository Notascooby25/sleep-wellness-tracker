# NUC Backup Overview (all three apps)

Last updated: 2026-09-20. This document is written to be copied into the other app workspaces (audio-scrobbler, expense tracker) so they know how backups work on the shared NUC and what changed. The scripts and the detailed runbook live in the **sleepwell** repo (`scripts/`, [backup-runbook.md](backup-runbook.md)). No hostnames, usernames or credentials are recorded here on purpose: this repo is public.

## Read this first (if you work on another app)

- The NUC runs three apps side by side under `/srv`. Since **2026-09-20**, everything under `/srv` except Postgres data files is mirrored to the Synology NAS every 6 hours by **one job owned by the sleepwell repo**. Your app is included automatically; you don't need to add anything.
- **Nothing was changed in the audio-scrobbler or expense-tracker code, cron entries or systemd timers.** Each app keeps its own backup pipeline. The NAS mirror is an extra copy on top.
- Rules of the road are in [section 5](#5-rules-for-other-app-workspaces).

## 1. Server layout (`/srv` on the NUC)

```text
/srv
  sleepwell/             git checkout; deployed with `git pull`
  audio-scrobbler-app/   file-drop dir: compose file, .env.production, scripts/, backups/, monitoring/ (not a git checkout)
  UK-Expense-Tracker/    git checkout; runtime data in data/, secrets in .streamlit/secrets.toml
  shared/
    backups/             local backup artifacts: DB dumps, archives, manifests, cron logs (mode 700)
    mood-images/         sleepwell's uploaded mood photos (+ accepted_missing_images.txt)
    garmin-tokens/       sleepwell's Garmin token file
    logs/                sleepwell backend/frontend logs
    postgres-data/       sleepwell's LIVE Postgres files (bind mount, owned by uid 999, mode 700)
```

Cron runs as the NUC user in local time (Europe/London). Scripts log timestamps in UTC.

## 2. Three layers of protection

```text
  app data ──► (1) local artifacts on the NUC ──► (2) Synology NAS mirror ──► (3) Google Drive (encrypted)
                   per-app scripts                  ONE job, all of /srv        per-app, artifacts only
```

| Layer | What | Who owns it |
|---|---|---|
| 1. Local | Each app makes its own dumps/archives | each app |
| 2. NAS | `/srv` mirrored to `/volume1/Backups/nuc-server` on the DS223, every 6h at `:30` | sleepwell repo (`push_srv_to_synology.sh`) |
| 3. Google Drive | rclone `gdrive-crypt` (client-side encrypted); only backup artifacts: app folders and `.env` files are never sent (the Garmin token tarball travels inside the encrypted backup copy) | each app (sleepwell: rclone copy of `/srv/shared/backups`; scrobbler: its own upload) |

### Per-app pipelines (unchanged, for reference)

| | sleepwell | audio-scrobbler | expense tracker |
|---|---|---|---|
| Data | Postgres (bind mount `/srv/shared/postgres-data`), mood images, Garmin tokens | Postgres in a **Docker named volume** (`postgres_data`, not under `/srv`) | `data/expense_database.csv`, `settings.json`, `saved_filters.json`, `.streamlit/secrets.toml` |
| Local backup | cron `run_db_backup_rotation.sh` at 00:00 and 12:00: `sleepdb_<UTC>.dump` + `.sql.gz` + sha256 manifest in `/srv/shared/backups`. Mood-image `.tar.gz` archives every 6h (`:15`, keeps 14) with an hourly integrity check. | systemd **user** timer every 6h: `scrobbler-<UTC>.dump` in `/srv/audio-scrobbler-app/backups`, restore-verified, heartbeat ping + Prometheus metrics. Local retention `BACKUP_RETENTION_DAYS` (default 3). | cron `0 3 */4 * *` (03:00 on days 1,5,9...): `data_backup.sh /srv/shared/backups 4` writes a `.tar.gz` + `.sha256` into `/srv/shared/backups` (keeps 4) |
| Google Drive | `rclone copy /srv/shared/backups` to `gdrive-crypt:backups/sleep-wellness` (90-day prune); mood archives also to `gdrive-crypt:mood-images/sleep-wellness` | its own script to `gdrive-crypt:AudioScrobblerBackups/` (`GDRIVE_RETENTION_DAYS=30`) | rides along inside sleepwell's copy of `/srv/shared/backups` |
| Restore doc | [backup-runbook.md](backup-runbook.md) | `docs/DISASTER_RECOVERY.md` in its repo | tarball, or the mirrored `data/` folder on the NAS |

## 3. The NAS mirror (new)

Script: `scripts/push_srv_to_synology.sh` in the sleepwell repo. Cron (installed by `scripts/setup_offsite_backup_cron.sh`): `30 */6 * * *`, output appended to `/srv/shared/backups/synology_backup_cron.log`.

NAS layout mirrors `/srv`:

```text
/volume1/Backups/nuc-server/
  shared/backups/          append-only: never deleted on the NAS, even after local rotation
  shared/mood-images/      mirror
  shared/garmin-tokens/    mirror
  shared/logs/             mirror, no version history
  sleepwell/               mirror
  audio-scrobbler-app/     mirror   (first time this app is on the NAS)
  UK-Expense-Tracker/      mirror
  _versions/<UTC time>/    files a mirror run replaced or deleted, pruned after 30 days
  _old-layout/             the previous layout, parked; delete after ~2026-10-20
```

How it behaves:

- **Two modes.** `shared/backups` is *append-only* (history accumulates on the NAS while the NUC rotates). Every other folder is a *mirror* with `--delete`, but each replaced or deleted file is first moved into `_versions/` (except logs).
- **Never copied:** `postgres-data/` (unreadable to the cron user, and a file copy of a live database isn't a usable backup, so the `.dump` files are the DB backup), `.git/`, `.venv/`, `venv/`, `node_modules/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.history/`, Synology `@eaDir` and `#recycle`. In `shared/backups` also `*.lock`, `*.tmp`, `.env*` and the old per-run `synology_sync_*.log`.
- **Secrets are included** for the app folders (`.env`, `.env.production` and its `.bak-*` copies, `secrets.toml`, `garmin_tokens.json`) with the source permissions preserved. These app-folder copies go to the NAS only, never to Google.
- **Safety guards.** A mirror whose source is missing or empty is skipped and reported (it will not empty the NAS copy). A run that would delete more than `MAX_DELETE` (200) files aborts that target. One failing target doesn't stop the others. The script exits non-zero if anything failed; an optional `NAS_HEALTHCHECK_URL` pings healthchecks.io (`/fail` on failure). It takes a lock (`/srv/shared/backups/.synology_sync.lock`), so runs can't overlap.
- **Config lives outside git** in `~/.config/nas-sync.env` on the NUC (`chmod 600`): `NAS_USER`, `NAS_HOST`, `NAS_PORT` (8022), `NAS_TARGET`. Optional: `SSH_KEY`, `NAS_HEALTHCHECK_URL`.
- **NAS permissions:** `nuc-server` is mode 700 (owner only), so other NAS users can't reach the copied secrets even where a file is 644 on the NUC. DSM admins still can.
- **Dry run:** `./scripts/push_srv_to_synology.sh --dry-run` shows exactly what would change and changes nothing.

## 4. What changed on 2026-09-20

**sleepwell repo**

- New `scripts/push_srv_to_synology.sh` (replaces `push_backups_to_synology.sh`, which is now unused and should be deleted once the new job has run cleanly for a few cycles).
- `scripts/setup_offsite_backup_cron.sh` now installs the new NAS job and removes the old NAS cron line.
- Backup upgrades that reached the NUC the same day: `flock` locking on the DB backup, NAS push and Google sync; Garmin token tarball and manifest pruning in `run_db_backup_rotation.sh`; default local retention raised to 14; optional Healthchecks.io ping; `scripts/test_restore_dump.sh` (restore drill in a throwaway Postgres container); 90-day pruning on the Google copy. See `backup-deployment-steps.md`.
- Docs: `backup-runbook.md` ("NAS Mirror"), `operations-reference.md`, `backup-deployment-steps.md`, and this file.

**NUC**

- Crontab: one line changed (`push_backups_to_synology.sh` to `push_srv_to_synology.sh`, same schedule). Previous crontab saved as `~/crontab-backup-20260920T181417.txt`.
- Created `~/.config/nas-sync.env`.
- `/srv/sleepwell` was reset onto GitHub `origin/main`: the NUC's old history had been rewritten upstream and the only content difference was a tracked `.history/` folder. Safety branch `backup-pre-reset-20260920` keeps the old history. A NUC-only uncommitted edit in `docker-compose.prod.yml` (`WATCHTOWER_SCOPE=none`) was preserved. `pull.ff only` is set so a future `git pull` fails loudly instead of merging.

**NAS**

| Old path | New path |
|---|---|
| `nuc-server/backups/` | `nuc-server/shared/backups/` |
| `nuc-server/mood-images/` (duplicate copy of the archives) | folded into `nuc-server/shared/backups/mood-images/` |
| stale one-off copies of the apps (May to Aug) | updated in place; replaced files are in `_versions/` |
| (none) | `nuc-server/audio-scrobbler-app/` |

Old `backups/` and `mood-images/` are parked in `nuc-server/_old-layout/`. Nothing was deleted.

## 5. Rules for other app workspaces

1. **Don't point your backups at another app's directory.** Keep your artifacts inside your own `/srv/<app>` folder (scrobbler: `/srv/audio-scrobbler-app/backups`). The mirror carries them to the NAS under your own folder, correctly filed. Writing into `/srv/shared/backups` files them under sleepwell's Google path and its append-only NAS tree. (Expense tracker already writes its tarballs there; that works and is covered by sleepwell's Google copy.)
2. **Never rsync or copy a live Postgres data directory.** Back databases up with `pg_dump` and keep the dumps.
3. **Everything in your `/srv/<app>` folder is mirrored every 6 hours, secrets included.** Don't leave stray copies of secrets lying around (e.g. old `.env.production.bak-*`); they will be mirrored too. Keep large regenerable data out of the app folder, or ask for an exclude.
4. **A new folder under `/srv` is not picked up automatically.** Adding a new app means one line in `push_srv_to_synology.sh`: `sync_dir mirror <folder-name> "${APP_EXCLUDES[@]}"`.
5. **Don't edit the NAS cron job or its script from another repo.** Make the change in the sleepwell repo and deploy it with `git pull` on the NUC.
6. **Keep your own recovery secrets off the NUC too.** The NAS copy of `.env.production` is a convenience, not a replacement for a password-manager copy (see the scrobbler DR doc).
7. **Check the NUC, not just the repo, before assuming something is deployed.** The live crontab and the checkouts have drifted from the repos before.

## 6. Restore quick reference

Run from the NUC; substitute your NAS user/host.

```bash
# a whole app folder back from the NAS
rsync -a -e "ssh -i ~/.ssh/id_ed25519_synology -p 8022" \
  <nas-user>@<nas-host>:/volume1/Backups/nuc-server/<app>/ /srv/<app>/

# a file that was overwritten or deleted: look in the version history first
ssh -i ~/.ssh/id_ed25519_synology -p 8022 <nas-user>@<nas-host> \
  "find /volume1/Backups/nuc-server/_versions -path '*<app>*' -name '<filename>'"
```

- **sleepwell database:** `pg_restore` the newest `sleepdb_*.dump` (`test_restore_dump.sh` rehearses this; see `backup-runbook.md`).
- **audio-scrobbler database:** follow its `docs/DISASTER_RECOVERY.md`. Dumps are also on the NAS in `audio-scrobbler-app/backups/`.
- **expense tracker:** newest `expense_tracker_data_*.tar.gz` in `shared/backups/`, or the mirrored `UK-Expense-Tracker/data/`.
- Restored files may need their original owner/permissions re-applied (garmin tokens are root-owned on the NUC).

## 7. Checking health

```bash
tail -n 50 /srv/shared/backups/synology_backup_cron.log      # NAS mirror: look for "Completed" and no FAILED/ERROR
crontab -l                                                    # 30 */6 line should point at push_srv_to_synology.sh
cd /srv/sleepwell && ./scripts/push_srv_to_synology.sh --dry-run   # should list ~nothing to send and nothing to delete
systemctl --user list-timers audio-scrobbler-backup.timer     # scrobbler pipeline
```

## 8. Known gaps and follow-ups

- **Pending from the DB-backup upgrade** (`backup-deployment-steps.md`): re-run `setup_db_backup_cron.sh` so the cron line uses `MAX_BACKUPS=14` (it is 4 today), and add `HEALTHCHECK_URL` to sleepwell's `.env` on the NUC (the script now reads it from there; until it is set, no ping is sent).
- **No NAS-side pruning of `shared/backups`.** It grows roughly 70 MB/day (about 25 GB/year). Fine for the 2.4 TB volume, but it needs a retention rule eventually.
- **No alerting on the NAS job** unless `NAS_HEALTHCHECK_URL` is set (optional, not configured).
- **Google jobs are duplicated in the crontab** (raw `rclone copy` lines at 00:20/12:20 plus the script lines). Harmless; not cleaned up. Some cron comment headers are stale.
- **Cleanup dates:** delete `nuc-server/_old-layout/` after about 2026-10-20; delete `push_backups_to_synology.sh` once the new job has run cleanly for a few cycles.

## Appendix: snippet for another workspace's AGENTS.md / CLAUDE.md

```markdown
## NUC backups (shared infrastructure)
- The NUC's whole /srv tree (except Postgres data files) is mirrored to the Synology NAS every 6h by
  sleepwell's scripts/push_srv_to_synology.sh. Our app folder is included automatically, secrets too.
- This app's own backup pipeline is separate and must stay separate. Don't write our artifacts into
  /srv/shared/backups (sleepwell's) and never copy a live Postgres data directory; use pg_dump.
- Don't edit the NAS cron job from this repo; changes go through the sleepwell repo.
- Full details: docs/nuc-backup-overview.md in the sleepwell repo (copy kept alongside this file).
```
