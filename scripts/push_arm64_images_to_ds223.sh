#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

: "${DS223_HOST:?Set DS223_HOST, e.g. DS223_HOST=192.168.68.107}"
DS223_USER="${DS223_USER:-admin}"
DS223_PORT="${DS223_PORT:-8022}"
DS223_SSH_TARGET="${DS223_USER}@${DS223_HOST}"
SSH_CONTROL_PATH="${SSH_CONTROL_PATH:-$HOME/.ssh/cm-%r@%h:%p}"

SSH_BASE_ARGS=(
  -p "$DS223_PORT"
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o "ControlPath=$SSH_CONTROL_PATH"
)

BACKEND_IMAGE="${BACKEND_IMAGE:-sleep-wellness-tracker-backend:arm64}"
FRONTEND_WEB_IMAGE="${FRONTEND_WEB_IMAGE:-sleep-wellness-tracker-frontend-web:arm64}"
BACKEND_LATEST="${BACKEND_LATEST:-sleep-wellness-tracker-backend:latest}"
FRONTEND_WEB_LATEST="${FRONTEND_WEB_LATEST:-sleep-wellness-tracker-frontend-web:latest}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/dist}"
SKIP_BUILD="${SKIP_BUILD:-0}"
REMOTE_DIR="${REMOTE_DIR:-/tmp/sleepwell-images}"

BACKEND_TAR="$OUTPUT_DIR/sleep-wellness-tracker-backend-arm64.tar"
FRONTEND_WEB_TAR="$OUTPUT_DIR/sleep-wellness-tracker-frontend-web-arm64.tar"

if [[ "$SKIP_BUILD" != "1" ]]; then
  "$SCRIPT_DIR/build_arm64_images.sh"
fi

if [[ ! -f "$BACKEND_TAR" || ! -f "$FRONTEND_WEB_TAR" ]]; then
  echo "Expected tar files not found in $OUTPUT_DIR" >&2
  echo "Run scripts/build_arm64_images.sh first or unset SKIP_BUILD." >&2
  exit 1
fi

echo "Creating remote temp dir: $REMOTE_DIR"
ssh "${SSH_BASE_ARGS[@]}" "$DS223_SSH_TARGET" "mkdir -p '$REMOTE_DIR'"

echo "Copying ARM64 image tar files to DS223"
scp -P "$DS223_PORT" -o ControlMaster=auto -o ControlPersist=5m -o "ControlPath=$SSH_CONTROL_PATH" "$BACKEND_TAR" "$FRONTEND_WEB_TAR" "$DS223_SSH_TARGET:$REMOTE_DIR/"

echo "Loading images on DS223 and tagging as :latest"
ssh "${SSH_BASE_ARGS[@]}" "$DS223_SSH_TARGET" "
set -euo pipefail
podman load -i '$REMOTE_DIR/$(basename "$BACKEND_TAR")'
podman load -i '$REMOTE_DIR/$(basename "$FRONTEND_WEB_TAR")'
podman tag '$BACKEND_IMAGE' '$BACKEND_LATEST'
podman tag '$FRONTEND_WEB_IMAGE' '$FRONTEND_WEB_LATEST'
podman image ls --format '{{.Repository}}:{{.Tag}}' | grep -E 'sleep-wellness-tracker-(backend|frontend-web):'
"

echo "Done. Images are loaded on DS223 as:"
echo "  $BACKEND_LATEST"
echo "  $FRONTEND_WEB_LATEST"
echo "Now run compose on DS223 with --no-build to use prebuilt images."
