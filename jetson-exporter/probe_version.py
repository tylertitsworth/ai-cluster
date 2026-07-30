import re
import sys

VERSION_MISMATCH_RE = re.compile(r"jtop service:\s*\[(\d+)\.(\d+)")


def required_spec(error_message):
    """
    Given jtop's version-mismatch error text, return a pip requirement spec
    pinned to the host service's major.minor, or None if the message doesn't
    describe a version mismatch.
    """
    match = VERSION_MISMATCH_RE.search(error_message)
    if not match:
        return None
    major, minor = match.groups()
    return "jetson-stats~={major}.{minor}.0".format(major=major, minor=minor)


if __name__ == "__main__":
    from jtop import jtop

    # jtop refuses to connect if the client's major.minor doesn't match the
    # host's jtop.service (see jtop.core.common.compare_versions). Different
    # Jetson nodes can run different JetPack/jetson_stats versions, so the
    # container's pinned client won't always match. Detect a mismatch from
    # jtop's own error message and print a pip requirement spec for
    # entrypoint.sh to install.
    try:
        with jtop():
            pass
    except Exception as exc:
        spec = required_spec(str(exc))
        if spec:
            print(spec)
    sys.exit(0)
