# Halogen prompt-cache tuning for agentic OpenCode — design

## Intent

Make the already-running Halogen 0.21.0 server the primary backend for agentic
development in OpenCode. The benchmark PR (#106) established the service; this
change tunes only its prompt cache for multi-turn, subagent-heavy work.

## Goals

- Keep `HALOGEN_PROMPT_CACHE=2` (the mode that resumes from the start of the
  last message and the end of every request).
- Let conversations survive a pod restart by persisting the prompt cache on
  the existing PVC.
- Keep a parent conversation's resume point when subagents fan out from it.
- Leave the ConfigMap GitOps-authoritative with no stale Helm-era keys.

## Non-goals

- No model, checkpoint, tokenizer, context, KV-pool, or slot changes.
- No OpenCode client changes — it already targets
  `https://halogen.tail79a5c8.ts.net/v1` with model `halogen-qwen3.8-27b`.
- No merging of PR #106, no second engine, no port-forward.

## Constraints

- One container on `framework-desktop`, 64 GB unified memory, image pinned to
  `ghcr.io/peonist-ai/halogen-flash-server:0.21.0`.
- PVC `ollama-data`: 100 GiB, 62 GiB free; mounted read-write at
  `/root/.ollama`.
- Current startup: 12.8 GiB weights, 18.3 GiB KV pool, 13.5 GiB working,
  ~7.3 GiB host left. Defaults `HALOGEN_CTX=262144`, pool 262144, 4 slots.
- Argo automated sync stays `false` at rest; temporary enable for sync only.

## Approaches

- **A — chosen: tune in place on `add/halogen-gguf`.** Add four config entries
  to `charts/halogen/values.yaml`, remove the stale ConfigMap so Argo rebuilds
  it from the chart, restart the Deployment, verify the live cache. One
  restart loses the current in-memory cache once; after that, conversations
  survive restarts.
- **B — rejected: leave defaults.** Mode 2 already works for a single long
  conversation, but nothing survives a restart and a two-child fan-out
  replaces the parent's resume point.
- **C — rejected: new production PR from `origin/main`.** Cleaner separation,
  but it duplicates the chart and Argo Application that #106 already owns.

## Changes

`charts/halogen/values.yaml` `config` additions:

| Key | Value | Why |
|---|---|---|
| `HALOGEN_CACHE_DIR` | `/root/.ollama/halogen-cache` | Persist the prompt cache on the PVC so a restart resumes conversations. |
| `HALOGEN_CACHE_DISK_GIB` | `32` | Bound disk use to half the free PVC space; ~27 KiB/token means ~1.2M tokens of cached context. |
| `HALOGEN_CACHE_BRANCHES` | `3` | Parent plus two subagents; the parent's resume point survives fan-out. |
| `HALOGEN_CACHE_ENTRIES` | `36` | Four conversations x 9 entries at three branches (was 28 = 4 x 7). |

Do not re-add the stale live keys `HALOGEN_CACHE_MB`,
`HALOGEN_CACHE_RESERVE_MB`, or `HALOGEN_SLOT_CTX`: none exists in 0.21.0 and
they are ignored.

One-time cleanup: delete `cm/halogen-config` in `ollama` and let Argo recreate
it from the chart, so those legacy keys cannot survive another apply.

## Verification

- `helm template halogen charts/halogen` contains all four new keys with the
  exact values and none of the three stale keys.
- Argo app `halogen` synced; ConfigMap has exactly the chart's keys; rollout
  ready; `/health` still mode 2, pool 262144, slots 4, `checkpoint_format: hgn`.
- `/cache` reports `disk.on: true` after at least one request, no
  `direct I/O`/cache-dir refusal in the logs.
- PR #106 still `OPEN`, base `main`, head `add/halogen-gguf`.

## Rollback

Revert the commit and re-sync; the old ConfigMap had only ignored legacy keys.
