# NUC Backup Overview (all three apps)

Last updated: 2026-09-21. This document is written to be copied into the other app workspaces (audio-scrobbler, expense tracker) so they know how backups work on the shared NUC and what changed. The scripts and the detailed runbook live in the **sleepwell** repo (`scripts/`, [backup-runbook.md](backup-runbook.md)). No hostnames, usernames or credentials are recorded here on purpose: this repo is public.

## Read this first (if you work on another app)

- The NUC runs three apps side by side under `/srv`. Since **2026-09-20**, everything under `/srv` except Postgres data files is mirrored to the Synology NAS every 6 hours by **one job owned by the sleepwell repo**. Your app is included automatically; you don't need to add anything.
- **The NAS mirror itself changed nothing in the audio-scrobbler or expense-tracker code, cron entries or systemd timers.** Each app keeps its own backup pipeline; the mirror is an extra copy on top. (The expense tracker's own backup was upgraded separately on 2026-09-21: see [Follow-up 2026-09-21](#follow-up-2026-09-21).)
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
| Data | Postgres (bind mount `/srv/shared/postgres-data`), mood images, Garmin tokens | Postgres in a **Docker named volume** (`postgres_data`, not under `/srv`) | everything in `data/` (`expense_database.csv`, `settings.json`, `saved_filters.json` and the joint-account `expense_database_joint.csv` / `settings_joint.json`), plus `.streamlit/secrets.toml` |
| Local backup | cron `run_db_backup_rotation.sh` at 00:00 and 12:00: `sleepdb_<UTC>.dump` + `.sql.gz` + sha256 manifest in `/srv/shared/backups`. Mood-image `.tar.gz` archives every 6h (`:15`, keeps 14) with an hourly integrity check. | systemd **user** timer every 6h: `scrobbler-<UTC>.dump` in `/srv/audio-scrobbler-app/backups`, restore-verified, heartbeat ping + Prometheus metrics. Local retention `BACKUP_RETENTION_DAYS` (default 3). | cron daily at 03:00: `data_backup.sh /srv/shared/backups 14` archives the **whole `data/` folder** (joint files included, `secrets.toml` deliberately not) into `expense_tracker_data_<ts>.tar.gz` + `.sha256` in `/srv/shared/backups`, self-verified before it is promoted, keeps 14. Installed by the expense repo's `scripts/setup_backup_cron.sh`. |
| Google Drive | `sync_backups_to_google.sh` copies `/srv/shared/backups` to `gdrive-crypt:backups/sleep-wellness` (90-day prune), then **asserts freshness** and pings a healthchecks.io check (see [section 9](#9-monitoring-what-tells-you-when-something-stops)); mood archives also to `gdrive-crypt:mood-images/sleep-wellness` | its own script to `gdrive-crypt:AudioScrobblerBackups/` (`GDRIVE_RETENTION_DAYS=30`) | rides along inside sleepwell's copy of `/srv/shared/backups` |
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
- DB backup cron line changed from `MAX_BACKUPS=4` to `MAX_BACKUPS=14` (crontab saved as `~/crontab-backup-20260920T183711.txt`). The first Garmin token tarball was created by a manual run of the upgraded rotation script; from now on one is made every 12h with the DB dump.
- `HEALTHCHECK_URL` (a healthchecks.io check, every 12h with a 1h grace period) was added to `/srv/sleepwell/.env`. `run_db_backup_rotation.sh` reads it from there and pings after each successful run, so a silent failure or a dead cron shows up as a missed ping. Verified with a manual run (ping accepted).
- `/srv/sleepwell/.env` tightened from mode 644 to 600 (it holds the DB password and the ping URL). It is only read by the docker client and the backup scripts, both running as the NUC user, and it is not mounted into any container, so nothing broke (verified: `docker compose config`, containers still healthy). The NAS copy follows at the next sync.
- `/srv/sleepwell` was reset onto GitHub `origin/main`: the NUC's old history had been rewritten upstream and the only content difference was a tracked `.history/` folder. Safety branch `backup-pre-reset-20260920` keeps the old history. A NUC-only uncommitted edit in `docker-compose.prod.yml` (`WATCHTOWER_SCOPE=none`) was preserved. `pull.ff only` is set so a future `git pull` fails loudly instead of merging.

**NAS**

| Old path | New path |
|---|---|
| `nuc-server/backups/` | `nuc-server/shared/backups/` |
| `nuc-server/mood-images/` (duplicate copy of the archives) | folded into `nuc-server/shared/backups/mood-images/` |
| stale one-off copies of the apps (May to Aug) | updated in place; replaced files are in `_versions/` |
| (none) | `nuc-server/audio-scrobbler-app/` |

Old `backups/` and `mood-images/` are parked in `nuc-server/_old-layout/`. Nothing was deleted.

### Follow-up 2026-09-21

An audit of the live NUC, NAS and Drive found these gaps; all are now addressed in code. The **NUC-side steps** (pull, crontab, env files, health checks) still have to be applied on the host, in this order: expense cadence first, then the Google freshness check.

- **Expense tracker: joint-account data was not in the Google copy.** The tarball held only three files. `scripts/data_backup.sh` (expense repo) now archives the whole `data/` folder, builds the archive as `.tmp`, self-checks it (readable, contains the main CSV, header matches the source) and only then promotes it. The `.sha256` now records a bare filename so `sha256sum -c` works wherever the pair is restored. Runs **daily** and keeps 14 (it was every 4th day, keep 4).
- **Silent failure of the producers.** `rclone copy` cheerfully re-uploads yesterday's files when the job that should have made new ones died. `scripts/sync_backups_to_google.sh` now checks that the newest sleepwell DB dump (<26h), mood archive (<13h), expense archive (<26h) and host-config snapshot (<26h) are current, and pings `/fail` otherwise. One healthchecks.io check covers all four producers plus the upload.
- **Google prune noise.** `rclone delete --min-age 90d --rmdirs` logged "directory not empty" every run. `--rmdirs` is dropped and empty directories are removed by a separate `rclone rmdirs --leave-root`.
- **Host configuration was in no backup.** New `scripts/backup_host_config.sh` writes a daily snapshot (crontab, systemd user timers and unit files, Tailscale Funnel status, `docker ps`, rclone remote *names*, redacted `nas-sync.env`, git HEAD and local diffs of each `/srv` checkout) to `/srv/shared/backups/host-config/`, from where the NAS mirror and Google copy carry it off the host. It never captures `rclone.conf`, SSH keys or docker credentials.
- **Cron installer.** `setup_offsite_backup_cron.sh` installs the host-config job (`10 4 * * *`) and no longer aborts when the crontab contains only its own jobs.

## 5. Rules for other app workspaces

1. **Don't point your backups at another app's directory.** Keep your artifacts inside your own `/srv/<app>` folder (scrobbler: `/srv/audio-scrobbler-app/backups`). The mirror carries them to the NAS under your own folder, correctly filed. Writing into `/srv/shared/backups` files them under sleepwell's Google path and its append-only NAS tree. (Expense tracker already writes its tarballs there; that works and is covered by sleepwell's Google copy.)
2. **Never rsync or copy a live Postgres data directory.** Back databases up with `pg_dump` and keep the dumps.
3. **Everything in your `/srv/<app>` folder is mirrored every 6 hours, secrets included.** Don't leave stray copies of secrets lying around (e.g. old `.env.production.bak-*`); they will be mirrored too. Keep large regenerable data out of the app folder, or ask for an exclude. Keep secret files mode 600 (like `.env` and `.env.production`) unless a container reads them through a bind mount, where a stricter mode could break the app.
4. **A new folder under `/srv` is not picked up automatically.** Adding a new app means one line in `push_srv_to_synology.sh`: `sync_dir mirror <folder-name> "${APP_EXCLUDES[@]}"`.
5. **Don't edit the NAS cron job or its script from another repo.** Make the change in the sleepwell repo and deploy it with `git pull` on the NUC.
6. **Keep your own recovery secrets off the NUC too.** The NAS copy of `.env.production` is a convenience, not a replacement for a password-manager copy (see the scrobbler DR doc). Two secrets are in *no* backup at all and must be in a password manager: `~/.config/rclone/rclone.conf` (the crypt passwords: without them every Google copy is unreadable) and the expense tracker's `.streamlit/secrets.toml` (kept out of the Google-bound archive on purpose; the NAS folder mirror holds a copy).
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
- **expense tracker:** newest `expense_tracker_data_*.tar.gz` in `shared/backups/` (now includes the joint-account files), or the mirrored `UK-Expense-Tracker/data/`. Verify with `sha256sum -c` next to the archive, stop the container (`docker stop uk_expense_tracker`), `tar -xzf … -C /srv/UK-Expense-Tracker`, start it again. Older archives (before 2026-09-21) hold only the three main files.
- Restored files may need their original owner/permissions re-applied (garmin tokens are root-owned on the NUC).

## 7. Checking health

```bash
tail -n 50 /srv/shared/backups/synology_backup_cron.log      # NAS mirror: look for "Completed" and no FAILED/ERROR
crontab -l                                                    # 30 */6 line should point at push_srv_to_synology.sh
cd /srv/sleepwell && ./scripts/push_srv_to_synology.sh --dry-run   # should list ~nothing to send and nothing to delete
systemctl --user list-timers audio-scrobbler-backup.timer     # scrobbler pipeline
tail -n 12 /srv/shared/backups/google_backup_cron.log         # Google: four "OK: newest ..." lines, no STALE/ERROR
ls -lt /srv/shared/backups/host-config | head -3              # a snapshot from today
```

Prove the copies restore (not just that they were written):

```bash
cd /srv/audio-scrobbler-app && scripts/restore_drill.sh nas      # also: local, gdrive
cd /srv/sleepwell && ./scripts/test_restore_dump.sh              # sleepwell DB, throwaway container
```

## 8. Known gaps and follow-ups

- **No NAS-side pruning of `shared/backups`.** It grows roughly 70 MB/day (about 25 GB/year). Fine for the 2.4 TB volume, but it needs a retention rule eventually.
- **Other secret files are still mode 644 on the NUC:** `UK-Expense-Tracker/.streamlit/secrets.toml` and `shared/garmin-tokens/garmin_tokens.json` (root-owned). Both are read by containers via bind mounts, so they were left alone rather than risk breaking those apps. They are protected on the NAS by its 700 folder.
- **Every push to sleepwell's `main` runs the image build and watchtower redeploys the app** (a few seconds of restart), even for docs-only commits. Put `[skip ci]` in the commit message of docs/script-only commits. (A `paths-ignore` filter in `.github/workflows/build-amd64.yml` would make this automatic; not done.)
- **No alerting on the NAS job** unless `NAS_HEALTHCHECK_URL` is set in `~/.config/nas-sync.env` (a separate healthchecks.io check, every 6h, 1h grace). Set it; without it a dead NAS or rotated key is silent for all three apps.
- **The sleepwell checkout is load-bearing for every app.** The NAS mirror and the Google copy of all three apps run from `/srv/sleepwell/scripts/`, updated by manual `git pull`. A broken or wiped checkout stops them all; the two heartbeats in [section 9](#9-monitoring-what-tells-you-when-something-stops) are what make that visible. The NUC checkout also carries local edits (`docker-compose.prod.yml`, a mode change on `push_backups_to_synology.sh`), so `pull.ff=only` will refuse a pull that touches those files: do not delete `push_backups_to_synology.sh` upstream until the NUC copy is reset.
- **The raw duplicate Google cron lines** (`rclone copy` at 00:20/12:20 for `/srv/shared/backups`) were superseded by `sync_backups_to_google.sh`, which adds locking, excludes, pruning and the freshness heartbeat; remove that one line from the NUC crontab. (The `mood-images/sleep-wellness` raw line is a separate destination and stays.) Mood archives are therefore uploaded twice to Google (also inside `backups/sleep-wellness/mood-images/`); harmless redundancy in the same failure domain.
- **Cleanup dates:** delete `nuc-server/_old-layout/` after about 2026-10-20; delete `push_backups_to_synology.sh` once the new job has run cleanly for a few cycles.

## 9. Monitoring: what tells you when something stops

| Job | Signal | Configured in |
|---|---|---|
| Sleepwell DB dump | healthchecks.io ping after each successful run (12h, 1h grace) | `HEALTHCHECK_URL` in `/srv/sleepwell/.env` |
| Scrobbler dump + restore-verify | heartbeat ping + Prometheus/Alertmanager (verify and offsite stale >12h) | `HEARTBEAT_URL` in `audio-scrobbler-backup.env`; scrobbler repo |
| **NAS mirror** (all apps) | healthchecks.io ping on success, `/fail` on error (6h, 1h grace) | `NAS_HEALTHCHECK_URL` in `~/.config/nas-sync.env` |
| **Google copy + producer freshness** (sleepwell DB, mood images, expense, host config) | healthchecks.io ping only if the upload succeeded **and** every producer is current (6h, 1h grace) | `GOOGLE_HEALTHCHECK_URL` in `~/.config/google-sync.env` (`chmod 600`) |

`~/.config/google-sync.env` (not in git):

```bash
GOOGLE_HEALTHCHECK_URL=https://hc-ping.com/<uuid>
# optional overrides (hours; 0 switches that check off):
# FRESH_DB_HOURS=26  FRESH_MOOD_HOURS=13  FRESH_EXPENSE_HOURS=26  FRESH_HOSTCONFIG_HOURS=26
```

Precedence is caller environment (an inline `VAR=` in the cron line) > that file > the defaults. Deploy order matters when rolling this out: switch the expense backup to daily and install the host-config job **before** the new Google script runs, otherwise its freshness check reports those two as missing/stale.

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
