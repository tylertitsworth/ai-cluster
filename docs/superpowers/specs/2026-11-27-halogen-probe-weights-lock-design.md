# Halogen probe tolerance and weights lock — design

## Intent

Stop Kubernetes from restarting the server during host-memory stalls that
Halogen itself treats as recoverable, and stop the kernel from reclaiming the
model weights to make room for the lookup table.

## Goals

- Liveness must not restart the pod before Halogen's own watchdog has finished
  its 900 s compaction deferral (`HALOGEN_ENGINE_WATCHDOG_DEFER_S`).
- `HALOGEN_WEIGHTS_LOCK=1` must actually lock the weights, not silently run
  unlocked because the container's memlock limit is too low.
- Preserve the cache tuning, the ht4 checkpoint, context/pool slots, GitOps
  authority, Tailscale ingress, and PR #106 open/unmerged.

## Non-goals

- No change to readiness (currently 24 × 15 s = 360 s; it only removes the pod
  from the Service and does not kill work).
- No change to Halogen's watchdog settings, model, KV pool, or cache flags.
- No OpenCode client change, second engine, port-forward, or merge.

## Constraints

- Chart is Helm/app-template with a single privileged root container; image
  pinned to `ghcr.io/peonist-ai/halogen-flash-server:0.21.0`.
- `/health` returns 503 when the engine does not answer an internal PING; that
  is expected during compaction or a long prompt, not proof the server is dead.
- Upstream: the watchdog waits 180 s, defers up to 900 s while the kernel
  compacts, and never kills a thread in uninterruptible sleep (issue #79).
- Upstream: weights lock uses `mlock`; it needs the memlock limit to cover the
  weights, and a failed lock leaves the server running unlocked with a startup
  line saying why. Live container: `ulimit -H -l` is 8192 KiB, but root in the
  privileged container can raise it to unlimited, verified in the running pod.
- The lookup table is never locked and still streams through the page cache;
  locking weights reduces reclaim but cannot stop host compaction by itself.
- Locked pages are unavailable to a co-tenant: on an over-committed host the
  OOM killer may pick this server (exit 137). Do not add other heavy work to
  this node.
- The engine was stalled when this work started; restart only when no engine
  thread is in uninterruptible (D) state, so the GPU driver cannot be left
  holding GPU memory.

## Approaches

- **A — chosen: widen liveness, lock weights.** `failureThreshold: 30` at
  `periodSeconds: 30` gives a 900 s failure window, matching the watchdog's
  deferral cap, while keeping a last-resort restart for a hung API process.
  Raise memlock in the container command and set `HALOGEN_WEIGHTS_LOCK=1`.
- **B — rejected: remove liveness.** Halogen's watchdog is better informed,
  but there would be no Kubernetes restart net if the API process hung while
  the engine was fine.
- **C — rejected: leave liveness at 180 s.** It can restart during a stall
  Halogen would forgive, killing an in-flight agentic turn.
- **Weights lock without raising memlock — rejected:** the 8 MiB limit is far
  below the ~12.8 GiB checkpoint, so the server would start unlocked.

## Changes

`charts/halogen/values.yaml`:

- `controllers.halogen.containers.main.probes.liveness.spec.failureThreshold`:
  `6` → `30` (the comment about the first-start download stays).
- `config`: add `HALOGEN_WEIGHTS_LOCK=1`.
- `controllers.halogen.containers.main`: add a command wrapper
  `/bin/bash -c 'ulimit -l unlimited; exec /usr/local/bin/entrypoint.sh all'`
  so `mlock` can cover the weights.

## Verification

- `helm template halogen charts/halogen` renders liveness `failureThreshold:
  30`, readiness unchanged at 24, ConfigMap `HALOGEN_WEIGHTS_LOCK: "1"`, and
  the command/args wrapper.
- Argo app `halogen` synced from git; automated sync restored to `false`;
  rollout 1/1.
- ConfigMap has the exact chart key set; no legacy cache keys.
- Startup log contains a `checkpoint: locked ...` line and no lock failure;
  `/health` still reports mode 2, pool 262144, slots 4, `checkpoint_format: hgn`;
  `/cache` still has `disk.on: true` and `max_entries: 36`.
- PR #106 remains `OPEN`, base `main`, head `add/halogen-gguf`.

## Rollback

Revert the commit and re-sync; the previous liveness window and unlocked
startup are the prior working state.
