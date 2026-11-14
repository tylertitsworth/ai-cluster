FROM debian:bookworm-slim

ARG TERRARIA_VERSION=1458

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*

ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID terraria \
    && useradd -u $UID -g $GID -m -s /bin/bash terraria
USER terraria
ENV USER terraria
ENV HOME /home/terraria
WORKDIR $HOME

RUN curl -fsSL "https://terraria.org/api/download/pc-dedicated-server/terraria-server-${TERRARIA_VERSION}.zip" -o /tmp/ts.zip \
    && unzip -q /tmp/ts.zip -d /tmp/ts \
    && mkdir -p "$HOME/server" \
    && cp -a "/tmp/ts/${TERRARIA_VERSION}/Linux/." "$HOME/server/" \
    && chmod +x "$HOME/server/TerrariaServer" "$HOME/server/TerrariaServer.bin.x86_64" \
    && rm -rf /tmp/ts /tmp/ts.zip

RUN test -x "$HOME/server/TerrariaServer.bin.x86_64"

EXPOSE 7777

ENTRYPOINT [ "/home/terraria/server/TerrariaServer", "-config", "/home/terraria/.local/share/Terraria/serverconfig.txt" ]
