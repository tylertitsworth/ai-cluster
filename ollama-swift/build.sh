#!/usr/bin/env bash
# Build and optionally push the ollama-swift image.
#
#   ./build.sh                    build ghcr.io/tylertitsworth/ollama-swift:latest
#   PUSH=1 ./build.sh             build, then push
#   PLATFORM=linux/arm64 ./build.sh
#
# The image is a Go-binary swap on the stock ROCm base, so a plain
# `docker build` is enough for a single platform. buildx is only required
# when PLATFORM is set to something other than the host architecture.
set -euo pipefail

cd "$(dirname "$0")"

REPO="${REPO:-ghcr.io/tylertitsworth/ollama-swift}"
TAG="${TAG:-latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE="${REPO}:${TAG}"

echo "==> building ${IMAGE} (${PLATFORM})"

if [[ "${PLATFORM}" == "$(docker version -f '{{.Server.Os}}/{{.Server.Arch}}')" ]]; then
  docker build -t "${IMAGE}" .
else
  docker buildx build --platform "${PLATFORM}" -t "${IMAGE}" --push .
fi

echo "==> verifying the patched binary is in place"
docker run --rm --entrypoint /bin/sh "${IMAGE}" -c '
  set -e
  # grep -a, not strings: binutils is not in this base image.
  echo -n "  version:            "
  /bin/ollama --version 2>&1 | grep -o "client version is .*"
  for marker in draft_spec_type draft_ngram_map_k4v_size_n \
                draft_ngram_map_k4v_size_m draft_ngram_map_k4v_min_hits; do
    if grep -aq "$marker" /bin/ollama; then
      echo "  marker ok:          $marker"
    else
      echo "  MARKER MISSING:     $marker"; exit 1
    fi
  done
  echo -n "  /bin -> /usr/bin:   "; readlink /bin
  echo -n "  llama-server k4v flags: "
  /usr/lib/ollama/llama-server --help 2>&1 | grep -c "spec-ngram-map-k4v"
'

echo "==> built ${IMAGE}"

if [[ "${PUSH:-0}" == "1" ]]; then
  echo "==> pushing ${IMAGE}"
  docker push "${IMAGE}"
fi
