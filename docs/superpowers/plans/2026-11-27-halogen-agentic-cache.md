# Halogen Agentic Cache Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tune the existing Halogen 0.21.0 chart so OpenCode agentic sessions keep a warm prompt cache across restarts and subagent fan-out, with GitOps as the only source of config.

**Architecture:** Add four env entries to `charts/halogen/values.yaml` (disk cache, disk bound, branches, entries), delete the stale ConfigMap once so Argo rebuilds it from the chart, restart the Deployment, and verify the live `/health` and `/cache` state. No client or model changes.

**Tech Stack:** Helm 4 / app-template 3.5.1, Argo CD, k3s, kubectl, Halogen 0.21.0, tailnet ingress.

**Spec:** `docs/superpowers/specs/2026-11-27-halogen-agentic-cache-design.md`

## Global Constraints

- Branch: `add/halogen-gguf`; PR #106 stays `OPEN`, base `main`, head `add/halogen-gguf`. Never merge.
- Image pinned: `ghcr.io/peonist-ai/halogen-flash-server:0.21.0`.
- Keep unverified values: `HALOGEN_CTX=262144`, `HALOGEN_KV_POOL_POSITIONS=262144`, `HALOGEN_KV_SLOTS=4`, `HALOGEN_PROMPT_CACHE=2`, `HALOGEN_HOST_RESERVE_GIB=8`, `HALOGEN_CHECKPOINT=/root/.ollama/qwen38-27b-ht4.hgn`, `HALOGEN_DOWNLOAD=peonist-ai/halogen-qwen3.8-27b-ht4`, `HALOGEN_MODEL_ID=halogen-qwen3.8-27b`, `HALOGEN_TOKENIZER=/root/.ollama/models/blobs/tokenizer`, `HALOGEN_API_PORT=8731`.
- Do not add `HALOGEN_CACHE_MB`, `HALOGEN_CACHE_RESERVE_MB`, or `HALOGEN_SLOT_CTX` — ignored by 0.21.0 and present only as live drift.
- Argo app `halogen` has `syncPolicy.automated.enabled: false` at rest; enable only for a sync, then restore.
- GitOps authoritative: no kubectl-only final state. Tailscale ingress `halogen` unchanged; no port-forward or second engine.
- PVC `ollama-data` (100 GiB, 62 GiB free) mounted at `/root/.ollama`; cache directory below that mount.

## Review Focus

- **Stale ConfigMap keys survive a merge apply:** the live ConfigMap has three legacy keys absent from the chart. Test in Task 2 asserts the ConfigMap has exactly the chart's cache keys and none of the stale three.
- **Cache directory on a filesystem that refuses direct I/O:** `/cache` must report `disk.on: true` and logs must not name a cache-dir refusal. Test in Task 2 asserts both; if it fails, the deployment falls back to memory-only and the design must be revisited.
- **More entries/branches eat the 7 GiB host headroom:** rollout must reach 1/1 and `/health` must still report pool 262144, slots 4, mode 2. Test in Task 2 asserts all four.
- **Argo left in automated mode:** a temporary patch can stick. Test in Task 2 asserts `.spec.syncPolicy.automated.enabled == false`.
- **PR or ingress accidentally changed:** test in Task 2 asserts PR #106 is OPEN with the original base/head and the chart still renders host `halogen` with class `tailscale`.

---

### Task 1: Chart cache values

**Files:**
- Modify: `charts/halogen/values.yaml` (`config` list, after `HALOGEN_PROMPT_CACHE`)
- Test: `.superpowers/sdd/2026-11-27-halogen-agentic-cache/task1-test.sh`

**Interfaces:**
- Consumes: existing `config` list shape (`key`/`value` pairs) from the benchmark chart.
- Produces: rendered ConfigMap entries `HALOGEN_CACHE_DIR`, `HALOGEN_CACHE_DISK_GIB`, `HALOGEN_CACHE_BRANCHES`, `HALOGEN_CACHE_ENTRIES` consumed by Task 2.

- [ ] **Step 1: Write the failing test** at `.superpowers/sdd/2026-11-27-halogen-agentic-cache/task1-test.sh`:

```bash
#!/bin/bash
set -euo pipefail
cd /home/titsw/.local/share/opencode/worktree/fc6729/silent-eagle
V=charts/halogen/values.yaml
fail() { echo "MISSING: $1"; exit 1; }
for pair in \
  'HALOGEN_CACHE_DIR|/root/.ollama/halogen-cache' \
  'HALOGEN_CACHE_DISK_GIB|32' \
  'HALOGEN_CACHE_BRANCHES|3' \
  'HALOGEN_CACHE_ENTRIES|36'; do
  k=${pair%%|*}; v=${pair#*|}
  grep -Fq "key: $k" "$V" || fail "$k in values"
  grep -A1 -F "key: $k" "$V" | grep -Fq "value: $v" || fail "$k=$v in values"
  helm template halogen charts/halogen | grep -Fq "$k: \"$v\"" || fail "$k=$v rendered"
done
for stale in HALOGEN_CACHE_MB HALOGEN_CACHE_RESERVE_MB HALOGEN_SLOT_CTX; do
  ! grep -Fq "$stale" "$V" || fail "stale $stale in values"
  ! helm template halogen charts/halogen | grep -Fq "$stale" || fail "stale $stale rendered"
done
helm template halogen charts/halogen | grep -Fq 'HALOGEN_PROMPT_CACHE: "2"' || fail 'prompt cache mode 2'
helm template halogen charts/halogen | grep -Fq 'HALOGEN_KV_POOL_POSITIONS: "262144"' || fail 'pool unchanged'
echo 'TASK1 PASS'
```

- [ ] **Step 2: Run it to verify RED** — `bash .superpowers/sdd/2026-11-27-halogen-agentic-cache/task1-test.sh` → expected `MISSING: HALOGEN_CACHE_DIR in values`.

- [ ] **Step 3: Add the four entries** to the `config` list in `charts/halogen/values.yaml`, immediately after the `HALOGEN_PROMPT_CACHE` pair, with values exactly `/root/.ollama/halogen-cache`, `32`, `3`, `36`. Add one comment line: `shortcut: 32 GiB bounds the cache to half the free PVC; raise when the disk cache approaches that limit.` Keep every other key in the list unchanged.

- [ ] **Step 4: Run it to verify GREEN** — `bash .superpowers/sdd/2026-11-27-halogen-agentic-cache/task1-test.sh` → expected `TASK1 PASS`.

- [ ] **Step 5: Commit** — `git add charts/halogen/values.yaml && git commit -m "feat(halogen): tune prompt cache for agentic OpenCode" && git push`.

---

### Task 2: GitOps sync and live verification

**Files:**
- Test: `.superpowers/sdd/2026-11-27-halogen-agentic-cache/task2-test.sh`
- No source files; live objects only.

**Interfaces:**
- Consumes: the ConfigMap rendered by Task 1 and the Argo Application `halogen` on `add/halogen-gguf`.
- Produces: live Halogen Deployment with mode 2, disk cache on, three branches, 36 entries; PR #106 still open.

- [ ] **Step 1: Write the failing test** at `.superpowers/sdd/2026-11-27-halogen-agentic-cache/task2-test.sh`:

```bash
#!/bin/bash
set -euo pipefail
cd /home/titsw/.local/share/opencode/worktree/fc6729/silent-eagle
fail() { echo "MISSING: $1"; exit 1; }
CM=$(kubectl -n ollama get cm halogen-config -o json 2>/dev/null || echo '{}')
for pair in \
  'HALOGEN_CACHE_DIR|/root/.ollama/halogen-cache' \
  'HALOGEN_CACHE_DISK_GIB|32' \
  'HALOGEN_CACHE_BRANCHES|3' \
  'HALOGEN_CACHE_ENTRIES|36'; do
  k=${pair%%|*}; v=${pair#*|}
  echo "$CM" | jq -e --arg k "$k" --arg v "$v" '.data[$k] == $v' >/dev/null || fail "$k=$v in ConfigMap"
done
for stale in HALOGEN_CACHE_MB HALOGEN_CACHE_RESERVE_MB HALOGEN_SLOT_CTX; do
  echo "$CM" | jq -e --arg k "$stale" '.data | has($k) | not' >/dev/null || fail "stale $stale in ConfigMap"
done
[[ "$(kubectl -n ollama get deploy halogen -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)" == 1 ]] || fail 'halogen ready replica'
[[ "$(kubectl -n argocd get app halogen -o jsonpath='{.spec.syncPolicy.automated.enabled}' 2>/dev/null || true)" == false ]] || fail 'automated sync restored'
kubectl -n ollama exec deploy/halogen -- python3 -c '
import json,urllib.request
h=json.load(urllib.request.urlopen("http://127.0.0.1:8731/health",timeout=10))
c=json.load(urllib.request.urlopen("http://127.0.0.1:8731/cache",timeout=10))
assert h["prompt_cache"]["mode"]==2, "mode"
assert h["kv_pool_positions"]==262144, "pool"
assert h["slots"]==4, "slots"
assert h["checkpoint_format"]=="hgn", "format"
assert c["disk"]["on"] is True, "disk cache off"
assert c["max_entries"]>=36, "entries"
print("CACHE OK")' 2>&1 | grep -Fq 'CACHE OK' || fail 'live health/cache'
if kubectl -n ollama logs deploy/halogen --tail=500 2>/dev/null | grep -iE 'direct I/O.*cache|cache dir.*refus|refus.*cache dir'; then fail 'cache dir refusal in logs'; fi
[[ "$(gh pr view 106 --json state --jq .state 2>/dev/null || true)" == OPEN ]] || fail 'PR #106 open'
helm template halogen charts/halogen | grep -Fq 'host: halogen' || fail 'ingress host'
echo 'TASK2 PASS'
```

- [ ] **Step 2: Run it to verify RED** — `bash .superpowers/sdd/2026-11-27-halogen-agentic-cache/task2-test.sh` → expected failure on `HALOGEN_CACHE_DIR=/root/.ollama/halogen-cache in ConfigMap`.

- [ ] **Step 3: Recreate the ConfigMap and sync** — run in order:

```bash
kubectl -n ollama delete cm halogen-config --ignore-not-found
kubectl -n argocd patch app halogen --type=merge -p '{"spec":{"syncPolicy":{"automated":{"enabled":true,"prune":true,"selfHeal":true}}}}'
kubectl -n argocd annotate app halogen argocd.argoproj.io/refresh=hard --overwrite
for i in $(seq 1 24); do
  v=$(kubectl -n ollama get cm halogen-config -o jsonpath='{.data.HALOGEN_CACHE_DIR}' 2>/dev/null || true)
  [[ "$v" == /root/.ollama/halogen-cache ]] && { echo "synced after $i checks"; break; }
  sleep 5
done
kubectl -n argocd patch app halogen --type=merge -p '{"spec":{"syncPolicy":{"automated":{"enabled":false,"prune":true,"selfHeal":true}}}}'
kubectl -n argocd get app halogen -o jsonpath='{.spec.syncPolicy.automated.enabled}{"\n"}'
```

Expected: ConfigMap synced, final automated value `false`.

- [ ] **Step 4: Restart and wait** — `kubectl -n ollama rollout restart deploy/halogen && kubectl -n ollama rollout status deploy/halogen --timeout=900s`. Expected: `deployment "halogen" successfully rolled out`.

- [ ] **Step 5: Run the test to verify GREEN** — `bash .superpowers/sdd/2026-11-27-halogen-agentic-cache/task2-test.sh` → expected `TASK2 PASS`. If `disk cache off`, inspect `kubectl -n ollama logs deploy/halogen --tail=200` for the direct-I/O refusal; do not mark the task done until either disk cache is on or the design is amended and approved.

- [ ] **Step 6: Ledger, no repo commit** — mark Task 2 done with `task-done`; all repo changes were committed in Task 1.
