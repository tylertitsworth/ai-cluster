from probe_version import required_spec

MISMATCH_MSG = """Mismatch version jtop service: [4.2.7] and client: [4.3.1]. Please run:

sudo jtop --install-service"""

assert required_spec(MISMATCH_MSG) == "jetson-stats~=4.2.0"
assert required_spec("The jtop.service is not active. Please run:\nsudo jtop --install-service") is None
assert required_spec("") is None

print("ok")
