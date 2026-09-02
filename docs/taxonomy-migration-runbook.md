# Taxonomy v2 Migration Runbook

This runbook applies the category and activity refactor defined in `db/taxonomy_v2.json`. It is deliberately manual: **do not run any step until the previous step succeeded**.

## What it does

- Adds new activities (`Headache`, `Jaw / TMJ Pain`, `Fatigue`, `Light Walk`, sleep-outcome tags, and more).
- Renames typos and emoji tags to clean names.
- Merges fragmented pain tags (Left/Right/Front/Back) into parent tags and stores the location in the new `mood_activity_details` table.
- Marks duplicated or superseded tags as **deprecated** (they remain in the database but no longer appear in the entry form).

Nothing is deleted. Every historical mood entry keeps its data; only the link now points to the new parent tag plus a `position` value.

## Preconditions

1. Code committed and pulled: `main` includes `db/taxonomy_v2.json`, `scripts/apply_taxonomy_v2.py`, and the additive schema.
2. `sleep_db` container is running.
3. `/srv/shared/backups/` is writable.
4. DS223 and Google offsite scripts are working.

## Step 1 — Pull the code

```bash
cd /srv/sleepwell
git pull --ff-only origin main
```

Verify the taxonomy file matches what you expect:

```bash
jq '.categories, .activities_merge[].into.name' db/taxonomy_v2.json
```

## Step 2 — Restart the backend so the new schema is applied

The backend patches missing columns at startup:

```bash
./scripts/podman-compose-native.sh up -d --build
docker logs --tail 40 sleep_backend | grep -Ei "adding missing|verified"
```

You should see lines about `activities.deprecated_at`, `moods.subjective_sleep_rating`, and table creation for `mood_activity_details`. Nothing else in the database has been changed at this point.

## Step 3 — Take a fresh backup with full offsite replication

```bash
./scripts/run_db_backup_rotation.sh
./scripts/mood_images_backup.sh
./scripts/push_backups_to_synology.sh
./scripts/sync_backups_to_google.sh
./scripts/verify_latest_manifest.sh
```

All must succeed. `verify_latest_manifest.sh` must exit zero.

## Step 4 — Dry-run the taxonomy migration

The script reads `DATABASE_URL` from the backend environment. Simplest is to run it inside the backend container:

```bash
docker exec -i sleep_backend python /app/../scripts/apply_taxonomy_v2.py --verbose
```

If the script is not visible in the container, run from the host with the DB URL from `.env`:

```bash
set -a; source .env; set +a
DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}" \
  python3 scripts/apply_taxonomy_v2.py --verbose
```

Expected output ends with a `Stats:` line summarising what **would** change. Review the log and confirm the counts look right (renames + merges + deprecations).

## Step 5 — Apply the migration

The script refuses to apply unless a fresh `.dump` file is present in `/srv/shared/backups` (default max age 60 minutes). To override for testing only, set `SKIP_BACKUP_GUARD=1` — **do not skip on production**.

```bash
DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}" \
  python3 scripts/apply_taxonomy_v2.py --apply --verbose
```

The whole change runs in one transaction. An audit log is written to `/srv/shared/backups/taxonomy_v2_apply_<UTC-timestamp>.jsonl`.

## Step 6 — Verify

Open the app. In the mood-entry page:

- Deprecated tags no longer appear.
- New parent tags (Headache, Jaw / TMJ Pain, Light Walk, etc.) appear.
- Selecting a position-sensitive tag shows Left / Right / Front / Back-Left / Back-Right / Bilateral pills.
- Selecting `Alcohol` or `Caffeine after 4pm` shows a quantity input.
- The Sleep Rating pill row appears.

Spot-check historical data:

```bash
docker exec -i sleep_db psql -U sleepuser -d sleepdb -c "
SELECT a.name, COUNT(*)
FROM mood_activities ma JOIN activities a ON a.id = ma.activity_id
WHERE a.deprecated_at IS NOT NULL
GROUP BY a.name
ORDER BY 2 DESC
LIMIT 20;
"
```

Expected result: zero rows. If any deprecated activity still has live join rows, the merge did not complete for it — investigate the audit log before making any further changes.

Also confirm position rows were created:

```bash
docker exec -i sleep_db psql -U sleepuser -d sleepdb -c "
SELECT a.name, mad.position, COUNT(*)
FROM mood_activity_details mad JOIN activities a ON a.id = mad.activity_id
GROUP BY a.name, mad.position
ORDER BY 1, 2;
"
```

## Rollback (if needed)

If verification fails and you want to revert to pre-migration state:

```bash
# Stop backend so no new writes happen
./scripts/podman-compose-native.sh stop backend

# Restore the most recent .dump taken in Step 3
NEWEST_DUMP=$(ls -1t /srv/shared/backups/*.dump | head -n1)
docker cp "$NEWEST_DUMP" sleep_db:/tmp/restore.dump
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" sleep_db \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --clean --if-exists /tmp/restore.dump

./scripts/podman-compose-native.sh up -d backend
```

Then investigate before re-attempting the migration.

## Re-running the migration

The script is idempotent. Running it again after success is a no-op that reports zero changes.
