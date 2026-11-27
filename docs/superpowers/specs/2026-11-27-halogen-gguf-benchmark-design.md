# Halogen GGUF benchmark on framework-desktop

## Intent

Find out whether Halogen's published Qwen3.8-27B speed (37.9 drafted / 15.1 serial decode, 578 / 605 / 530 tok/s prefill) comes from its engine rather than its 4-bit checkpoint, by serving **our existing GGUF weights** on Halogen's own image and running **Halogen's own benchmark**. The result is a filled comparison table, not a permanent service change. Everything lands on a branch and an open, unmerged PR.

## Goals

- New `charts/halogen` chart and `apps/ai/halogen.yaml` Application on a branch cut from `origin/main` (`3566581`), PR into `main`, never merged.
- Serve the same weights llama.cpp currently serves: `hf.co/ukisai/Swift-Qwen3.8-27B-GGUF:Q6_K` (GGUF `qwen35`, 22.87 GB). On the `ollama-data` PVC the Ollama blob has no extension; a hardlink `qwen38-27b-swift-q6k.gguf` (same inode, no extra disk) gives Halogen the `.gguf` suffix it requires.
- Match the published setup 1:1 wherever the 64 GB box allows: image `halogen-flash-server:0.21.0`, `HALOGEN_CTX=262144`, `HALOGEN_PROMPT_CACHE=2`, `HALOGEN_KV_SLOTS=4`, default `HALOGEN_MAX_TOK`, no vision tower, no LoRA, no RoPE scaling.
- Tailscale ingress named `halogen` (same class/proxy pattern as `vllm`).
- Scale the llama.cpp server to zero through GitOps on the same branch, so the APU is free for the benchmark.
- Run `bench serial,mtp 256 low 3` and cold `sweep -p 8192,32768 -n 128` (with `HALOGEN_PROMPT_CACHE=0`) from inside the Halogen pod, then fill the comparison table.

## Non-goals

- No merge to `main`, no permanent cutover of `ollama`/`open-webui` traffic.
- No kernel, ROCm, GRUB, or BIOS changes in this PR — those were decided separately.
- No download of `qwen38-27b-ht4.hgn` unless the GGUF start is refused; that is phase 2.
- No new benchmark harness: use the CLI shipped in the Halogen image.

## Anti-goals

- Leaving the cluster in a kubectl-only state that Argo would later revert.
- Reporting published numbers as if measured on this box.
- Taking the service down with no route back (the branch/PR is the route back).

## Constraints

- `framework-desktop`: Ryzen AI Max+ 395 / gfx1151, **64 GB** unified memory, 56 GiB GTT, Ubuntu 25.10 kernel 6.17, ROCm 7.2.0, k3s worker.
- Halogen's published defaults assume 128 GB and a 20 GiB host reserve; they do not fit here with Q6_K weights.
- The existing `ollama-data` PVC is 100 GiB and already holds the GGUF. No spare models PVC is assumed.
- This harness reaches the box through `kubectl` and the tailnet HTTPS ingress, not direct port 11434.
- A leftover Helm-created `halogen` Deployment/Service exists in namespace `ollama` with 0 replicas; there is **no** Argo Application named `halogen`.

## Approaches

1. **Chosen: new chart, GGUF first.** Add a fresh app-template chart on a new branch; point both the new `halogen` Application and the existing `llama-cpp` Application at that branch; scale llama.cpp to 0; run the benchmark; keep a single value toggle to the ht4 checkpoint for phase 2. Best match to the request, keeps GitOps authoritative, and the fallback costs one value change rather than a new PR.
2. **ht4 first.** Guaranteed to match the published numbers and fits memory more easily, but skips the GGUF question that motivated the test. Kept as the phase-2 toggle in approach 1.
3. **Revive `add/halogen`.** Rejected: it pins `halogen:0.1.4` and `HALOGEN_SLOT_CTX`, which 0.21.0 does not load, and the branch carries unrelated deletions from a stale base.

## Decisions

**Calls made after the builder check (check these while reading):**

- **One container, not the split compose topology.** The README quickstart and the BYO-GGUF recipe both use a single container serving `:8731`; the `engine`/`api` compose split is an optional topology, not a requirement. The chart uses one container with one `/health` probe and one service.
- **`HALOGEN_DOWNLOAD=peonist-ai/halogen-qwen3.8-flash-next` supplies the head, not the weights.** The 27B repo contains no standalone `.hgn` draft head — only `qwen38-27b-ht4.hgn` (head baked in), the vision tower, and the tokenizer. Halogen's GGUF path insists on `qwen38-flash-next-mtp.hgn`; that file lives in the flash-next repo, whose tokenizer is documented as identical to 27B's. No ht4 checkpoint is fetched at phase 1: `HALOGEN_CHECKPOINT` names the GGUF explicitly. If the engine refuses the GGUF or its head, flip both the checkpoint and download repo to phase 2 and report that as the result.
- **Delete the leftover Helm `halogen` Deployment/Service before the first Argo sync**, so Argo creates fresh objects instead of colliding with a Helm-owned release. This is a one-time cleanup, after which Argo is authoritative.
- **Results go in `docs/benchmarks/halogen-vs-llamacpp-2026-11-27.md` on the branch**, committed, and are summarised in the PR body.

**Forced deviations (name these in the PR):** Halogen's published default KV pool is two full conversations at 524,288 positions; with Q6_K (~21 GiB repacked) + 1.4 GiB draft head + ~12 GiB working set it cannot fit 64 GB. Keep the request context and cache 1:1, shrink only the residency knobs:

| Setting | Published | This chart | Reason |
|---|---|---|---|
| `HALOGEN_CTX` | 262144 | **262144** | 1:1 request context |
| `HALOGEN_PROMPT_CACHE` | 2 | **2** | 1:1 caching |
| `HALOGEN_KV_SLOTS` | 4 | **4** | 1:1 concurrency |
| `HALOGEN_KV_POOL_POSITIONS` | 524288 | **262144** | ~18 GiB instead of ~36 GiB; still one full 262k conversation or four at 65k |
| `HALOGEN_HOST_RESERVE_GIB` | 20 | **8** | matches the existing 56 GiB GTT / 8 GiB host split; prevents auto-lowering the pool |

If startup logs `LOWERING THE POOL TO N`, record the actual `pool N/<positions>` value and treat that as the tested configuration; do not silently accept a smaller pool.

**Files on branch `add/halogen-gguf`:**

- `charts/halogen/Chart.yaml`, `Chart.lock` — app-template 3.5.1, appVersion `0.21.0`, modelled on `charts/vllm`.
- `charts/halogen/values.yaml` — deployment pinned to `framework-desktop`, `amd.com/gpu: 1`, privileged + host IPC for KFD/DRI and shared memory, `/health` probes with long initial delays for first-start repack/download, service 8731, tailscale ingress host `halogen` with `tailscale.com/proxy-class: pin-framework-desktop` and TLS, config map entries below.
- `charts/halogen/templates/configmap.yaml` — renders `.Values.config` into `halogen-config`, same shape as the old chart.
- `apps/ai/halogen.yaml` — Application, both sources `targetRevision: add/halogen-gguf`, destination `ollama`, automated sync **disabled** so the cutover is deliberate.
- `apps/ai/llama-cpp.yaml` — `targetRevision: add/halogen-gguf`; `apps/ai/llamacpp/deployment.yaml` — `replicas: 0`.
- One documented phase-2 switch: `HALOGEN_CHECKPOINT=/root/.ollama/qwen38-27b-ht4.hgn` and `HALOGEN_DOWNLOAD=peonist-ai/halogen-qwen3.8-27b-ht4` (the latter is only needed if the ht4 file is not already on the PVC).

**Environment (phase 1):** `HALOGEN_CHECKPOINT` = the `.gguf` hardlink to the existing GGUF blob; `HALOGEN_DOWNLOAD=peonist-ai/halogen-qwen3.8-flash-next` so the draft head and tokenizer land beside the GGUF; `HALOGEN_API_PORT=8731`; `HALOGEN_MODEL_ID=halogen-qwen3.8-27b`; `HALOGEN_TOKENIZER=/root/.ollama/models/blobs/tokenizer` (the download writes it beside the head, not under `/models`); plus the five table entries above. Keep `HALOGEN_KV8`, `HALOGEN_VISION_TOWER`, `HALOGEN_ROPE_YARN`, and `HALOGEN_GGUF_CACHE` unset.

**Persistence:** mount the existing `ollama-data` PVC read-write at `/root/.ollama`. It holds the GGUF, and is writable so `HALOGEN_DOWNLOAD` can place the head/tokenizer (and, in phase 2, the ht4 file) there. No new PVC.

**Benchmark:** use the image's own CLI inside the pod. Decode from `bench serial,mtp 256 low 3`; cold prefill from `sweep -p 8192,32768 -n 128` with prompt cache off. Record `bench` output, any `LOWERING THE POOL` line, and `/health` `checkpoint_format`. Put the measured rows into the comparison table alongside the published Halogen and measured llama.cpp rows, with the deviations listed.

## Resolved during the build

- The MTP head is `qwen38-flash-next-mtp.hgn`, fetched from `peonist-ai/halogen-qwen3.8-flash-next`; the 27B repo has no standalone head. Tokenizer files are the same for both models; `HALOGEN_TOKENIZER` must point at the `tokenizer/` folder written beside the head.
- The checkpoint path needs a `.gguf` suffix: a hardlink to the extensionless Ollama blob was added on the PVC (same inode, no extra disk).
- `amd.com/gpu` plus `privileged`/`hostIPC` starts the container; the initial `FailedScheduling` was a terminating llama.cpp pod still holding the single GPU, not a device-injection problem.
- `helm dependency update` and `helm template` pass; the lock file is committed.
- Cold `sweep` invocation is pinned in Task 5 of the implementation plan and remains to be run.
