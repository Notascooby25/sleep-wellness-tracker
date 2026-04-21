#!/usr/bin/env bash
set -euo pipefail

# Build both backend and frontend images for linux/arm64 using docker buildx,
# load them into the local Docker daemon, and optionally export tar files.
#
# Usage:
#   From project root:
#     ./scripts/build_arm64_images.sh
#
# Environment overrides:
#   PLATFORM (default linux/arm64)
#   BACKEND_IMAGE (default sleep-wellness-tracker-backend:arm64)
#   FRONTEND_IMAGE (default sleep-wellness-tracker-frontend:arm64)
#   OUTPUT_DIR (default ./dist)
#   EXPORT_TARS (1 to export tar files, 0 to skip)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PLATFORM="${PLATFORM:-linux/arm64}"
BACKEND_IMAGE="${BACKEND_IMAGE:-sleep-wellness-tracker-backend:arm64}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-sleep-wellness-tracker-frontend:arm64}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/dist}"
EXPORT_TARS="${EXPORT_TARS:-1}"

# Ensure docker CLI exists
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker CLI not found in PATH" >&2
  exit 1
fi

# Ensure buildx is available
if ! docker buildx version >/dev/null 2>&1; then
  echo "ERROR: docker buildx is required. Install Docker Buildx and try again." >&2
  exit 1
fi

cd "$ROOT_DIR"

# Create and use a builder if none exists
if ! docker buildx inspect sleepwell-builder >/dev/null 2>&1; then
  echo "Creating buildx builder 'sleepwell-builder'..."
  docker buildx create --name sleepwell-builder --use
else
  docker buildx use sleepwell-builder
fi

# Ensure QEMU emulation registered (only needed if building for non-native arch)
if ! docker run --rm --privileged multiarch/qemu-user-static --reset -p yes >/dev/null 2>&1; then
  echo "Warning: could not register qemu-user-static. If builds fail, run:"
  echo "  docker run --rm --privileged multiarch/qemu-user-static --reset -p yes"
fi

# Validate Dockerfiles do not force an architecture
for df in backend/Dockerfile frontend/Dockerfile; do
  if grep -E -- '--platform=|FROM --platform=' "$df" >/dev/null 2>&1; then
    echo "ERROR: $df contains an explicit platform directive. Remove any '--platform' or 'FROM --platform=...' lines."
    exit 1
  fi
done

echo "Building backend image for $PLATFORM -> $BACKEND_IMAGE"
docker buildx build \
  --platform "$PLATFORM" \
  -t "$BACKEND_IMAGE" \
  -f backend/Dockerfile \
  backend \
  --load

echo "Building frontend image for $PLATFORM -> $FRONTEND_IMAGE"
docker buildx build \
  --platform "$PLATFORM" \
  -t "$FRONTEND_IMAGE" \
  -f frontend/Dockerfile \
  frontend \
  --load

if [[ "$EXPORT_TARS" == "1" ]]; then
  mkdir -p "$OUTPUT_DIR"
  BACKEND_TAR="$OUTPUT_DIR/sleep-wellness-tracker-backend-arm64.tar"
  FRONTEND_TAR="$OUTPUT_DIR/sleep-wellness-tracker-frontend-arm64.tar"

  echo "Exporting $BACKEND_IMAGE -> $BACKEND_TAR"
  docker save -o "$BACKEND_TAR" "$BACKEND_IMAGE"

  echo "Exporting $FRONTEND_IMAGE -> $FRONTEND_TAR"
  docker save -o "$FRONTEND_TAR" "$FRONTEND_IMAGE"

  echo "Done. Tar files:"
  echo "  $BACKEND_TAR"
  echo "  $FRONTEND_TAR"
fi

echo "ARM64 image build completed."
