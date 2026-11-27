# Halogen Probe Tolerance and Weights Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Kubernetes liveness tolerant of Halogen's 180 s + 900 s watchdog window and make `HALOGEN_WEIGHTS_LOCK=1` actually lock the weights by raising the container's memlock limit.

**Architecture:** Change only `charts/halogen/values.yaml`: widen the liveness threshold from 6 to 40 at 30 s intervals (1200 s), add `HALOGEN_WEIGHTS_LOCK=1` to the chart config, and wrap the container command with `set -e; ulimit -l unlimited` before the existing entrypoint. Then sync via Argo, restart the Deployment when no engine thread is in D state, and verify the rendered chart, ConfigMap, pod spec, startup log, `/health` and `/cache`.

**Tech Stack:** Helm 4 / app-template 3.5.1, Argo CD, k3s, kubectl, Halogen 0.21.0.

**Spec:** `docs/superpowers/specs/2026-11-27-halogen-probe-weights-lock-design.md`

## Global Constraints

- Branch `add/halogen-gguf`; PR #106 stays `OPEN`, base `main`, head `add/halogen-gguf`; never merge.
- Image pinned `ghcr.io/peonist-ai/halogen-flash-server:0.21.0`; single container, privileged root.
- Preserve `HALOGEN_CTX=262144`, `HALOGEN_PROMPT_CACHE=2`, `HALOGEN_KV_SLOTS=4`, `HALOGEN_KV_POOL_POSITIONS=262144`, `HALOGEN_HOST_RESERVE_GIB=8`, ht4 checkpoint/tokenizer, all four `HALOGEN_CACHE_*` values from the previous plan, readiness 24 × 15 s, Tailscale ingress `halogen`.
- Argo app `halogen` has `syncPolicy.automated.enabled: false` at rest; enable only for a sync, then restore.
- GitOps authoritative: no kubectl-only final state; no port-forward or second engine.
- Restart only when no engine thread is in uninterruptible (D) state; an engine killed in D state can leave the GPU driver holding GPU memory (upstream issue #79).

## Review Focus

Execution note: the embedded test snippets below were hardened during execution
(`grep -Fc` instead of `grep -Fq` under `pipefail`, a narrowed lock-failure regex,
and bounded retries for transient `/health` 503s). The executable copies in
`.superpowers/sdd/2026-11-27-halogen-probe-weights-lock/` are authoritative.

- **memlock too low:** if the command wrapper does not raise both soft and hard limits, the server starts unlocked despite the flag. Test in Task 2 asserts a `checkpoint: locked` startup line and no lock-failure line.
- **Liveness preempting the watchdog:** if `failureThreshold` is not 40 in the rendered chart and the live pod, Kubernetes can restart at ~875 s, inside the watchdog's 180 s + 900 s = 1080 s budget. Tests in Tasks 1 and 2 pin both. An unbounded D-state stall remains an accepted residual risk of keeping HTTP liveness (the user rejected removing liveness); it is documented in the spec, not silently ignored.
- **Readiness accidentally widened:** a person expects readiness to keep signalling unavailability; Task 2 asserts live readiness is still 24.
- **Entry point broken by the wrapper:** a person expects the server to start; Task 2 asserts rollout 1/1 and `/health` mode 2 after restart.
- **Cache tuning lost in the restart:** Task 2 asserts `/cache` `disk.on: true` and `max_entries: 36`.
- **Argo or PR drift:** Task 2 asserts automated sync `false` and PR #106 `OPEN`.

---

### Task 1: Chart probe and weights-lock values

**Files:**
- Modify: `charts/halogen/values.yaml` (`containers.main.command`/`args`, liveness threshold, `config` list)
- Test: `.superpowers/sdd/2026-11-27-halogen-probe-weights-lock/task1-test.sh`

**Interfaces:**
- Consumes: existing chart structure from the cache-tuning plan.
- Produces: rendered Deployment liveness `failureThreshold: 40`, readiness `failureThreshold: 24`, fail-closed command/args wrapper raising memlock, ConfigMap `HALOGEN_WEIGHTS_LOCK: "1"`; consumed by Task 2.

- [ ] **Step 1: Write the failing test** at `.superpowers/sdd/2026-11-27-halogen-probe-weights-lock/task1-test.sh`:

```bash
#!/bin/bash
set -euo pipefail
cd /home/titsw/.local/share/opencode/worktree/fc6729/silent-eagle
V=charts/halogen/values.yaml
R=$(helm template halogen charts/halogen)
fail() { echo "MISSING: $1"; exit 1; }
echo "$R" | grep -Fc 'failureThreshold: 40' >/dev/null || fail 'liveness threshold 40 rendered'
echo "$R" | grep -Fc 'failureThreshold: 24' >/dev/null || fail 'readiness threshold 24 rendered'
echo "$R" | grep -Fq 'HALOGEN_WEIGHTS_LOCK: "1"' || fail 'weights lock config rendered'
echo "$R" | grep -Fq '/bin/bash' || fail 'command wrapper rendered'
echo "$R" | grep -Fq 'ulimit -l unlimited' || fail 'memlock raise rendered'
echo "$R" | grep -Fq 'exec /usr/local/bin/entrypoint.sh all' || fail 'entrypoint exec rendered'
grep -A1 -F 'key: HALOGEN_WEIGHTS_LOCK' "$V" | grep -Fq 'value: 1' || fail 'weights lock value in values'
echo "$R" | grep -Fq 'HALOGEN_PROMPT_CACHE: "2"' || fail 'prompt cache unchanged'
echo "$R" | grep -Fq 'HALOGEN_CACHE_ENTRIES: "36"' || fail 'cache entries unchanged'
echo "$R" | grep -Fq 'host: "halogen"' || fail 'ingress host'
echo 'TASK1 PASS'
```

- [ ] **Step 2: Run it to verify RED** — `bash .superpowers/sdd/2026-11-27-halogen-probe-weights-lock/task1-test.sh` → expected `MISSING: liveness threshold 40 rendered`.

- [ ] **Step 3: Edit `charts/halogen/values.yaml`**:
  - Under `containers.main`, before `envFrom`, add `command: [/bin/bash]` and `args: [-c, "ulimit -l unlimited\nexec /usr/local/bin/entrypoint.sh all"]` in the block YAML style already used by this chart.
  - Change liveness `failureThreshold: 6` to `40`; keep the first-start comment and all other probe numbers.
  - Add `set -e` before `ulimit -l unlimited` so a failed memlock raise stops the pod.
  - Append `HALOGEN_WEIGHTS_LOCK` with bare value `1` to the `config` list, after the four cache keys.

- [ ] **Step 4: Run it to verify GREEN** — `bash .superpowers/sdd/2026-11-27-halogen-probe-weights-lock/task1-test.sh` → expected `TASK1 PASS`.

- [ ] **Step 5: Commit** — `git add charts/halogen/values.yaml && git commit -m "feat(halogen): tolerate stalls and lock weights" && git push`.

---

### Task 2: GitOps sync, safe restart, live verification

**Files:**
- Test: `.superpowers/sdd/2026-11-27-halogen-probe-weights-lock/task2-test.sh`
- No source files; live objects only.

**Interfaces:**
- Consumes: the Deployment/ConfigMap rendered by Task 1.
- Produces: live Halogen pod with 1200 s liveness window, unlocked→locked weights, unchanged readiness/cache; PR #106 still open.

- [ ] **Step 1: Write the failing test** at `.superpowers/sdd/2026-11-27-halogen-probe-weights-lock/task2-test.sh`:

```bash
#!/bin/bash
set -euo pipefail
cd /home/titsw/.local/share/opencode/worktree/fc6729/silent-eagle
fail() { echo "MISSING: $1"; exit 1; }
CM=$(kubectl -n ollama get cm halogen-config -o json 2>/dev/null || echo '{}')
echo "$CM" | jq -e '.data.HALOGEN_WEIGHTS_LOCK == "1"' >/dev/null || fail 'weights lock in ConfigMap'
P=$(kubectl -n ollama get deploy halogen -o json 2>/dev/null || echo '{}')
echo "$P" | jq -e '.spec.template.spec.containers[0].livenessProbe.failureThreshold == 40' >/dev/null || fail 'live liveness 40'
echo "$P" | jq -e '.spec.template.spec.containers[0].readinessProbe.failureThreshold == 24' >/dev/null || fail 'live readiness 24'
echo "$P" | jq -e '[.spec.template.spec.containers[0].command[], .spec.template.spec.containers[0].args[]] | join(" ") | contains("ulimit -l unlimited")' >/dev/null || fail 'live memlock wrapper'
[[ "$(kubectl -n ollama get deploy halogen -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)" == 1 ]] || fail 'halogen ready replica'
[[ "$(kubectl -n argocd get app halogen -o jsonpath='{.spec.syncPolicy.automated.enabled}' 2>/dev/null || true)" == false ]] || fail 'automated sync restored'
kubectl -n ollama logs deploy/halogen --tail=500 2>/dev/null | grep -Fq 'checkpoint: locked' || fail 'weights lock startup line'
if kubectl -n ollama logs deploy/halogen --tail=500 2>/dev/null | grep -iE 'lock.*fail|fail.*lock|mlock.*(refus|error)'; then fail 'lock failure in logs'; fi
kubectl -n ollama exec deploy/halogen -- python3 -c '
import json,urllib.request
h=json.load(urllib.request.urlopen("http://127.0.0.1:8731/health",timeout=30))
c=json.load(urllib.request.urlopen("http://127.0.0.1:8731/cache",timeout=30))
assert h["prompt_cache"]["mode"]==2, "mode"
assert h["kv_pool_positions"]==262144, "pool"
assert h["slots"]==4, "slots"
assert h["checkpoint_format"]=="hgn", "format"
assert c["disk"]["on"] is True, "disk cache off"
assert c["max_entries"]>=36, "entries"
print("CACHE OK")' 2>&1 | grep -Fq 'CACHE OK' || fail 'live health/cache'
[[ "$(gh pr view 106 --json state --jq .state 2>/dev/null || true)" == OPEN ]] || fail 'PR #106 open'
echo 'TASK2 PASS'
```

- [ ] **Step 2: Run it to verify RED** — `bash .superpowers/sdd/2026-11-27-halogen-probe-weights-lock/task2-test.sh` → expected `MISSING: weights lock in ConfigMap`.

- [ ] **Step 3: Confirm restart is safe** — `kubectl -n ollama exec deploy/halogen -- sh -c 'for p in /proc/[0-9]*/task/*/status; do grep -q "^State:[[:space:]]*D" "$p" && echo "$p"; done | head -5'`. Expected: no output. If any path is printed, wait in 30 s checks (max 10) until none; do not restart while a thread is in D state.

- [ ] **Step 4: Sync and restore automation** — run in order:

```bash
kubectl -n argocd patch app halogen --type=merge -p '{"spec":{"syncPolicy":{"automated":{"enabled":true,"prune":true,"selfHeal":true}}}}'
kubectl -n argocd annotate app halogen argocd.argoproj.io/refresh=hard --overwrite
for i in $(seq 1 24); do
  v=$(kubectl -n ollama get cm halogen-config -o jsonpath='{.data.HALOGEN_WEIGHTS_LOCK}' 2>/dev/null || true)
  [[ "$v" == 1 ]] && { echo "synced after $i checks"; break; }
  sleep 5
done
kubectl -n argocd patch app halogen --type=merge -p '{"spec":{"syncPolicy":{"automated":{"enabled":false,"prune":true,"selfHeal":true}}}}'
kubectl -n argocd get app halogen -o jsonpath='{.spec.syncPolicy.automated.enabled}{"\n"}'
```

Expected: ConfigMap key `1`, final automated value `false`.

- [ ] **Step 5: Restart and wait** — `kubectl -n ollama rollout restart deploy/halogen && kubectl -n ollama rollout status deploy/halogen --timeout=1200s`. Expected: `deployment "halogen" successfully rolled out`. If the log does not contain `checkpoint: locked`, the lock failed: check the startup line for the reason and ledger it; do not claim success.

- [ ] **Step 6: Run the test to verify GREEN** — `bash .superpowers/sdd/2026-11-27-halogen-probe-weights-lock/task2-test.sh` → expected `TASK2 PASS`.

- [ ] **Step 7: Ledger, no repo commit** — mark Task 2 done with `task-done`; all repo changes were committed in Task 1.
