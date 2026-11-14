# flaresolverr-patched: stock flaresolverr with a fix for upstream issue #1815
# ("Error terminating service process" PermissionError leaves orphaned chromium).
#
# Build:  ./build.sh
# Push:   PUSH=1 ./build.sh
# Image:  ghcr.io/tylertitsworth/flareSolverr-patched:latest  (lowercase for ghcr)

FROM ghcr.io/flaresolverr/flaresolverr:latest@sha256:c80ae007ce2ccdcd217a12426e4f039ef763ff90738c808d38810c3e59323767

USER root
COPY patch.py /tmp/patch.py
RUN python3 /tmp/patch.py && rm /tmp/patch.py
USER flaresolverr