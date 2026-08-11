FROM node:24-slim AS build

ARG OPENCODE_VERSION=beta
RUN npm install -g opencode-ai@${OPENCODE_VERSION} \
    && mv /usr/local/lib/node_modules/opencode-ai/bin/opencode.exe /usr/local/bin/opencode \
    && chmod +x /usr/local/bin/opencode

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 opencode \
    && useradd -u 1000 -g 1000 -m -s /bin/bash opencode

COPY --from=build /usr/local/bin/opencode /usr/local/bin/opencode

USER opencode
WORKDIR /home/opencode
EXPOSE 4096

ENTRYPOINT ["opencode"]
