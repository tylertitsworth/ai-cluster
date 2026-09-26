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

# ---------------------------------------------------------------------------
# Stage 1: fetch pinned upstream source, apply the patch, compile
# ---------------------------------------------------------------------------
FROM golang:1.26 AS builder

# Pinned so the image is reproducible. Bump both together.
ARG OLLAMA_VERSION=v0.34.0
# Reported by `ollama --version`; the `-swift` suffix makes it obvious in a
# running pod that the patched binary is in place.
ARG BUILD_VERSION=0.34.0-swift

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
# Stage 2: stock ROCm image with only /bin/ollama swapped
# ---------------------------------------------------------------------------
FROM ollama/ollama:0.34.0-rocm

# /bin is a symlink to /usr/bin in this base, so this single COPY replaces the
# binary at both paths and leaves the entrypoint (/bin/ollama) and PATH lookup
# on the patched build.
COPY --from=builder /out/ollama /bin/ollama
