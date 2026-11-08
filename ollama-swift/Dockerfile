ARG OLLAMA_VERSION
ARG OLLAMA_IMAGE_TAG
ARG BUILD_VERSION

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
ENV CGO_ENABLED=1
RUN go build -trimpath -buildmode=pie \
      -ldflags "-w -s -X github.com/ollama/ollama/version.Version=${BUILD_VERSION}" \
      -o /out/ollama .

FROM ollama/ollama:${OLLAMA_IMAGE_TAG}
COPY --from=builder /out/ollama /bin/ollama
