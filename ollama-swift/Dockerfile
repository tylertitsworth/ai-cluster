# ollama-swift: stock ROCm ollama with the Go plumbing needed to forward
# ngram / ngram-map-k4v speculative-decoding options to llama-server.
#
# Only the Go binary is rebuilt. The ROCm runtime and the llama-server binary
# (which already implements the ngram-map-k4v route) come from the base image,
# so the `LLAMA_CPP_VERSION` bump in the upstream patch is deliberately not
# applied -- see the patch header.
#
# Build:  ./build.sh          (or: docker build -t ollama-swift .)
# Push:   docker push ghcr.io/tylertitsworth/ollama-swift:latest

# Global args — single source of truth. Bump all three together.
# OLLAMA_VERSION drives `git clone --branch` in the builder; OLLAMA_IMAGE_TAG
# selects the ROCm runtime image in stage 2. Workflow derives IMAGE_TAG from
# OLLAMA_VERSION (${VER#v}-rocm) and passes all three as build-args.
ARG OLLAMA_VERSION=v0.40.15
ARG OLLAMA_IMAGE_TAG=0.40.15-rocm
ARG BUILD_VERSION=0.40.15-swift

# ---------------------------------------------------------------------------
# Stage 1: fetch pinned upstream source, apply the patch, compile
# ---------------------------------------------------------------------------
FROM golang:1.26.10 AS builder

ARG OLLAMA_VERSION
ARG BUILD_VERSION

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 --branch "${OLLAMA_VERSION}" https://github.com/ollama/ollama.git .

COPY 0001-llama-server-forward-ngram-map-k4v.patch /tmp/patch
RUN git apply --verbose /tmp/patch

# CGO_ENABLED=1 is required: server/images.go imports x/mlxrunner/mlx, whose
# bindings are cgo. The MLX C symbols are resolved lazily through dlopen
# (x/mlxrunner/mlx/dynamic.c), so the MLX C libraries themselves do not need
# to be built or present at link time. This mirrors ollama's own Dockerfile.
ENV CGO_ENABLED=1
RUN go build -trimpath -buildmode=pie \
      -ldflags "-w -s -X github.com/ollama/ollama/version.Version=${BUILD_VERSION}" \
      -o /out/ollama .

# ---------------------------------------------------------------------------
# Stage 2.5: gfx1151 hipBLASLt kernels
#
# The stock image ships no hipblaslt/library/ dir, so hipBLASLt emits
# `Cannot read "TensileLibrary_lazy_gfx1151.dat"` and silently falls back to
# slower paths. kyuz0 ships the tuned gfx1151 kernel library (ROCm 7.1);
# ship the whole dir (TensileLibrary_lazy_gfx1151.dat + Kernels.so).
# ---------------------------------------------------------------------------
FROM docker.io/kyuz0/amd-strix-halo-toolboxes:rocm-7.1 AS rocmlib

# note: the kyuz0 reference image is pinned by tag; bump above when upstream releases a newer ROCm toolbox.

# ---------------------------------------------------------------------------
# Stage 2: stock ROCm image with only /bin/ollama swapped
# ---------------------------------------------------------------------------
FROM ollama/ollama:${OLLAMA_IMAGE_TAG}

# /bin is a symlink to /usr/bin in this base, so this single COPY replaces the
# binary at both paths and leaves the entrypoint (/bin/ollama) and PATH lookup
# on the patched build.
COPY --from=builder /out/ollama /bin/ollama

# gfx1151 hipBLASLt kernels (from the rocmlib stage above).
COPY --from=rocmlib /opt/rocm-7.1.0/lib/hipblaslt/library/ /usr/lib/ollama/rocm_v7_2/hipblaslt/library/

# Maximal HIP tuning for gfx1151 (Bkpaine 2026): hipBLASLt kernels + rocWMMA FA.
ENV ROCBLAS_USE_HIPBLASLT=1
