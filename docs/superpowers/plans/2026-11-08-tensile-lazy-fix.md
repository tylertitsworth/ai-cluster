# Tensor lazy fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make hipBLASLt actually load tuned gfx1151 kernels in the Swift image so the `TensileLibrary_lazy_gfx1151.dat` error disappears and prompt speed improves.

**Architecture:** Add a `rocmlib` stage from `kyuz0/amd-strix-halo-toolboxes:rocm-7.1` to the Swift Dockerfile, copy `hipblaslt/library/` into Ollama's `rocm_v7_2/`, rebuild via the existing Actions workflow, smoke-test error removal + tok/s, then benchmark.

**Tech Stack:** Docker multi-stage BuildKit, `ollama/ollama:0.40.15-rocm` base (ROCm 7.2 `70201`), `kyuz0` ROCm 7.1 kernels, GitHub Actions `build-ollama-swift`.

**Spec:** Log error `rocblaslt error: Cannot read "TensileLibrary_lazy_gfx1151.dat"` — Ollama ships `libhipblaslt.so.1.2.70201` with no `hipblaslt/library/` dir; kyuz0 `opt/rocm-7.1.0/lib/hipblaslt/library/` has `Kernels.so-000-gfx1151.hsaco` (21MB) + `TensileLibrary_lazy_gfx1151.dat` (33KB).

## Global Constraints
- Do not restart/terminate prod pod except as the final Argo swap step.
- Keep model Q6_K, context 131072, MTP4, `q8_0`, `b2048`, `ROCBLAS_USE_HIPBLASLT=1` unchanged.
- Tag stays dynamic from Dockerfile `OLLAMA_VERSION` (`0.40.15-tuned`, `0.40.15-swift-tuned`).

## Review Focus
- Wrong dest path — hipBLASLt still can’t find lazy file (fix: dest `rocm_v7_2/hipblaslt/library/`).
- ROCm 7.1 vs 7.2 mismatch — kernels for 7.1 loaded by 7.2 runtime (fix: pin to rocm-7.1, record fallback risk).
- Missing Kernels.so — copying only .dat still fails (fix: copy whole `library/` dir).
- Silent fallback — error gone but still slow (fix: assert marker + benchmark).
- Image bloat / layer cache — 21MB+ added (fix: single COPY layer, no extra stage artefacts).

---
### Task 1: Fix Dockerfile to ship gfx1151 hipBLASLt kernels

**Files:**
- Modify: `ollama-swift/Dockerfile`
- Modify: `ollama-swift/build.sh` (assert lazy file present)

**Interfaces:**
- Consumes: `kyuz0/amd-strix-halo-toolboxes:rocm-7.1` at `/opt/rocm-7.1.0/lib/hipblaslt/library/`
- Produces: new image with `/usr/lib/ollama/rocm_v7_2/hipblaslt/library/TensileLibrary_lazy_gfx1151.dat` + `Kernels.so-000-gfx1151.hsaco`

- [ ] **Step 1: Write the failing assert (in build.sh verify block)**

```bash
# in ollama-swift/build.sh verify step, after marker loop:
test -f /usr/lib/ollama/rocm_v7_2/hipblaslt/library/TensileLibrary_lazy_gfx1151.dat && echo "lazy ok" || { echo "LAZY MISSING"; exit 1; }
test -f /usr/lib/ollama/rocm_v7_2/hipblaslt/library/Kernels.so-000-gfx1151.hsaco && echo "kernels ok" || { echo "KERNELS MISSING"; exit 1; }
```

- [ ] **Step 2: Run it (expect FAIL)**

`./ollama-swift/build.sh` or manual `grep -c lazy` — it will fail because the file is missing today. Expected: `LAZY MISSING`.

- [ ] **Step 3: Implement — add rocmlib stage to Dockerfile**

```dockerfile
# Stage 2.5: gfx1151 hipBLASLt kernels (fixes TensileLibrary_lazy_gfx1151.dat)
FROM docker.io/kyuz0/amd-strix-halo-toolboxes:rocm-7.1 AS rocmlib
# ... after stage 2 COPY, add:
COPY --from=rocmlib /opt/rocm-7.1.0/lib/hipblaslt/library/ /usr/lib/ollama/rocm_v7_2/hipblaslt/library/
```

- [ ] **Step 4: Run it (expect PASS)**

Build via Actions (see Task 2) then `docker run --rm --entrypoint ls <image> /usr/lib/ollama/rocm_v7_2/hipblaslt/library/TensileLibrary_lazy_gfx1151.dat` → file present. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ollama-swift/Dockerfile ollama-swift/build.sh
git commit -s -m "ollama-swift: ship gfx1151 hipBLASLt kernels (fixes lazy .dat)"
```

### Task 2: Rebuild and push via Actions

**Files:**
- Modify: none (reuse `.github/workflows/build-ollama-swift.yaml` — triggers on `ollama-swift/**` push)

**Interfaces:**
- Consumes: Task 1 Dockerfile
- Produces: pushed `ai-cluster-ollama-swift:0.40.15-tuned` + `0.40.15-swift-tuned` with new digest

- [ ] **Step 1: Push the branch**

`git push origin build/ollama-swift-dockerfile` (or current branch) — triggers `build-ollama-swift` on `ollama-swift/**`.

- [ ] **Step 2: Wait for green**

`gh run list --branch <branch> --limit 1` and `gh run view <id> --json conclusion` → `success`. Expected: build + push succeed (same as 42425796501).

- [ ] **Step 3: Verify tags**

`docker manifest inspect ghcr.io/tylertitsworth/ai-cluster-ollama-swift:0.40.15-tuned` shows new digest. Expected: digest ≠ `1990735…`.

- [ ] **Step 4: Commit (none — record in ledger)**

`Task 2: complete (run <id>, digest <new>)`

### Task 3: Deploy and smoke-test (error gone + MTP intact)

**Files:**
- Modify: none (uses Task 2 image; no values change — env `ROCBLAS_USE_HIPBLASLT=1` already in image)

**Interfaces:**
- Consumes: Task 2 image
- Produces: live pod with no `TensileLibrary_lazy` error, MTP still active

- [ ] **Step 1: Swap prod to new image (only this restart)**

`kubectl -n argocd patch application ollama` → sync (or `kubectl rollout restart deployment/ollama -n ollama` after pointing values to new digest tag). Wait for `1/1 Running` + `/api/ps` digest updated.

- [ ] **Step 2: Assert no Tensile error**

`kubectl logs -n ollama <new-pod> | grep -i Tensile` → empty. Expected: no lines (old prod shows 2 lines).

- [ ] **Step 3: Assert MTP intact**

`kubectl logs -n ollama <pod> | grep -E "spec-type|draft-mtp|ROCBLAS_USE"` → shows `--spec-type draft-mtp,ngram-map-k4v --spec-draft-n-max 4` and `ROCm0 gfx1151`. Expected: present.

- [ ] **Step 4: Assert lazy file in pod**

`kubectl exec -n ollama <pod> -- ls /usr/lib/ollama/rocm_v7_2/hipblaslt/library/TensileLibrary_lazy_gfx1151.dat` → present.

- [ ] **Step 5: Commit (ledger)**

`Task 3: complete (error gone, MTP ok, pod <name>)`

### Task 4: Benchmark prompt speed (same prompts as before)

**Files:**
- Modify: `docs/superpowers/benchmarks/2026-11-07-vulkan-vs-hip.md` (append table, not in PR)

**Interfaces:**
- Consumes: Task 3 live pod
- Produces: before/after prompt tok/s delta

- [ ] **Step 1: Run the 3 canonical prompts via tailscale API**

```bash
# via https://ollama.tail79a5c8.ts.net/v1/chat/completions, temp 0, max_tokens 160:
# small "Reply with exactly: ok" (32), mid "*900 fox" (~10k), large "*3400 fox" (~34k)
```

- [ ] **Step 2: Capture print_timing**

`kubectl logs -n ollama <pod> | grep -E "prompt eval|eval time|draft acceptance"` → record pp/tg. Baseline (0.40.15-swift today): mid 328.91/19.76, 34k 286.20/15.33. Expect pp lift (hipBLASLt win is prefill), gen within ±10%.

- [ ] **Step 3: Fill table**

Append to benchmark doc: `| 10,810 | 328.91 | X | 19.76 | Y |` etc. Expected: decide keep/drop `ROCBLAS_USE_HIPBLASLT=1` from data.

- [ ] **Step 4: Ledger**

`Task 4: complete (pp <old>→<new>, tg <old>→<new>, keep hipBLASLt: yes/no)`

## Self-Review
- Spec coverage: add file [T1], trigger rebuild [T2], push+test improves perf [T3+T4] — all covered.
- Step scan: each step one action + check; no body transcripts.
- Type consistency: dest path `rocm_v7_2/hipblaslt/library/` used in all tasks; tag names consistent.
- Review Focus: 5 lines above each pinned to T1/T3/T4 test.
- Proportion: plan ~1.5x code, acceptable.
