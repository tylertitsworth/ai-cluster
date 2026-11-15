FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git bash openssh-client \
    && rm -rf /var/lib/apt/lists/*
# Install opencode CLI
ARG OPENCODE_VERSION=2.2.6
RUN curl -fsSL "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-x64.tar.gz" \
      -o /tmp/opencode.tar.gz \
    && tar -xzf /tmp/opencode.tar.gz -C /usr/local/bin opencode \
    && chmod +x /usr/local/bin/opencode \
    && rm /tmp/opencode.tar.gz
RUN useradd -m -u 65532 -s /bin/bash kagent \
    && mkdir -p /config /skills /plugins /data/plugins /workspace \
    && chown -R 65532:65532 /config /skills /plugins /data /workspace /home/kagent
COPY opencode-byo-harness.bin /app
USER 65532:65532
WORKDIR /workspace
ENV HOME=/home/kagent
ENTRYPOINT ["/app"]
