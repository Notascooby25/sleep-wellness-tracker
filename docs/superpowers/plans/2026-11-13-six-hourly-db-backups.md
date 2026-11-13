# Six-Hourly Database Backups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the sleepwell database backup from every 12 hours to every 6 hours (maximum 6 hours of recent data lost), keep the same seven days of local history, and make the freshness alarms match the new cadence.

**Architecture:** Change defaults and limits in the existing scripts rather than adding new machinery. The cron installer and the rotation script default to a 6-hourly schedule keeping 28 snapshots. The plain-SQL copy (for human inspection) is made once per day instead of on every run, so storage grows only by the extra `.dump` files. The Google upload's freshness check and the restore drill's age limit are tightened so a single missed dump is reported. Hermetic fixture tests cover each change; the live crontab change is a separate, owner-approved rollout step.

**Tech Stack:** bash, GNU coreutils, cron, existing `scripts/tests/lib.sh` helpers, stub `docker` (as in `scripts/tests/test_restore_dump.sh`).

**Spec:** Owner decision 2026-11-13: accept losing up to 6 hours of data for the sleep tracker and the audio scrobbler. This plan covers the sleep tracker only; the audio scrobbler already dumps every 6 hours in its own repo.

## Global Constraints

- Public repo: no hostnames, IP addresses, account names, NAS details or secrets in any file, fixture or log message.
- Defaults after this change: schedule `0 */6 * * *`, `MAX_BACKUPS` 28 snapshots (seven days at four per day), plain-SQL copy at most once per 20 hours, `FRESH_DB_HOURS` 4, `DRILL_MAX_AGE_HOURS` 8. Every value stays overridable by the existing environment variables.
- A failed dump must never trigger pruning of older snapshots (existing behaviour, `set -e` order in `run_db_backup_rotation.sh`; must stay true).
- The mood-image archive (`:15`), NAS mirror (`:30`), Google upload (`:35`) and manifest verify (`:50`) cron minutes stay as they are; the dump runs at `:00` so each downstream job sees a fresh dump 15 to 50 minutes later.
- No change to the backend image or to application code.
- Touches `.github/workflows/build-amd64.yml` (adds one test). Tell the owner in the PR change record.

## Review Focus

- Running `run_db_backup_rotation.sh` by hand with no `MAX_BACKUPS` set must not prune below the live retention (28), not the old default of 4.
- Plain-SQL gating: no `.sql.gz` at all, one younger than 20 hours, and one older than 20 hours each behave correctly; a failed `pg_dump` leaves no partial `.sql.gz`.
- A newest dump 6.6 hours old (one missed run, seen by the 35-minute-past Google check) is reported stale; one 3 hours old is fine; `FRESH_DB_HOURS=0` still disables the check.
- Re-running the cron installer replaces the old 12-hourly line, keeps unrelated jobs, and is idempotent.
- Snapshots that hold only a `.dump` (no `.sql.gz`) are counted and pruned correctly by `db_cleanup.sh`.

## Not in this plan (decided separately)

- **Automatic dump before each deploy.** The backend image has no `pg_dump`, so a Watchtower pre-update hook cannot take one without adding `postgresql-client` to the image (a new dependency and an image change). This plan documents a manual step instead (Task 4). The image change can be planned on its own if wanted.
- **Tiered retention on Google Drive and the NAS.** At six-hourly the extra storage is about 10 MB per day. Tiering is deferred until real usage figures are measured.

---

### Task 1: Defaults for the cron installer and rotation script

**Files:**
- Modify: `scripts/setup_db_backup_cron.sh` (defaults at lines 10-11)
- Modify: `scripts/run_db_backup_rotation.sh` (`MAX_BACKUPS` default, line 10)
- Create: `scripts/tests/test_db_backup_schedule.sh`

**Interfaces:**
- Consumes: `scripts/tests/lib.sh` (`check`, `has`, `hasnt`, `count`, `summary`); a stub `crontab` on PATH that reads and writes a file in the temp dir.
- Produces: installer defaults `SCHEDULE="0 */6 * * *"`, `MAX_BACKUPS=28`; rotation default `MAX_BACKUPS=28`. Test helpers `fake_repo()` (temp copy of `scripts/` with stub `db_backup.sh`) reused by Task 2.

- [ ] **Step 1: Write the failing test** `scripts/tests/test_db_backup_schedule.sh` with these named cases:
  - `installer default line is 6-hourly with 28 snapshots`: empty crontab, run installer with no env, crontab holds `0 */6 * * * MAX_BACKUPS=28 BACKUP_DIR=... run_db_backup_rotation.sh >> ...`.
  - `installer replaces an existing 12-hourly line`: crontab holds the old `0 */12 ... MAX_BACKUPS=14 ...` line plus an unrelated job; afterwards exactly one rotation line (the 6-hourly one) and the unrelated job remains.
  - `installer is idempotent`: second run leaves the crontab byte-identical.
  - `SCHEDULE and MAX_BACKUPS overrides still work`.
  - `rotation with no MAX_BACKUPS keeps 28 snapshots`: temp backup dir with 31 fake snapshots (`sleepdb_<ts>.dump` + `.sql.gz`), stub `db_backup.sh` in a copied scripts dir, real `db_cleanup.sh`; afterwards 28 snapshots remain and the 3 oldest are gone.
  - `rotation honours MAX_BACKUPS=5`.
  - `snapshots holding only a .dump are counted and pruned`: 30 `.dump`-only snapshots, default run leaves 28.
  - `a failing db_backup.sh prunes nothing`: stub exits 1; the 31 snapshots are all still present and the rotation exits non-zero.

- [ ] **Step 2: Run it** — `bash scripts/tests/test_db_backup_schedule.sh`. Expected: FAIL on the three default-value cases (installer default, rotation keeps 28, only-dump pruning); the rest pass or fail only because the new defaults are missing. Record the failing case names.

- [ ] **Step 3: Change the defaults.** In `setup_db_backup_cron.sh` set `MAX_BACKUPS="${MAX_BACKUPS:-28}"` and `SCHEDULE="${SCHEDULE:-0 */6 * * *}"` and update the header comment ("every 6 hours"). In `run_db_backup_rotation.sh` set `MAX_BACKUPS="${MAX_BACKUPS:-28}"`.

- [ ] **Step 4: Run the test** — Expected: `failed=0`.

- [ ] **Step 5: Commit** — `git add scripts/setup_db_backup_cron.sh scripts/run_db_backup_rotation.sh scripts/tests/test_db_backup_schedule.sh` then `git commit -m "feat(backup): six-hourly DB backup defaults, keep 28 snapshots"`.

### Task 2: Plain-SQL copy at most once a day

**Files:**
- Modify: `scripts/db_backup.sh` (the plain-SQL section, currently unconditional)
- Test: `scripts/tests/test_db_backup_schedule.sh` (new section)

**Interfaces:**
- Consumes: Task 1's `fake_repo()`; a stub `docker` driven by `STUB_DUMP_FAIL` (plain-SQL `pg_dump` exits 1 when set) that answers `inspect` with `running` and writes fixed bytes for `pg_dump`.
- Produces: environment variable `PLAIN_SQL` with values `daily` (default), `always`, `never`. `daily` creates the `.sql.gz` only when no `*.sql.gz` in `OUTPUT_DIR` is younger than 20 hours. The custom-format `.dump` is made on every run in every mode.

- [ ] **Step 1: Write the failing tests** (new section in the same file), using a temp `.env` containing `POSTGRES_PASSWORD=x`:
  - `daily: no sql.gz present -> both files written`.
  - `daily: a 2-hour-old sql.gz present -> only the .dump is written`.
  - `daily: a 25-hour-old sql.gz present -> both written`.
  - `always: both files written even with a fresh sql.gz`.
  - `never: only the .dump is written`.
  - `invalid PLAIN_SQL value -> exit 1 with a message naming the variable`.
  - `plain-SQL pg_dump failing leaves no partial .sql.gz and no .tmp file` (`STUB_DUMP_FAIL=1`; exit non-zero).
  - `the .dump is non-empty and was written before the plain copy was attempted`.

- [ ] **Step 2: Run** — Expected: FAIL (today the `.sql.gz` is always written, and `PLAIN_SQL` is unknown).

- [ ] **Step 3: Implement** the gate in `db_backup.sh`: read `PLAIN_SQL` (default `daily`, validate), and when it is `daily` look for `find "$OUTPUT_DIR" -maxdepth 1 -name '*.sql.gz' -mmin -1200` (20 hours) to decide; skip the plain-SQL block and log which mode skipped it. Keep the existing temp-file-then-rename behaviour for the copy that is made.

- [ ] **Step 4: Run** — Expected: `failed=0`.

- [ ] **Step 5: Commit** — `git add scripts/db_backup.sh scripts/tests/test_db_backup_schedule.sh` then `git commit -m "feat(backup): plain-SQL copy once a day, custom dump every run"`.

### Task 3: Freshness and drill limits match the new cadence

**Files:**
- Modify: `scripts/sync_backups_to_google.sh` (`FRESH_DB_HOURS` default 26 -> 4, header comment)
- Modify: `scripts/test_restore_dump.sh` (`DRILL_MAX_AGE_HOURS` default 14 -> 8, header comment)
- Modify: `scripts/tests/test_sync_backups_to_google.sh` (cases that encode the 26-hour limit) and `scripts/tests/test_restore_dump.sh` (cases that encode the 14-hour limit)

**Interfaces:**
- Consumes: existing fixtures `fresh_fixture` and `run` in both test files.
- Produces: new defaults as in Global Constraints; no new variables.

- [ ] **Step 1: Update the tests first** so they encode the new limits: in the sync test, a DB dump 3 hours old passes, 5 hours old is stale and pings `/fail`, 6.6 hours old (`touch -d '400 minutes ago'`) is stale, and `FRESH_DB_HOURS=0` still disables the check; in the drill test, a 7-hour-old dump passes and a 9-hour-old dump fails with "old". Leave the mood (13h), expense (26h) and host-config (26h) cases unchanged.

- [ ] **Step 2: Run both tests** — Expected: FAIL only on the cases whose result flips with the new limits.

- [ ] **Step 3: Change the two defaults and their comments.**

- [ ] **Step 4: Run both tests** — Expected: `failed=0` on each.

- [ ] **Step 5: Commit** — `git add scripts/sync_backups_to_google.sh scripts/test_restore_dump.sh scripts/tests/test_sync_backups_to_google.sh scripts/tests/test_restore_dump.sh` then `git commit -m "feat(backup): tighten DB freshness and drill age limits for 6-hourly dumps"`.

### Task 4: CI, docs and the manual pre-release step

**Files:**
- Modify: `.github/workflows/build-amd64.yml` (add `test_db_backup_schedule.sh` to the script-test step)
- Modify: `docs/backup-runbook.md`, `docs/backup-deployment-steps.md`, `docs/nuc-backup-overview.md`, `docs/operations-reference.md` (wherever the 12-hourly schedule, 14-snapshot retention, `FRESH_DB_HOURS`, `DRILL_MAX_AGE_HOURS` or the healthchecks.io period are described; find them with `grep -rn -i "12 hours\|every 12\|0 \*/12\|MAX_BACKUPS=14\|26h\|14 hours" docs`)

- [ ] **Step 1:** Add the new test to CI and run all five script tests exactly as CI does; Expected: every `failed=0`.
- [ ] **Step 2:** Update the docs: new schedule and retention, the once-a-day plain-SQL copy, the new freshness and drill limits, and that the sleepwell healthchecks.io check period should be 6 hours with a 1 hour grace. Add a short "Before a release that changes database models or startup migrations, run `./scripts/db_backup.sh` on the server first" note to `operations-reference.md`, with the reason (no automatic pre-deploy dump yet).
- [ ] **Step 3:** Run the full set CI runs: backend tests against a throwaway Postgres, the lint job commands, the five script tests; paste the last lines into the PR.
- [ ] **Step 4: Commit** — `git add .github/workflows/build-amd64.yml docs` then `git commit -m "ci,docs(backup): run schedule test in CI; document six-hourly backups"`.

### Rollout (owner steps after merge; each needs separate approval)

1. Save the current crontab: `crontab -l > ~/crontab-backup-$(date +%Y%m%dT%H%M%S).txt`.
2. Check there is exactly one rotation line and that it uses the checkout path: `crontab -l | grep run_db_backup_rotation.sh` should print one line containing `/srv/sleepwell/scripts/run_db_backup_rotation.sh`. (The installer replaces only a line with that exact path; a line from another path would survive and the two jobs would fight over the lock.)
3. **Take a dump with the current scripts first** (before pulling): `cd /srv/sleepwell && MAX_BACKUPS=14 BACKUP_DIR=/srv/shared/backups ./scripts/run_db_backup_rotation.sh`. This guarantees a fresh dump exists, so the new 4-hour freshness limit cannot trip in the minutes between the pull and the cron switch.
4. Straight afterwards (within ten minutes, steps 3 to 4 back to back): `git pull`, then `./scripts/setup_db_backup_cron.sh`. Confirm `crontab -l | grep -c run_db_backup_rotation.sh` prints `1` and that line starts `0 */6 * * * MAX_BACKUPS=28`.
5. In healthchecks.io set the sleepwell DB check to a 6-hour period with a **2-hour grace** (cron runs on local time, so on the autumn clock change the gap between two runs is 7 real hours).
6. Next day: confirm four dumps in 24 hours, `google_backup_cron.log` ending with four OK lines, and `./scripts/test_restore_dump.sh` passing with the new 8-hour limit.
7. Rollback, undoing exactly what was changed:
   - From the checkout run `SCHEDULE='0 */12 * * *' MAX_BACKUPS=14 ./scripts/setup_db_backup_cron.sh` (it replaces only its own line, so any other cron edits made since are kept). Restore the saved crontab file only if the installer itself fails.
   - Put `FRESH_DB_HOURS=26` in `~/.config/google-sync.env`, and run the drill with `DRILL_MAX_AGE_HOURS=14` while on 12-hourly dumps.
   - Set the healthchecks.io check back to a 12-hour period with a 1-hour grace.
   - Expect the first old-style run to prune 28 snapshots down to 14.
