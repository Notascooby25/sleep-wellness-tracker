#!/usr/bin/env bash
# mood_images_verify_hook.sh — run verification and append alert events to a hook log.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_SCRIPT="${VERIFY_SCRIPT:-$SCRIPT_DIR/mood_images_verify.sh}"
HOOK_LOG="${HOOK_LOG:-/srv/shared/backups/mood_images_hook.log}"
MISSING_SNAPSHOT_DIR="${MISSING_SNAPSHOT_DIR:-/srv/shared/backups/mood-images/missing-reports}"

mkdir -p "$(dirname "$HOOK_LOG")" "$MISSING_SNAPSHOT_DIR"

tmp_output="$(mktemp)"
trap 'rm -f "$tmp_output"' EXIT

set +e
STRICT=0 "$VERIFY_SCRIPT" 2>&1 | tee "$tmp_output"
verify_rc=${PIPESTATUS[0]}
set -e

unexpected_count="$(awk -F': ' '/Newly missing files:/ {print $2}' "$tmp_output" | tail -n 1)"
unexpected_count="${unexpected_count:-0}"
accepted_count="$(awk -F': ' '/Accepted missing files:/ {print $2}' "$tmp_output" | tail -n 1)"
accepted_count="${accepted_count:-0}"

ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ "$verify_rc" -ne 0 ]]; then
  echo "$ts ERROR verify_failed rc=$verify_rc" | tee -a "$HOOK_LOG"
  exit "$verify_rc"
fi

if [[ "$unexpected_count" =~ ^[0-9]+$ ]] && (( unexpected_count > 0 )); then
  report_path="$MISSING_SNAPSHOT_DIR/missing_${ts//[:]/-}.log"
  awk 'f{print} /First missing entries:/{f=1; next}' "$tmp_output" > "$report_path"
  echo "$ts ALERT new_missing_files=$unexpected_count accepted_missing_files=$accepted_count report=$report_path" | tee -a "$HOOK_LOG"
  exit 2
fi

echo "$ts OK new_missing_files=0 accepted_missing_files=$accepted_count" | tee -a "$HOOK_LOG"
