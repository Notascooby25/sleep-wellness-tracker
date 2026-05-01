#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PLATFORM="${PLATFORM:-arm64}"
BACKEND_IMAGE="${BACKEND_IMAGE:-sleep-wellness-tracker-backend:arm64}"
FRONTEND_WEB_IMAGE="${FRONTEND_WEB_IMAGE:-sleep-wellness-tracker-frontend-web:arm64}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/dist}"
EXPORT_TARS="${EXPORT_TARS:-1}"

# Ensure podman exists
if ! command -v podman >/dev/null 2>&1; then
  echo "ERROR: podman CLI not found" >&2
  exit 1
fi

cd "$ROOT_DIR"

# Ensure qemu registered for podman (one-time)
echo "Registering qemu for cross-arch emulation (may require sudo)..."
sudo podman run --rm --privileged multiarch/qemu-user-static --reset -p yes || true

# Validate Dockerfiles do not force an architecture
for df in backend/Dockerfile frontend-web/Dockerfile; do
  if grep -E -- '--platform=|FROM --platform=' "$df" >/dev/null 2>&1; then
    echo "ERROR: $df contains an explicit platform directive. Remove any '--platform' or 'FROM --platform=...' lines."
    exit 1
  fi
done

echo "Building backend image for $PLATFORM -> $BACKEND_IMAGE"
podman build --arch "$PLATFORM" -t "$BACKEND_IMAGE" -f backend/Dockerfile backend

echo "Building frontend-web image for $PLATFORM -> $FRONTEND_WEB_IMAGE"
podman build --arch "$PLATFORM" -t "$FRONTEND_WEB_IMAGE" -f frontend-web/Dockerfile frontend-web

if [[ "$EXPORT_TARS" == "1" ]]; then
  mkdir -p "$OUTPUT_DIR"
  BACKEND_TAR="$OUTPUT_DIR/sleep-wellness-tracker-backend-arm64.tar"
  FRONTEND_WEB_TAR="$OUTPUT_DIR/sleep-wellness-tracker-frontend-web-arm64.tar"

  echo "Exporting $BACKEND_IMAGE -> $BACKEND_TAR"
  podman save -o "$BACKEND_TAR" "$BACKEND_IMAGE"

  echo "Exporting $FRONTEND_WEB_IMAGE -> $FRONTEND_WEB_TAR"
  podman save -o "$FRONTEND_WEB_TAR" "$FRONTEND_WEB_IMAGE"

  echo "Done. Tar files:"
  echo "  $BACKEND_TAR"
  echo "  $FRONTEND_WEB_TAR"
fi

echo "ARM64 image build completed with Podman."
