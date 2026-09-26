# ollama-swift

An ollama image that can actually reach the `ngram-map-k4v` speculative
decoding route.

`ghcr.io/tylertitsworth/ollama-swift:latest` (private)

## Why this exists

The `llama-server` shipped in `ollama/ollama:0.34.0-rocm` **already
implements** the `ngram-map-k4v` route — it is present in llama.cpp at the
`LLAMA_CPP_VERSION` that ollama v0.34.0 pins (`b10760`), and the flags are
registered:

```
--spec-type none,draft-simple,draft-eagle3,draft-mtp,draft-dflash,draft-dspark,ngram-simple,ngram-map-k,ngram-map-k4v,ngram-mod,ngram-cache
--spec-ngram-map-k4v-size-n N
--spec-ngram-map-k4v-size-m N
--spec-ngram-map-k4v-min-hits N
```

What stock ollama cannot do is *ask* for it. The Go plumbing that carries a
Modelfile `PARAMETER` down to the `llama-server` command line does not
forward `draft_spec_type` or the `draft_ngram_map_k4v_*` options, so a
Modelfile setting them is silently dropped. Without this image the ngram
route is unreachable no matter what the model card says.

So this is a **Go-binary swap on a stock ROCm base**, not a full custom
ollama build. `LLAMA_CPP_VERSION` is deliberately left alone, and no
llama.cpp rebuild is involved.

## What the patch changes

`0001-llama-server-forward-ngram-map-k4v.patch` is a backport of
[`samuelishida/ollama@fc3682f7`](https://github.com/samuelishida/ollama/commit/fc3682f78e01c5391a656f02f28762633faa0528)
onto `v0.34.0`.

| File | Change |
| --- | --- |
| `api/types.go` | `Runner` gains `draft_spec_type`, the three `draft_ngram_map_k4v_*` fields, and the three `draft_ngram_mod_*` fields |
| `llm/llama_server.go` | `appendDraftArgs` prefers `opts.DraftSpecType` over the auto-detected type and splits a comma-separated list via a new `hasSpecType`, so several routes combine in one launch; emits the `ngram-map-k4v` / `ngram-mod` flags. Also adds an `OLLAMA_LLAMA_SERVER` override |
| `discover/llama_server.go` | adds `llama-server`'s own directory to the device-discovery library path |
| `docs/*`, `*_test.go` | documentation and test expectations from upstream |

No `server/` change is needed: `api.Options` embeds `Runner` and
`Options.FromMap` resolves entries by json tag, so a Modelfile `PARAMETER`
reaches the runner through existing code.

**Carried over but not required:** the `memoryParsingWriter` rework in
`llm/llama_server.go` (draft-model VRAM accounting). It is upstream's own
validated code and it matters at a 256K context with a draft head, but the
ngram route does not depend on it.

**Left out on purpose:** the `LLAMA_CPP_VERSION` bump and
`llama/compat/001-llama-cpp-hooks.patch` (the route already exists at
`b10760`, and re-pinning would invalidate this image against its ROCm base),
and `scripts/ollama-ngram.sh` (a desktop/systemd launcher that hardcodes
`OLLAMA_HOST=127.0.0.1:11434`, which would break the in-cluster Service).

## Build

```sh
./build.sh              # build only
PUSH=1 ./build.sh       # build and push
```

Requires `docker` with buildx only for cross-platform builds. To bump the
base, change `OLLAMA_VERSION` and the `FROM` line together.

## Verify a built or pulled image

```sh
docker run --rm --entrypoint /bin/sh ollama-swift -c '
  /bin/ollama --version
  grep -ac draft_spec_type /bin/ollama
  /usr/lib/ollama/llama-server --help 2>&1 | grep spec-ngram-map-k4v
'
```

`build.sh` runs exactly this and fails the build if a marker is missing.

## In-cluster pull secret

The package is private, so the `ollama` namespace needs a pull secret:

```sh
kubectl create secret docker-registry ghcr-pull-secret \
  --namespace ollama \
  --docker-server=ghcr.io \
  --docker-username=<user> \
  --docker-password=<token with read:packages>
```

Referenced from `apps/ai/values/ollama.yaml` via `imagePullSecrets`. The
secret intentionally lives only in the cluster — this repo has no SOPS,
ExternalSecret, or SealedSecret setup, so there is nowhere in git to put it.
