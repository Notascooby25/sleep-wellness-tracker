#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 <local-manifest-path> <remote-manifest-remote>
Example: $0 /srv/shared/backups/manifest_20260819T020000Z.sha256 gdrive-crypt:backups/sleep-wellness/manifest_20260819T020000Z.sha256

This script downloads the remote manifest via rclone and diffs it against the local manifest. Exits 0 on success, non-zero on mismatch.
EOF
}

if [[ "$#" -lt 2 ]]; then
  usage
  exit 2
fi

LOCAL_MANIFEST="$1"
REMOTE_MANIFEST_REMOTE="$2"
RCLONE_CONF="${RCLONE_CONF:-${XDG_CONFIG_HOME:-$HOME/.config}/rclone/rclone.conf}"

if [[ ! -f "$LOCAL_MANIFEST" ]]; then
  echo "Local manifest not found: $LOCAL_MANIFEST" >&2
  exit 3
fi

TMP_REMOTE="$(mktemp /tmp/remote_manifest.XXXXXX)"
cleanup() { rm -f "$TMP_REMOTE"; }
trap cleanup EXIT

# Fetch remote manifest to temporary file
if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone not found in PATH" >&2
  exit 4
fi

echo "[verify_remote_manifest] Downloading remote manifest: $REMOTE_MANIFEST_REMOTE"
rclone copyto "$REMOTE_MANIFEST_REMOTE" "$TMP_REMOTE" --config "$RCLONE_CONF"

echo "[verify_remote_manifest] Comparing local and remote manifests"
if ! diff -u "$LOCAL_MANIFEST" "$TMP_REMOTE"; then
  echo "[verify_remote_manifest] Manifest verification FAILED" >&2
  exit 5
fi

echo "[verify_remote_manifest] Manifest verification succeeded"
exit 0
