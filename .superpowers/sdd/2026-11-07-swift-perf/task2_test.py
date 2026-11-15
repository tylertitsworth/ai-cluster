#!/usr/bin/env python3
"""Task2 RED/GREEN: MTP4 + ctx live."""
p="/home/titsw/Projects/ai-cluster/apps/ai/values/ollama.yaml"
t=open(p).read()
assert "draft_num_predict 4" in t, "FAIL: draft_num_predict not 4"
assert 'OLLAMA_CONTEXT_LENGTH' in t and 'value: "131072"' in t, "FAIL: ctx not 131072"
print("PASS mtp4+ctx")
