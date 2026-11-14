#!/usr/bin/env bash
# Build and optionally push the flaresolverr-patched image.
#
#   ./build.sh                    build ghcr.io/tylertitsworth/ai-cluster-flaresolverr:latest
#   PUSH=1 ./build.sh             build, then push
#   PLATFORM=linux/arm64 ./build.sh
set -euo pipefail

REPO="${REPO:-ghcr.io/tylertitsworth/ai-cluster-flaresolverr}"
TAG="${TAG:-latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE="${REPO}:${TAG}"

cd "$(dirname "$0")"
echo "==> building ${IMAGE}"

if [[ "${PLATFORM}" == "$(docker version -f '{{.Server.Os}}/{{.Server.Arch}}')" ]]; then
  docker build -t "${IMAGE}" .
else
  docker buildx build --platform "${PLATFORM}" -t "${IMAGE}" --load .
fi

if [[ "${PUSH:-0}" == "1" ]]; then
  echo "==> pushing ${IMAGE}"
  docker push "${IMAGE}"
fi