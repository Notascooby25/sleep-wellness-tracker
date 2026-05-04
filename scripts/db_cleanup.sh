#!/usr/bin/env bash
# db_cleanup.sh — Keep only the N most recent database backup snapshots
#
# A backup snapshot is identified by files that share the same timestamp stem,
# e.g. sleepdb_20260504T120000Z.dump + sleepdb_20260504T120000Z.sql.gz.
#
# Usage:
#   ./scripts/db_cleanup.sh
#
# Optional arguments:
#   --backup-dir PATH  Backup directory (default: /srv/shared/backups)
#   --max-backups N    Keep N most recent snapshots (default: 4)
#   --dry-run          Show what would be deleted without deleting

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

BACKUP_DIR="/srv/shared/backups"
MAX_BACKUPS=4
DRY_RUN=false

# ── Parse arguments ───────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --max-backups)
            MAX_BACKUPS="$2"
            shift 2
            ;;
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            echo "Usage: $0 [--backup-dir PATH] [--max-backups N] [--dry-run]" >&2
            exit 1
            ;;
    esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[db_cleanup] $*"; }

[[ "$MAX_BACKUPS" =~ ^[0-9]+$ ]] || die "--max-backups must be a non-negative integer"

# ── Verify backup directory exists ────────────────────────────────────────────

[[ -d "$BACKUP_DIR" ]] || die "Backup directory not found: $BACKUP_DIR"

# ── Build snapshot map from backup files ─────────────────────────────────────

info "Scanning backups in: $BACKUP_DIR"

declare -A snapshot_latest_ts=()
declare -A snapshot_files=()

while IFS= read -r file; do
    filename="$(basename "$file")"

    snapshot_id=""
    if [[ "$filename" =~ ^(.+_[0-9]{8}T[0-9]{6}Z)\.dump$ ]]; then
        snapshot_id="${BASH_REMATCH[1]}"
    elif [[ "$filename" =~ ^(.+_[0-9]{8}T[0-9]{6}Z)\.sql\.gz$ ]]; then
        snapshot_id="${BASH_REMATCH[1]}"
    else
        continue
    fi

    modified_ts="$(stat -c %Y "$file")"

    if [[ -z "${snapshot_latest_ts[$snapshot_id]:-}" ]] || (( modified_ts > snapshot_latest_ts[$snapshot_id] )); then
        snapshot_latest_ts[$snapshot_id]="$modified_ts"
    fi

    if [[ -n "${snapshot_files[$snapshot_id]:-}" ]]; then
        snapshot_files[$snapshot_id]+=$'\n'"$file"
    else
        snapshot_files[$snapshot_id]="$file"
    fi
done < <(find "$BACKUP_DIR" -maxdepth 1 \( -name "*.dump" -o -name "*.sql.gz" \) -type f)

snapshot_count="${#snapshot_latest_ts[@]}"
info "Found $snapshot_count backup snapshot(s)."

if (( snapshot_count <= MAX_BACKUPS )); then
    info "Current snapshot count ($snapshot_count) is at or below limit ($MAX_BACKUPS). No cleanup needed."
    exit 0
fi

# ── Sort snapshots by newest first ───────────────────────────────────────────

mapfile -t ordered_snapshots < <(
    for snapshot_id in "${!snapshot_latest_ts[@]}"; do
        printf '%s %s\n' "${snapshot_latest_ts[$snapshot_id]}" "$snapshot_id"
    done | sort -rn | awk '{print $2}'
)

to_delete_snapshots=$((snapshot_count - MAX_BACKUPS))
info "Keeping: $MAX_BACKUPS newest snapshot(s)"
info "Deleting: $to_delete_snapshots older snapshot(s)"
echo ""

# ── Delete files that belong to old snapshots ───────────────────────────────

deleted_snapshot_count=0
deleted_count=0
for ((i = MAX_BACKUPS; i < snapshot_count; i++)); do
    snapshot_id="${ordered_snapshots[$i]}"
    deleted_snapshot_count=$((deleted_snapshot_count + 1))

    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        file_size="$(du -h "$file" | cut -f1)"

        if [[ "$DRY_RUN" == "true" ]]; then
            info "[DRY RUN] Would delete: $(basename "$file")  ($file_size)"
        else
            info "Deleting: $(basename "$file")  ($file_size)"
            rm -f "$file"
            deleted_count=$((deleted_count + 1))
        fi
    done <<< "${snapshot_files[$snapshot_id]}"
done

# ── Report ────────────────────────────────────────────────────────────────────

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
    info "Dry run complete. No files were deleted."
else
    info "Cleanup complete. Deleted $deleted_count backup file(s) across $deleted_snapshot_count snapshot(s)."
fi

# ── Show remaining snapshots ─────────────────────────────────────────────────

info ""
info "Remaining snapshot(s):"
for ((i = 0; i < MAX_BACKUPS && i < snapshot_count; i++)); do
    snapshot_id="${ordered_snapshots[$i]}"
    mod_time="$(date -u -d "@${snapshot_latest_ts[$snapshot_id]}" +%Y-%m-%dT%H:%M:%SZ)"
    file_count="$(wc -l <<< "${snapshot_files[$snapshot_id]}" | xargs)"
    printf "  %-32s  files=%s  (%s)\n" "$snapshot_id" "$file_count" "$mod_time"
done
