#!/bin/sh
set -e

REQUIRED_SPEC=$(python3 /app/probe_version.py)
if [ -n "$REQUIRED_SPEC" ]; then
    echo "jtop client/service version mismatch detected, vendoring $REQUIRED_SPEC"
    # `pip install` runs jetson-stats' setup.py, which tries to delete the
    # real /run/jtop.sock when run as root (container-detection is unreliable
    # under k3s/containerd, and absent entirely before 4.3.0). Vendor just
    # the jtop/ package instead of letting pip run its installer.
    WORKDIR=$(mktemp -d)
    pip download --no-deps --no-binary=:all: --quiet "$REQUIRED_SPEC" -d "$WORKDIR"
    SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
    tar xzf "$WORKDIR"/*.tar.gz -C "$WORKDIR"
    rm -rf "$SITE_PACKAGES/jtop"
    cp -r "$WORKDIR"/jetson-stats-*/jtop "$SITE_PACKAGES/jtop"
    rm -rf "$WORKDIR"
fi

exec python3 /app/exporter.py --port 8000
