import re
import sys

VERSION_MISMATCH_RE = re.compile(r"jtop service:\s*\[([^\]]+)\]")


def required_spec(error_message):
    """
    Must be an exact pin, not a major.minor range: jetson-stats <4.3.0
    compares the full version string for equality, so "latest patch in
    this minor line" can still mismatch against an older service.
    """
    match = VERSION_MISMATCH_RE.search(error_message)
    if not match:
        return None
    return "jetson-stats=={version}".format(version=match.group(1))


if __name__ == "__main__":
    from jtop import jtop

    # Probe the real connection; on a version mismatch, print the spec
    # entrypoint.sh should vendor in place of the installed client.
    try:
        with jtop():
            pass
    except Exception as exc:
        spec = required_spec(str(exc))
        if spec:
            print(spec)
    sys.exit(0)
