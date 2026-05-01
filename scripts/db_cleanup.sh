#!/usr/bin/env bash
# db_cleanup.sh — Keep only the 2 most recent database backups
#
# This script removes old database backups from /srv/shared/backups to conserve 
# disk space. It keeps the 2 most recent backups and deletes any older ones.
#
# Usage:
#   ./scripts/db_cleanup.sh
#
# Optional arguments:
#   --max-backups N   Keep N backups instead of 2 (default: 2)
#   --dry-run         Show what would be deleted without actually deleting
#
# For automated cleanup, add to crontab:
#   # Delete old backups every Sunday at 2am
#   0 2 * * 0 cd /home/andyl/sleep-wellness-tracker && ./scripts/db_cleanup.sh
#
# Or with a specific path:
#   0 2 * * 0 /home/andyl/sleep-wellness-tracker/scripts/db_cleanup.sh --max-backups 3

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

BACKUP_DIR="/srv/shared/backups"
MAX_BACKUPS=2
DRY_RUN=false

# ── Parse arguments ───────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --max-backups)
            MAX_BACKUPS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            echo "Usage: $0 [--max-backups N] [--dry-run]" >&2
            exit 1
            ;;
    esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[db_cleanup] $*"; }

# ── Verify backup directory exists ────────────────────────────────────────────

[[ -d "$BACKUP_DIR" ]] || die "Backup directory not found: $BACKUP_DIR"

# ── List backups sorted by modification time (newest first) ──────────────────

info "Scanning backups in: $BACKUP_DIR"

# Find all .dump and .sql.gz files, sorted by modification time (newest first)
mapfile -t backup_files < <(find "$BACKUP_DIR" -maxdepth 1 \( -name "*.dump" -o -name "*.sql.gz" \) -type f -printf '%T@ %p\n' | sort -rn | awk '{print $2}')

total_backups="${#backup_files[@]}"
info "Found $total_backups backup files."

if (( total_backups <= MAX_BACKUPS )); then
    info "Current backup count ($total_backups) is at or below limit ($MAX_BACKUPS). No cleanup needed."
    exit 0
fi

# ── Calculate which backups to delete ──────────────────────────────────────────

to_delete_count=$((total_backups - MAX_BACKUPS))
info "Keeping: $MAX_BACKUPS newest backups"
info "Deleting: $to_delete_count older backups"
info ""

# ── Delete old backups ────────────────────────────────────────────────────────

deleted_count=0
for ((i = MAX_BACKUPS; i < total_backups; i++)); do
    file="${backup_files[$i]}"
    file_size=$(du -h "$file" | cut -f1)
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would delete: $(basename "$file")  ($file_size)"
    else
        info "Deleting: $(basename "$file")  ($file_size)"
        rm -f "$file"
        deleted_count=$((deleted_count + 1))
    fi
done

# ── Report ────────────────────────────────────────────────────────────────────

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
    info "Dry run complete. No files were deleted."
else
    info "Cleanup complete. Deleted $deleted_count backup file(s)."
fi

# ── Show remaining backups ────────────────────────────────────────────────────

info ""
info "Remaining backups:"
remaining_files=("${backup_files[@]:0:MAX_BACKUPS}")
for file in "${remaining_files[@]}"; do
    file_size=$(du -h "$file" | cut -f1)
    mod_time=$(stat -c %y "$file" | cut -d' ' -f1-2)
    printf "  %-40s  %4s  (%s)\n" "$(basename "$file")" "$file_size" "$mod_time"
done
