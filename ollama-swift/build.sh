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

OLLAMA_VERSION=$(sed -n 's/^ARG OLLAMA_VERSION=//p' Dockerfile | head -n 1)
OLLAMA_IMAGE_TAG="${OLLAMA_VERSION#v}-rocm"
BUILD_VERSION=$(sed -n 's/^ARG BUILD_VERSION=//p' Dockerfile | head -n 1)
REPO="${REPO:-ghcr.io/tylertitsworth/ai-cluster-ollama-swift}"
TAG="${TAG:-${OLLAMA_VERSION#v}-tuned}"
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE="${REPO}:${TAG}"

echo "==> building ${IMAGE} (${PLATFORM}) from OLLAMA_VERSION=${OLLAMA_VERSION} BUILD_VERSION=${BUILD_VERSION} OLLAMA_IMAGE_TAG=${OLLAMA_IMAGE_TAG}"

if [[ "${PLATFORM}" == "$(docker version -f '{{.Server.Os}}/{{.Server.Arch}}')" ]]; then
  docker build --build-arg "OLLAMA_VERSION=${OLLAMA_VERSION}" --build-arg "OLLAMA_IMAGE_TAG=${OLLAMA_IMAGE_TAG}" --build-arg "BUILD_VERSION=${BUILD_VERSION}" -t "${IMAGE}" .
else
  docker buildx build --platform "${PLATFORM}" --build-arg "OLLAMA_VERSION=${OLLAMA_VERSION}" --build-arg "OLLAMA_IMAGE_TAG=${OLLAMA_IMAGE_TAG}" --build-arg "BUILD_VERSION=${BUILD_VERSION}" -t "${IMAGE}" --push .
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
  # gfx1151 hipBLASLt kernels (rocmlib stage) — fail fast if the lazy file is gone.
  test -f /usr/lib/ollama/rocm_v7_2/hipblaslt/library/TensileLibrary_lazy_gfx1151.dat && echo "  lazy ok" || { echo "  LAZY MISSING"; exit 1; }
  test -f /usr/lib/ollama/rocm_v7_2/hipblaslt/library/Kernels.so-000-gfx1151.hsaco && echo "  kernels ok" || { echo "  KERNELS MISSING"; exit 1; }
  echo -n "  /bin -> /usr/bin:   "; readlink /bin
  echo -n "  llama-server k4v flags: "
  /usr/lib/ollama/llama-server --help 2>&1 | grep -c "spec-ngram-map-k4v"
'

echo "==> built ${IMAGE}"

if [[ "${PUSH:-0}" == "1" ]]; then
  echo "==> pushing ${IMAGE}"
  docker push "${IMAGE}"
fi
