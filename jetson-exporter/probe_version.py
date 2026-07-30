import re
import sys

VERSION_MISMATCH_RE = re.compile(r"jtop service:\s*\[([^\]]+)\]")


def required_spec(error_message):
    """
    Given jtop's version-mismatch error text, return a pip requirement spec
    pinned to the host service's exact version, or None if the message
    doesn't describe a version mismatch.

    Must be an exact pin, not a major.minor range: jetson-stats <4.3.0
    compares the full version string for equality, not just major.minor
    (that leniency was only added in 4.3.0), so installing "latest patch
    in this minor line" can still mismatch against an older service.
    """
    match = VERSION_MISMATCH_RE.search(error_message)
    if not match:
        return None
    return "jetson-stats=={version}".format(version=match.group(1))


if __name__ == "__main__":
    from jtop import jtop

    # jtop refuses to connect if the client's version doesn't match the
    # host's jtop.service (see jtop.jtop.start()). Different Jetson nodes
    # can run different JetPack/jetson_stats versions, so the container's
    # pinned client won't always match. Detect a mismatch from jtop's own
    # error message and print a pip requirement spec for entrypoint.sh to
    # install.
    try:
        with jtop():
            pass
    except Exception as exc:
        spec = required_spec(str(exc))
        if spec:
            print(spec)
    sys.exit(0)
