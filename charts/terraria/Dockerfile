FROM steamcmd/steamcmd:alpine-3

# Install prerequisites
RUN apk update \
    && apk add --no-cache bash curl tmux libstdc++ libgcc icu-libs \
    && rm -rf /var/cache/apk/*

# Fix 32 and 64 bit library conflicts
RUN mkdir /steamlib \
    && mv /lib/libstdc++.so.6 /steamlib \
    && mv /lib/libgcc_s.so.1 /steamlib
ENV LD_LIBRARY_PATH /steamlib

# Set a specific tModLoader version, defaults to the latest Github release
ARG TML_VERSION

# Create .dockerenv marker for Kubernetes compatibility
# The management script checks for this file to detect container environment
RUN touch /.dockerenv

# Create tModLoader user and drop root permissions
ARG UID=1000
ARG GID=1000
RUN addgroup -g $GID tml \
    && adduser tml -u $UID -G tml -h /home/tml -D
USER tml
ENV USER tml
ENV HOME /home/tml
WORKDIR $HOME

# Update SteamCMD and verify latest version
RUN steamcmd +quit

ADD --chown=tml:tml https://raw.githubusercontent.com/tModLoader/tModLoader/1.4.5/patches/tModLoader/Terraria/release_extras/DedicatedServerUtils/manage-tModLoaderServer.sh .

# Make management script executable
RUN chmod +x manage-tModLoaderServer.sh

# Install tModLoader at build time. Defaults to the latest published GitHub
# release; pass --build-arg TML_VERSION=<tag> to pin an exact version.
# Only pass the flag when a version is set: an empty --tmlversion resolves to
# a 404 and the build would silently ship without tModLoader.
RUN set -e \
    && if [ -n "$TML_VERSION" ]; then \
         ./manage-tModLoaderServer.sh install-tml --github --tmlversion "$TML_VERSION"; \
       else \
         ./manage-tModLoaderServer.sh install-tml --github; \
       fi

# Fail loudly if tModLoader did not actually install
# (the script populates server/ under the install folder)
RUN test -n "$(cat server/.ver)" && test -f server/LaunchUtils/ScriptCaller.sh

EXPOSE 7777

# The management script's "docker" command was removed upstream (v4.0.0.1);
# "start" is the equivalent now that tModLoader is installed at build time.
ENTRYPOINT [ "./manage-tModLoaderServer.sh", "start", "--folder", "/home/tml/.local/share/Terraria/tModLoader" ]
