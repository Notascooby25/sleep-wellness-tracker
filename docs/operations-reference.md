# Sleep Wellness Tracker — Operations Reference

Current version: `4.9.0`. Last significant change: 2026-09-03 (category-level position support, custom position options).

---

## Infrastructure

| Host | Address | Role |
|---|---|---|
| NUC | see local ops notes (not committed) | Runs the app in Docker |
| DS223 NAS | see local ops notes (not committed); SSH port `8022` | Local mirror of backups |
| Google Drive | remote `gdrive-crypt` (rclone) | Encrypted offsite backup |

Real hostnames/IPs/usernames for this deployment are kept out of the public repo. Set them as environment variables (e.g. `DS223_HOST`, `DS223_USER`) or in a local, gitignored notes file when running the scripts under `scripts/`.

**On the NUC**

- App deployment directory: `/srv/sleepwell`
- Shared runtime data: `/srv/shared`
- Backups root: `/srv/shared/backups`
- Mood image storage: `/srv/shared/mood-images/mood_images`

**On the dev workstation**

- Working copy: `/home/andyl/sleep-wellness-tracker`
- Watcher: `./scripts/watcher_commit_open.sh .` (auto-commits saves)

---

## Deployment model

The NUC does **not** build images. Deployment is CI-driven:

1. Push to `main` on GitHub.
2. `.github/workflows/build-amd64.yml` runs the lint + build job and pushes new `:latest` images to GHCR (backend + frontend-web).
3. Watchtower on the NUC polls every 300 s (5 min) and pulls the new `:latest`.
4. Backend startup patches missing schema columns via `_ensure_legacy_schema_compatibility()` in `backend/app/database.py`.

**Never** use `docker compose up --build` on the NUC — the compose file references `image:`, not `build:`, so `--build` is a no-op.

Force a manual rollout on the NUC:

```bash
cd /srv/sleepwell
sudo docker compose -f docker-compose.prod.yml pull backend frontend_web
sudo docker compose -f docker-compose.prod.yml up -d --force-recreate backend frontend_web
```

**GHCR authentication**

GHCR pulls need `/root/.docker/config.json` on the NUC. Watchtower reads it from a bind mount. If Watchtower logs show `auth: "not present"`:

```bash
export GHCR_PAT='ghp_your_read_packages_token'
echo "$GHCR_PAT" | sudo docker login ghcr.io -u Notascooby25 --password-stdin
```

Token requires the `read:packages` scope.

**After every code change** the required workflow is:

1. Bump `frontend-web/package.json` version (patch/minor/major appropriately).
2. Commit with a Conventional Commit message.
3. Push to `origin/main`.

---

## Data model

**Categories** (`categories`) — 6 fixed timeline groups:

| id | name |
|---|---|
| 1 | Lifestyle |
| 2 | Headache Issues |
| 3 | Health |
| 4 | Before Sleep |
| 5 | During Sleep |
| 6 | Morning / Waking Feedback |

**Activities** (`activities`) — `id`, `name`, `category_id`, `is_archived`, `deprecated_at`. Deprecated rows are hidden from the picker but still queryable and still keep their historical mood links.

**Mood entries** (`moods`) — `mood_score` (1–5, 1 = great, 5 = struggling), `notes`, `image_url` / `image_urls`, `timestamp`, and the new `subjective_sleep_rating` (1–5, 1 = great, 5 = poor).

**Join** — `mood_activities` (mood_id, activity_id).

**Per-link details** (`mood_activity_details`) — nullable `position`, `severity`, `quantity_numeric`, `quantity_unit`. Written when a position-sensitive tag is selected (Headache family, Jaw / TMJ Pain, Sharp Shooting Pain, Throat Strain, Tinnitus / Ear Humming, Ear Ache, Shoulder / Arm / Neck Pain) or when a quantity tag is selected (Alcohol → units, Caffeine after 4pm → cups).

Historical Garmin data lives in `garmin_*_daily` and `garmin_activities`. `garmin_sync_state` records last-sync watermarks.

Mood image uploads require a mounted persistent path (`MOOD_IMAGE_REQUIRE_MOUNT=1`). If missing, uploads/reads return HTTP 503 rather than writing to ephemeral storage.

---

## Backup strategy

Three tiers, each verified.

### Tier 1 — Local NUC snapshots

| Data | Path | Retention | Cron |
|---|---|---|---|
| DB dumps + manifests | `/srv/shared/backups/*.dump`, `*.sql.gz`, `manifest_*.sha256` | 4 snapshots | every 12 h |
| Mood image archives | `/srv/shared/backups/mood-images/mood_images_*.tar.gz` + `.sha256` | 14 archives | every 6 h at :15 |
| Mood image verify | writes to `/srv/shared/backups/mood_images_hook.log` | — | hourly at :45 |

Install/refresh crons:

```bash
./scripts/setup_db_backup_cron.sh
./scripts/setup_mood_image_backup_cron.sh
./scripts/setup_offsite_backup_cron.sh
crontab -l
```

### Tier 2 — DS223 mirror

Script: [scripts/push_backups_to_synology.sh](scripts/push_backups_to_synology.sh)

- Destination: `/volume1/Backups/nuc-server`
  - `backups/` — DB dumps + manifests
  - `mood-images/` — image archives
- Auth: SSH key at `$SSH_KEY` (see script), port `8022`, user/host from `NAS_USER`/`NAS_HOST` env vars (not committed).
- Uses `rsync -az` with excludes for `.env*`, `postgres-data/`.
- Logs: `/srv/shared/backups/synology_sync_<UTC>.log`

### Tier 3 — Google Drive encrypted

Script: [scripts/sync_backups_to_google.sh](scripts/sync_backups_to_google.sh)

- Remote: `gdrive-crypt:backups/sleep-wellness` (an rclone crypt remote wrapping a Google Drive remote).
- Uses `rclone copy` (never `sync`), so local retention cannot delete remote history.
- File **names and contents are encrypted** on Drive; to read them, always go through rclone.
- Config path: `~/.config/rclone/rclone.conf`.

List decrypted view:

```bash
rclone config show gdrive-crypt
rclone lsf gdrive-crypt:backups/sleep-wellness
```

### Off-host schedule

Installed by `scripts/setup_offsite_backup_cron.sh` — every 6 hours:

- `:30` — DS223 push
- `:35` — Google copy
- `:50` — Google manifest verification

Verification script: [scripts/verify_latest_manifest.sh](scripts/verify_latest_manifest.sh) — downloads the newest local manifest from Drive and diffs it byte-for-byte. Non-zero exit means mismatch.

### Verifying it's working

```bash
crontab -l
ls -1t /srv/shared/backups/*.dump | head -n 3
tail -n 100 /srv/shared/backups/db_backup_cron.log
tail -n 100 /srv/shared/backups/synology_backup_cron.log
tail -n 100 /srv/shared/backups/google_backup_cron.log
tail -n 100 /srv/shared/backups/google_verify_cron.log
sha256sum -c "$(ls -1t /srv/shared/backups/manifest_*.sha256 | head -n 1)"
./scripts/verify_latest_manifest.sh
```

### Restore procedures

DB restore from `.dump`:

```bash
NEWEST=$(ls -1t /srv/shared/backups/*.dump | head -n 1)
docker cp "$NEWEST" sleep_db:/tmp/restore.dump
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" sleep_db \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --clean --if-exists /tmp/restore.dump
```

Mood images restore from an archive:

```bash
ARCHIVE=/srv/shared/backups/mood-images/mood_images_YYYYMMDDTHHMMSSZ.tar.gz
mkdir -p /srv/shared/mood-images/mood_images
tar -xzf "$ARCHIVE" -C /srv/shared/mood-images/mood_images
./scripts/mood_images_verify.sh
```

Recovering something from Google:

```bash
mkdir -p /tmp/recover
rclone copy gdrive-crypt:backups/sleep-wellness /tmp/recover \
  --include '*.dump' --include 'manifest_*.sha256' --config ~/.config/rclone/rclone.conf
```

### Accepted-missing image baseline

60 mood-image files were confirmed unrecoverable on 2026-09-02. Their filenames were captured to `/srv/shared/mood-images/accepted_missing_images.txt`. `mood_images_verify.sh` treats these as accepted losses; a **new** missing file still triggers a strict failure.

To rebuild the baseline intentionally (only if you know what you're doing):

```bash
rm /srv/shared/mood-images/accepted_missing_images.txt
WRITE_ACCEPTED_BASELINE=1 ./scripts/mood_images_verify.sh
```

---

## Taxonomy v2 (applied 2026-09-02)

Migration script: `scripts/apply_taxonomy_v2.py` driven by `db/taxonomy_v2.json`. Runbook: `docs/taxonomy-migration-runbook.md`. Applied audit log: `/srv/shared/backups/taxonomy_v2_apply_20260902T180257Z.jsonl`.

### What was done

- Emoji activities renamed (`Reading 📚 → Reading`, `Workout 🏋️‍♂️ → Strength / Workout`, etc.) via SQL first, then the migration.
- 5 explicit deprecations (Before Sleep `Reading`, `Exercise`, `Pain`, `Illness`; Lifestyle `Exercise`). Their historical mood links **stay** — they're just hidden from new logging.
- 25 merges consolidated fragmented tags into parents. Position captured in `mood_activity_details`. Totals:
  - **501 mood links repointed**
  - **237 position/quantity detail rows created**
  - **92 headache detail rows** with `Left / Right / Front / Back-Left / Back-Right`
- 36 new activities added (parent tags + sleep-outcome tags).

### Position-sensitive tags

`Headache`, `Jaw / TMJ Pain`, `Sharp Shooting Pain`, `Throat Strain`, `Tinnitus / Ear Humming`, `Ear Ache`, `Shoulder / Arm / Neck Pain`.

### Quantity tags

`Alcohol` (units), `Caffeine after 4pm` (cups).

### Rating semantics

- `moods.mood_score` — overall entry mood, 1 = great, 5 = struggling.
- `moods.subjective_sleep_rating` — 1 = great, 5 = poor. Optional. Only rendered when the `Morning / Waking Feedback` tab is active **or** a Morning/Waking activity is already selected.

### Re-running

`apply_taxonomy_v2.py` is idempotent. Re-running is a no-op after a successful apply.

### Sanity queries

Deprecated activities from **merges** should have zero live links (explicit-deprecate activities keep theirs):

```bash
docker exec -i sleep_db psql -U sleepuser -d sleepdb -c "
SELECT a.id, a.name, COUNT(*) AS live_links
FROM mood_activities ma JOIN activities a ON a.id = ma.activity_id
WHERE a.deprecated_at IS NOT NULL
  AND a.name NOT IN ('Reading','Exercise','Pain','Illness')
GROUP BY a.id, a.name ORDER BY 3 DESC;
"
```

Position distribution:

```bash
docker exec -i sleep_db psql -U sleepuser -d sleepdb -c "
SELECT a.name, mad.position, COUNT(*) AS n
FROM mood_activity_details mad JOIN activities a ON a.id = mad.activity_id
GROUP BY a.name, mad.position ORDER BY 1, 2;
"
```

---

## Common operations

**Take a fresh backup + verify offsite:**

```bash
cd /srv/sleepwell
./scripts/run_db_backup_rotation.sh
./scripts/mood_images_backup.sh
./scripts/push_backups_to_synology.sh
./scripts/sync_backups_to_google.sh
./scripts/verify_latest_manifest.sh
```

**Rebuild/roll out after a code push:**

```bash
sudo docker compose -f docker-compose.prod.yml pull backend frontend_web
sudo docker compose -f docker-compose.prod.yml up -d --force-recreate backend frontend_web
```

**Check container health:**

```bash
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Image}}' | grep sleep
docker logs --tail 50 sleep_backend
```

**Confirm running image is the latest commit:**

```bash
sudo docker inspect ghcr.io/notascooby25/sleep-wellness-tracker-backend:latest \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
```

---

## Known limitations to revisit

- `docs/taxonomy-migration-runbook.md` rollback step assumes the fresh dump path.
- Mood-log edit save does not round-trip `activity_details`; the backend’s `None`-preserving semantics protect the data, but unchecking an activity may leave an orphan detail row (harmless; investigate later if it grows).
- Taxonomy migration script’s dry-run doesn’t simulate mid-transaction state (deprecations aren’t visible to subsequent reads until `--apply`). Log lines about spurious “merge” intents in dry-run are cosmetic — the apply run does the right thing.

---

## Version history (recent)

- **4.7.1** — mood-log shows deprecated activity names and position/quantity chips.
- **4.7.0** — position pills now selectable; Sleep Rating gated to Morning / Waking context; label clarity.
- **4.6.3** — runbook verification corrected.
- **4.6.2** — Legacy `Back Right` folded into Headache `Back-Right`.
- **4.6.1** — Emoji rename fixes; deprecate-before-rename order.
- **4.6.0** — Additive schema, taxonomy v2 machinery, backend acceptance.
- **4.5.6** — Accepted-missing mood-image baseline.
- **4.5.5** — Encrypted Google sync + off-host scheduler.
