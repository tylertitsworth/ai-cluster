#!/usr/bin/env python3
"""RED test for Task 1: compaction must be 72k on 131k (buffer 45%)."""
import json, pathlib, sys
p = pathlib.Path.home() / ".config/opencode/opencode.json"
data = json.loads(p.read_text())
comp = data.get("compaction", {})
buf = comp.get("buffer")
keep = comp.get("keep", {}).get("tokens")
bg = data.get("experimental", {}).get("background_compaction")
print(f"buffer={buf!r} keep={keep!r} background={bg!r}")
assert buf == "45%", f"FAIL: buffer {buf!r} != '45%' (want 72k on 131k)"
assert keep == 15000, f"FAIL: keep {keep!r} != 15000"
assert bg is True, f"FAIL: background_compaction {bg!r} != True"
print("PASS")
