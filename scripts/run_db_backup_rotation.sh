#!/usr/bin/env bash
# Run a database backup and then enforce retention.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

MAX_BACKUPS="${MAX_BACKUPS:-4}"
BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups}"

# Cron doesn't load .env, so read HEALTHCHECK_URL from it unless the caller already set one.
# Only this one key is parsed; the file is never sourced.
if [[ -z "${HEALTHCHECK_URL:-}" && -f "$ROOT_DIR/.env" ]]; then
    while IFS='=' read -r key value || [[ -n "$key" ]]; do
        [[ "$key" == "HEALTHCHECK_URL" ]] || continue
        value="${value%%[[:space:]]#*}"              # strip a trailing " # comment"
        value="${value%"${value##*[![:space:]]}"}"   # rtrim
        value="${value#\"}" value="${value%\"}"
        value="${value#\'}" value="${value%\'}"
        HEALTHCHECK_URL="$value"
    done < "$ROOT_DIR/.env"
fi

"$ROOT_DIR/scripts/db_backup.sh"
"$ROOT_DIR/scripts/db_cleanup.sh" --backup-dir "$BACKUP_DIR" --max-backups "$MAX_BACKUPS"

# ── create a checksum manifest for the produced snapshots and archives ──
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MANIFEST_FILE="$BACKUP_DIR/manifest_${TIMESTAMP}.sha256"

# ── backup garmin tokens ──
GARMIN_TOKENS_DIR="/srv/shared/garmin-tokens"
if [[ -d "$GARMIN_TOKENS_DIR" ]]; then
    GARMIN_ARCHIVE="$BACKUP_DIR/garmin_tokens_${TIMESTAMP}.tar.gz"
    tar -czf "$GARMIN_ARCHIVE" -C "$(dirname "$GARMIN_TOKENS_DIR")" "$(basename "$GARMIN_TOKENS_DIR")" || true
    echo "[run_db_backup_rotation] Garmin tokens backed up: $GARMIN_ARCHIVE"
fi

# Find top-level db dumps, gzipped SQL files, garmin tokens and checksum them.
# Use find + sort to produce stable ordering.
{
  find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.dump' -o -name '*.sql.gz' -o -name 'garmin_tokens_*.tar.gz' \) -print0 | sort -z | xargs -0 sha256sum 2>/dev/null || true

  # Include mood-image archives if present
  if [[ -d "/srv/shared/backups/mood-images" ]]; then
    find /srv/shared/backups/mood-images -type f -name '*.tar.gz' -print0 | sort -z | xargs -0 sha256sum 2>/dev/null || true
  fi
} > "$MANIFEST_FILE" || true

# Make the manifest readable by the backup user only
chmod 600 "$MANIFEST_FILE" || true

echo "[run_db_backup_rotation] Manifest created: $MANIFEST_FILE"

# ── cleanup old garmin tokens and manifests ──
# Keep only MAX_BACKUPS of garmin_tokens and manifests
# `|| true`: with pipefail, an unmatched glob (ls exits 2) would otherwise abort the script before the ping.
ls -1t "$BACKUP_DIR"/garmin_tokens_*.tar.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -f || true
ls -1t "$BACKUP_DIR"/manifest_*.sha256 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -f || true

# ── send healthchecks.io ping ──
if [[ -n "${HEALTHCHECK_URL:-}" ]]; then
    curl -fsS -m 10 --retry 3 "${HEALTHCHECK_URL}" >/dev/null 2>&1 || echo "[run_db_backup_rotation] Warning: Failed to ping HEALTHCHECK_URL"
fi
