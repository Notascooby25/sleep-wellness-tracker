#!/usr/bin/env bash
# mood_images_backup.sh — archive mood image files with retention and checksums.

set -euo pipefail

SOURCE_DIR="${SOURCE_DIR:-/srv/shared/mood-images/mood_images}"
BACKUP_DIR="${BACKUP_DIR:-/srv/shared/backups/mood-images}"
MAX_BACKUPS="${MAX_BACKUPS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE_BASENAME="mood_images_${STAMP}.tar.gz"
ARCHIVE_PATH="$BACKUP_DIR/$ARCHIVE_BASENAME"
SHA_PATH="$ARCHIVE_PATH.sha256"
LOCK_PATH="$BACKUP_DIR/.mood_images_backup.lock"

log() { echo "[mood_images_backup] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

[[ -d "$SOURCE_DIR" ]] || die "Source directory not found: $SOURCE_DIR"
mkdir -p "$BACKUP_DIR"

exec 9>"$LOCK_PATH"
if ! flock -n 9; then
  die "Another mood image backup process is running"
fi

tmp_archive="$ARCHIVE_PATH.tmp"
tmp_sha="$SHA_PATH.tmp"

log "Creating archive: $ARCHIVE_PATH"
# Store only file names in root of archive for easy restore to SOURCE_DIR.
tar -C "$SOURCE_DIR" -czf "$tmp_archive" .

tar -tzf "$tmp_archive" >/dev/null
sha256sum "$tmp_archive" > "$tmp_sha"

mv "$tmp_archive" "$ARCHIVE_PATH"
mv "$tmp_sha" "$SHA_PATH"

count_files="$(find "$SOURCE_DIR" -maxdepth 1 -type f | wc -l | tr -d ' ')"
archive_size="$(du -sh "$ARCHIVE_PATH" | awk '{print $1}')"
log "Backup complete: files=$count_files archive_size=$archive_size"

mapfile -t archives < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'mood_images_*.tar.gz' -printf '%f\n' | sort -r)
if (( ${#archives[@]} > MAX_BACKUPS )); then
  for old in "${archives[@]:MAX_BACKUPS}"; do
    log "Pruning old backup: $old"
    rm -f "$BACKUP_DIR/$old" "$BACKUP_DIR/$old.sha256"
  done
fi

log "Done"
