# Restore Drill Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/test_restore_dump.sh` a drill that fails on any restore problem, uses the production Postgres major version, and is itself covered by a hermetic fixture test that runs in CI.

**Architecture:** Keep the script's flow (throwaway Postgres container, copy newest dump in, `pg_restore`, sanity queries, tear down). Tighten it: restore errors fail the drill, the restored table set must match the dump's table list, key tables must be non-empty, the dump must be recent, and, when the live database container is running, the restored row counts must be within a band of live. Cover it with a fixture test using a stub `docker` on PATH, in the style of the existing `scripts/tests/test_sync_backups_to_google.sh`.

**Tech Stack:** bash, GNU coreutils, Docker (stubbed in tests), existing `scripts/tests/lib.sh` (`check`, `has`, `hasnt`, `summary`).

**Spec:** Phase 1 of the owner-approved backup master plan (agreed in chat 2026-11-13, no separate spec file). Behaviour is defined in the tasks below.

## Global Constraints

- Public repo: no hostnames, IP addresses, account names, NAS details or secrets in any file, test fixture or log message.
- The drill must never write to, or restore into, the live database or any live volume. It only talks to its own throwaway container, and reads (never writes) the live container for version and row counts.
- Follow the existing script style: `set -euo pipefail`, `die()` / `log()` helpers, `[test_restore]` log prefix.
- Existing environment variables keep working: `BACKUP_DIR` (default `/srv/shared/backups`).
- New env vars, with these defaults: `PG_IMAGE` (default `postgres:<major of the live container>`, falling back to `postgres:15`), `LIVE_CONTAINER` (default `sleep_db`), `DRILL_MAX_AGE_HOURS` (default `14`), `DRILL_MIN_LIVE_FRACTION` (default `0.9`).
- Tests are hermetic: stubs on PATH, all state in a temp dir removed on exit, nothing touches real Docker.
- This change touches `.github/workflows/build-amd64.yml`. Tell the owner in the PR change record, because a pull request can weaken its own checks.

## Review Focus

- Dump file is empty or not a Postgres archive: drill fails, does not report success.
- `pg_restore` exits non-zero but the sanity queries still return counts: drill fails (the original gap).
- Restored database has fewer tables than the dump lists: drill fails.
- Newest dump is older than the age limit (the backup job has silently stopped): drill fails with a message naming the age.
- Live container is not running (or on another host): live-count comparison is skipped with a log line, the rest still runs.

---

### Task 1: Fixture test for the drill (written first, fails against the current script)

**Files:**
- Create: `scripts/tests/test_restore_dump.sh`
- Test: itself (`bash scripts/tests/test_restore_dump.sh`)

**Interfaces:**
- Consumes: `scripts/tests/lib.sh` helpers; the script under test at `scripts/test_restore_dump.sh`, run with `BACKUP_DIR`, `PG_IMAGE`, `LIVE_CONTAINER`, `DRILL_MAX_AGE_HOURS`, `DRILL_MIN_LIVE_FRACTION` in the environment.
- Produces: a stub `docker` driven by env vars `STUB_RESTORE_RC` (exit code of `pg_restore`), `STUB_MOODS`, `STUB_ACTIVITIES` (counts returned for the restored DB), `STUB_TOC_TABLES` and `STUB_DB_TABLES` (table counts for the dump's TOC and the restored DB), `STUB_LIVE` (`absent` or `moods=<n>,activities=<n>`), and `STUB_LIVE_VERSION` (text returned by `postgres --version` in the live container). Every call is appended to `$T/docker.log`.

- [ ] **Step 1: Write the test file** with these named cases, each using `check` and a `run` helper that sets `RC` and leaves `$T/out.txt` and `$T/docker.log`:
  - `healthy run`: exit 0, output contains `DR Test Passed`, container was stopped (`docker.log` has a `stop` line).
  - `pg_restore fails (exit 1) but counts look fine`: exit 1, output contains `restore`, no `DR Test Passed`.
  - `no dump in BACKUP_DIR`: exit 1, no container started (`docker.log` has no `run` line).
  - `empty dump file`: exit 1.
  - `dump older than limit` (`touch -d '20 hours ago'`, limit 14): exit 1, output contains `old`.
  - `dump within limit` (`touch -d '2 hours ago'`): exit 0.
  - `zero moods` and `zero activities` (two cases): exit 1 each.
  - `restored table count differs from dump table list` (`STUB_TOC_TABLES=12`, `STUB_DB_TABLES=11`): exit 1, output contains `tables`.
  - `live container absent`: exit 0, output contains `skipping live comparison`.
  - `restored moods below 90% of live` (`STUB_LIVE=moods=1000,activities=100`, `STUB_MOODS=800`): exit 1, output contains `live`.
  - `restored moods at 95% of live`: exit 0.
  - `image follows live major version` (`STUB_LIVE_VERSION='postgres (PostgreSQL) 16.2'`, no `PG_IMAGE`): `docker.log` run line contains `postgres:16`.
  - `PG_IMAGE override wins`: `docker.log` run line contains the override value.
  - `fallback image when live container unreadable`: run line contains `postgres:15`.
  - `drill never touches the live container except to read`: `docker.log` has no line where the target is the live container and the subcommand is `stop`, `rm`, `restart` or `cp`.

- [ ] **Step 2: Run it against the current script**

Run: `bash scripts/tests/test_restore_dump.sh`
Expected: FAIL (the `pg_restore fails`, `older than limit`, `table count` and `image follows live` cases fail against the current script). Record the failing case names in the PR change record.

- [ ] **Step 3: Commit the test only**

```bash
git add scripts/tests/test_restore_dump.sh
git commit -m "test(backup): fixture test for restore drill, failing against current script"
```

### Task 2: Harden `scripts/test_restore_dump.sh`

**Files:**
- Modify: `scripts/test_restore_dump.sh`

**Interfaces:**
- Consumes: the env vars and stub behaviour defined in Task 1.
- Produces: unchanged CLI (no arguments), exit 0 only on full success, `[test_restore]` prefixed output, final line `DR Test Passed successfully. Backups are healthy.`

- [ ] **Step 1: Resolve the image.** Add `resolve_image()` that returns `$PG_IMAGE` if set, else `postgres:<major>` parsed from `docker exec "$LIVE_CONTAINER" postgres --version`, else `postgres:15`. Log which image and why.

- [ ] **Step 2: Check the dump before starting a container.** Fail (no container started) if the newest `*.dump` is empty, or older than `DRILL_MAX_AGE_HOURS` (age from file mtime; message `Newest dump <name> is <N>h old (limit <M>h)`).

- [ ] **Step 3: Make restore errors fatal.** Remove `|| true` after `pg_restore`; add `--exit-on-error`; on failure `die "pg_restore failed ..."`. Capture the dump's table count with `pg_restore -l` inside the container (count of `TABLE ` entries, excluding `TABLE DATA`).

- [ ] **Step 4: Sanity checks.** After restore: restored base-table count in schema `public` must equal the dump's table count (`die` naming both numbers and the word `tables`); `moods` and `activities` counts must be non-zero (replace the `|| echo '0'` fallbacks with a real failure on query error).

- [ ] **Step 5: Live comparison.** If `LIVE_CONTAINER` is running, read live `moods` and `activities` counts (read-only `psql -Atc "SELECT COUNT(*) ..."`); fail when a restored count is below `DRILL_MIN_LIVE_FRACTION` of live. If not running, log `skipping live comparison (live container not running)` and continue. Reading live credentials: the script must not source or print any env file; use the live container's own environment via `docker exec "$LIVE_CONTAINER" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "..."'`.

- [ ] **Step 6: Run the fixture test**

Run: `bash scripts/tests/test_restore_dump.sh`
Expected: `passed=<all> failed=0`

- [ ] **Step 7: Lint**

Run: `shellcheck scripts/test_restore_dump.sh scripts/tests/test_restore_dump.sh` (if shellcheck is installed; otherwise `bash -n` on both and say shellcheck was not run).
Expected: no findings.

- [ ] **Step 8: Commit**

```bash
git add scripts/test_restore_dump.sh
git commit -m "fix(backup): restore drill fails on restore errors, checks tables, age and live counts"
```

### Task 3: Run script tests in CI, update docs

**Files:**
- Modify: `.github/workflows/build-amd64.yml` (the `Run script tests` step, currently one line running `test_preview.sh`)
- Modify: `docs/backup-runbook.md` (restore-drill section), `docs/nuc-backup-overview.md` (section 7 "Checking health")

**Interfaces:**
- Consumes: the test files in `scripts/tests/`.
- Produces: CI runs `test_preview.sh`, `test_restore_dump.sh`, `test_sync_backups_to_google.sh` and `test_host_config_and_cron.sh`.

- [ ] **Step 1: Run the two existing but un-run script tests locally**

Run: `bash scripts/tests/test_sync_backups_to_google.sh && bash scripts/tests/test_host_config_and_cron.sh`
Expected: `failed=0` on both. If either fails today, stop and tell the owner before wiring them into CI.

- [ ] **Step 2: Edit the CI step** so it runs all four script tests (one `run: |` block, each command on its own line, job fails if any fails).

- [ ] **Step 3: Update the two docs**: new env vars and defaults, what the drill now checks, expected `DR Test Passed` output, and that the age limit default (14h) is tightened to 8h when the dump moves to 6-hourly.

- [ ] **Step 4: Run everything CI runs**

Run: `cd backend && TEST_DATABASE_URL=<throwaway postgres url> pytest tests -q`; then the four script tests; then the repo linter used by the `lint` job.
Expected: all pass. Paste the last lines of each into the PR.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/build-amd64.yml docs/backup-runbook.md docs/nuc-backup-overview.md
git commit -m "ci(backup): run backup script tests in CI; document hardened restore drill"
```

### After merge (owner steps, separate approval)

- On the live server: `git pull` in the sleepwell checkout, then run `./scripts/test_restore_dump.sh`. Expect `DR Test Passed` and the new check lines (image `postgres:15`, table counts match, live comparison within band).
