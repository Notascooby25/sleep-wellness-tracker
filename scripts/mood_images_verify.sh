#!/usr/bin/env bash
# mood_images_verify.sh — verify mood image directory and check DB-referenced image files.

set -euo pipefail

SOURCE_DIR="${SOURCE_DIR:-/srv/shared/mood-images/mood_images}"
CONTAINER="${CONTAINER:-sleep_db}"
RUNTIME="${RUNTIME:-docker}"
STRICT="${STRICT:-1}"
ACCEPTED_MISSING_FILE="${ACCEPTED_MISSING_FILE:-$(dirname "$SOURCE_DIR")/accepted_missing_images.txt}"
WRITE_ACCEPTED_BASELINE="${WRITE_ACCEPTED_BASELINE:-0}"

log() { echo "[mood_images_verify] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

[[ -d "$SOURCE_DIR" ]] || die "Source directory not found: $SOURCE_DIR"

if ! findmnt -T "$SOURCE_DIR" >/dev/null 2>&1; then
  die "Could not resolve mount for $SOURCE_DIR"
fi

source_count="$(find "$SOURCE_DIR" -maxdepth 1 -type f | wc -l | tr -d ' ')"
log "Current image files on disk: $source_count"

if ! command -v "$RUNTIME" >/dev/null 2>&1; then
  die "Container runtime '$RUNTIME' not found"
fi

if ! "$RUNTIME" inspect --format '{{.State.Status}}' "$CONTAINER" 2>/dev/null | grep -q "running"; then
  die "Container '$CONTAINER' is not running"
fi

tmp_expected="$(mktemp)"
tmp_missing="$(mktemp)"
tmp_accepted="$(mktemp)"
tmp_unexpected="$(mktemp)"
trap 'rm -f "$tmp_expected" "$tmp_missing" "$tmp_accepted" "$tmp_unexpected"' EXIT

"$RUNTIME" exec "$CONTAINER" psql -U sleepuser -d sleepdb -Atc "
with urls as (
  select image_url as u from moods where image_url is not null
  union all
  select jsonb_array_elements_text(image_urls::jsonb) as u
  from moods
  where image_urls is not null and jsonb_typeof(image_urls::jsonb)='array'
)
select distinct regexp_replace(u,'^/mood/image/','')
from urls
where u like '/mood/image/%'
order by 1;
" > "$tmp_expected"

expected_count="$(wc -l < "$tmp_expected" | tr -d ' ')"
log "DB-referenced image files: $expected_count"

while IFS= read -r fname; do
  [[ -z "$fname" ]] && continue
  if [[ ! -f "$SOURCE_DIR/$fname" ]]; then
    echo "$fname" >> "$tmp_missing"
  fi
done < "$tmp_expected"

missing_count="$(wc -l < "$tmp_missing" | tr -d ' ')"
if [[ "$WRITE_ACCEPTED_BASELINE" == "1" ]]; then
  [[ ! -e "$ACCEPTED_MISSING_FILE" ]] || die "Accepted-missing baseline already exists: $ACCEPTED_MISSING_FILE"
  install -Dm 600 "$tmp_missing" "$ACCEPTED_MISSING_FILE"
  log "Created accepted-missing baseline: $ACCEPTED_MISSING_FILE ($missing_count file(s))"
fi

if [[ -f "$ACCEPTED_MISSING_FILE" ]]; then
  grep -Fxf "$ACCEPTED_MISSING_FILE" "$tmp_missing" > "$tmp_accepted" || true
  grep -Fvxf "$ACCEPTED_MISSING_FILE" "$tmp_missing" > "$tmp_unexpected" || true
fi

accepted_count="$(wc -l < "$tmp_accepted" | tr -d ' ')"
unexpected_count="$(wc -l < "$tmp_unexpected" | tr -d ' ')"
log "Accepted missing files: $accepted_count"

if (( unexpected_count > 0 )); then
  log "Newly missing files: $unexpected_count"
  log "First missing entries:"
  sed -n '1,20p' "$tmp_unexpected"
  if [[ "$STRICT" == "1" ]]; then
    exit 2
  fi
else
  log "No newly missing files detected"
fi

log "Done"
