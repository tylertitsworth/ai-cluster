# Halogen GGUF Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the existing Swift Q6_K GGUF on Halogen 0.21.0 via a GitOps-managed chart on branch `add/halogen-gguf`, cut the llama.cpp server down, run Halogen's own benchmarks, and record the measured comparison in an unmerged PR.

**Architecture:** A new app-template Helm chart supplies one privileged Deployment pinned to `framework-desktop`, reusing the `ollama-data` PVC for the GGUF, downloaded head/tokenizer, and optional phase-2 checkpoint. Two Argo Applications on the branch control the Halogen server and the llama.cpp scale-down; the image's own `bench`/`sweep` CLI produces the numbers.

**Tech Stack:** Helm 4 / app-template 3.5.1, Argo CD, k3s, kubectl, gh CLI, `ghcr.io/peonist-ai/halogen-flash-server:0.21.0`.

**Spec:** `docs/superpowers/specs/2026-11-27-halogen-gguf-benchmark-design.md`

## Global Constraints

- Branch: `add/halogen-gguf`, cut from `origin/main` (`3566581`). PR base `main`. **Never merge.**
- Image: `ghcr.io/peonist-ai/halogen-flash-server:0.21.0` (pinned; `halogen:0.1.4` cannot load 0.21.0 files).
- Checkpoint phase 1: `/root/.ollama/models/blobs/qwen38-27b-swift-q6k.gguf` — a hardlink (same inode, no extra disk) to the Ollama blob `sha256-7f4de8abd5446c08b0f975a1b38e43d02639f4ae9ecdd2ddfd5c5b0f612bda59`; Halogen detects GGUF by the `.gguf` suffix.
- `HALOGEN_CTX=262144`, `HALOGEN_PROMPT_CACHE=2`, `HALOGEN_KV_SLOTS=4` — 1:1 with published defaults.
- Deviations: `HALOGEN_KV_POOL_POSITIONS=262144`, `HALOGEN_HOST_RESERVE_GIB=8`.
- `HALOGEN_DOWNLOAD=peonist-ai/halogen-qwen3.8-flash-next` (only the MTP head + tokenizer are fetched; the 27B repo has no standalone head); `HALOGEN_API_PORT=8731`; `HALOGEN_MODEL_ID=halogen-qwen3.8-27b`.
- Leave unset: `HALOGEN_KV8`, `HALOGEN_VISION_TOWER`, `HALOGEN_ROPE_YARN`, `HALOGEN_GGUF_CACHE`.
- Node `framework-desktop`; PVC `ollama-data` mounted read-write at `/root/.ollama`; ingress className `tailscale`, host `halogen`, proxy-class `pin-framework-desktop`, TLS.
- Benchmark: `bench serial,mtp 256 low 3`; cold `sweep -p 8192,32768 -n 128` with `HALOGEN_PROMPT_CACHE=0`.

## Review Focus

- **64 GB fit:** if startup logs `LOWERING THE POOL TO N`, the tested config differs from the spec — Task 4 records the actual `pool N/<positions>` from `/health` and Task 5 reports it.
- **GGUF refusal / missing draft head:** the 27B repo has no standalone head; if the engine refuses the Swift GGUF, Task 5 switches the checkpoint to `qwen38-27b-ht4.hgn` and reruns rather than reporting a bogus number.
- **Ingress collision:** the tailnet name `halogen` must be new; Task 1 asserts the ingress host/class/proxy-class before anything is applied.
- **GitOps drift:** a kubectl-only revision change would be reverted later; Task 2 changes both repo manifests and Task 4 restores the live app's `automated.enabled=false` after the initial sync.
- **Benchmark comparability:** cache-off, 256 greedy tokens, and 8192/32768 prompt sizes must be exactly the published shapes; Task 5 pins the commands and asserts the captured output contains timings.

---

### Task 1: Halogen Helm chart

**Files:**
- Create: `charts/halogen/Chart.yaml`
- Create: `charts/halogen/Chart.lock` (generated)
- Create: `charts/halogen/values.yaml`
- Create: `charts/halogen/templates/configmap.yaml`

**Interfaces:**
- Produces: ConfigMap `halogen-config` in the release namespace; Deployment/Service named `halogen`; port `8731`; `.Values.config` as a list of `{key, value}` entries.

- [ ] **Step 1: Create `charts/halogen/Chart.yaml`** with `apiVersion: v2`, `name: halogen`, `description: Halogen inference server (Qwen3.8-27B GGUF benchmark)`, `type: application`, `version: 0.1.0`, `appVersion: "0.21.0"`, dependency `app-template` version `3.5.1` from `https://bjw-s-labs.github.io/helm-charts/`.

- [ ] **Step 2: Create `charts/halogen/templates/configmap.yaml`** with exactly:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: halogen-config
  namespace: {{ .Release.Namespace }}
data:
  # Halogen is configured entirely through environment variables.
{{ range .Values.config }}  {{ .key }}: {{ .value | quote }}
{{ end }}
```

- [ ] **Step 3: Create `charts/halogen/values.yaml`** following `charts/vllm/values.yaml` structure: `app-template.controllers.halogen` (deployment, 1 replica, Recreate, image `ghcr.io/peonist-ai/halogen-flash-server` tag `0.21.0` pullPolicy `IfNotPresent`, `envFrom` referring to `halogen-config`, readiness/liveness `/health:8731` with `initialDelaySeconds: 300` readiness and `7200` liveness, `amd.com/gpu: "1"` request+limit, `privileged: true`, `hostIPC: true`, node affinity `kubernetes.io/hostname In framework-desktop`); `service.main` ClusterIP port 8731; `ingress.main` enabled, class `tailscale`, annotation `tailscale.com/proxy-class: pin-framework-desktop`, host `halogen`, path `/` Prefix, TLS host `halogen`; `persistence.models` existing PVC `ollama-data`, global mount `/root/.ollama`; and `config` entries for all Global Constraints env vars with their exact values.

- [ ] **Step 4: Generate the lock file** — Run: `helm dependency update charts/halogen` — Expected: `charts/halogen/Chart.lock` created with app-template 3.5.1.

- [ ] **Step 5: Render and assert** — Run: `helm template halogen charts/halogen > /tmp/halogen-rendered.yaml`, then assert the rendered YAML contains `image: ghcr.io/peonist-ai/halogen-flash-server:0.21.0`, `HALOGEN_CTX: "262144"`, `HALOGEN_KV_POOL_POSITIONS: "262144"`, `HALOGEN_HOST_RESERVE_GIB: "8"`, `HALOGEN_PROMPT_CACHE: "2"`, `HALOGEN_KV_SLOTS: "4"`, the SHA256 blob path, `host: halogen`, `className: tailscale`, `pin-framework-desktop`, `claimName: ollama-data`, `replicas: 1`, and no `HALOGEN_VISION_TOWER` key. Expected: all present.

- [ ] **Step 6: Commit**

```bash
git add charts/halogen
git commit -m "feat(halogen): add chart for Qwen3.8-27B GGUF benchmark"
```

### Task 2: Argo applications and llama.cpp scale-down

**Files:**
- Create: `apps/ai/halogen.yaml`
- Create: `apps/ai/values/halogen.yaml`
- Modify: `apps/ai/llama-cpp.yaml:15`
- Modify: `apps/ai/llamacpp/deployment.yaml:8`

**Interfaces:**
- Consumes: chart path `charts/halogen` from Task 1.
- Produces: Applications `halogen` and `llama-cpp` on `targetRevision: add/halogen-gguf`; llama-cpp `replicas: 0`.

- [ ] **Step 1: Create `apps/ai/halogen.yaml`** modelled on `apps/ai/vllm.yaml`: name `halogen`, namespace `argocd`, label `stack: ai`, two sources with `targetRevision: add/halogen-gguf` (chart source `path: charts/halogen`, `helm.valueFiles: [$values/apps/ai/values/halogen.yaml]`; second source same revision with `ref: values`), destination namespace `ollama`, `syncPolicy.automated.enabled: false`, `prune: true`, `selfHeal: true`, `syncOptions: [CreateNamespace=true]`, plus the deployment-revision `ignoreDifferences` from `apps/ai/vllm.yaml`.

- [ ] **Step 2: Create `apps/ai/values/halogen.yaml`** with a comment documenting that the phase-2 switch is a one-line edit to the `HALOGEN_CHECKPOINT` entry in `charts/halogen/values.yaml` (the app value file stays otherwise empty so the chart defaults apply).

- [ ] **Step 3: Change `apps/ai/llama-cpp.yaml:15`** from `targetRevision: main` to `targetRevision: add/halogen-gguf`.

- [ ] **Step 4: Change `apps/ai/llamacpp/deployment.yaml:8`** from `replicas: 1` to `replicas: 0`.

- [ ] **Step 5: Assert repo state** — Run: `grep -q 'targetRevision: add/halogen-gguf' apps/ai/halogen.yaml && grep -q 'targetRevision: add/halogen-gguf' apps/ai/llama-cpp.yaml && grep -q 'replicas: 0' apps/ai/llamacpp/deployment.yaml` — Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add apps/ai/halogen.yaml apps/ai/values/halogen.yaml apps/ai/llama-cpp.yaml apps/ai/llamacpp/deployment.yaml
git commit -m "feat(halogen): add Argo app and scale llama.cpp to zero on branch"
```

### Task 3: Publish the branch and open the PR

**Files:** none (remote state).

**Interfaces:** Produces PR with head `add/halogen-gguf`, base `main`.

- [ ] **Step 1: Push** — Run: `git push -u origin add/halogen-gguf` — Expected: new remote branch created.

- [ ] **Step 2: Open PR** — Run: `gh pr create --base main --head add/halogen-gguf --title "Halogen GGUF benchmark on framework-desktop" --body "GGUF-first Halogen 0.21.0 benchmark app. References docs/superpowers/specs/2026-11-27-halogen-gguf-benchmark-design.md. Deviations: HALOGEN_KV_POOL_POSITIONS=262144, HALOGEN_HOST_RESERVE_GIB=8. Do not merge."` — Expected: PR URL printed.

- [ ] **Step 3: Assert PR state** — Run: `gh pr view --json baseRefName,headRefName,state` — Expected: `baseRefName: main`, `headRefName: add/halogen-gguf`, `state: OPEN`.

### Task 4: Cut the cluster over to Halogen

**Files:** none (live cluster state; repo is already correct from Task 2).

**Interfaces:** Consumes: Applications from Task 2. Produces: running Halogen pod, llama.cpp at zero replicas, live app `automated.enabled=false` matching the repo.

- [ ] **Step 1: Remove stale Helm objects** — Run: `kubectl -n ollama delete deploy halogen svc halogen --ignore-not-found` — Expected: both removed (ignore not-found).

- [ ] **Step 2: Apply branch Applications** — Run: `kubectl apply -f apps/ai/halogen.yaml -f apps/ai/llama-cpp.yaml` — Expected: `application.argoproj.io/halogen created`, `application.argoproj.io/llama-cpp configured`.

- [ ] **Step 3: Trigger the initial sync** — Run: `kubectl -n argocd patch app halogen --type=merge -p '{"spec":{"syncPolicy":{"automated":{"enabled":true,"prune":true,"selfHeal":true}}}}'` — Expected: patch accepted; Argo starts syncing.

- [ ] **Step 4: Assert workloads** — Run: `kubectl -n ollama rollout status deploy/halogen --timeout=900s` and `kubectl -n ollama get deploy llama-cpp -o jsonpath='{.spec.replicas}'` — Expected: Halogen rollout complete, llama-cpp replicas `0`, no llama-cpp Pods.

- [ ] **Step 5: Assert the served configuration** — Run: `kubectl -n ollama exec deploy/halogen -- sh -c 'curl -s localhost:8731/health'` and `kubectl -n ollama logs deploy/halogen --tail=500 | grep -iE "LOWERING THE POOL|checkpoint_format"` — Expected: `/health` reports `checkpoint_format: gguf` (or `gguf-cache`) and a pool equal to 262144; record any `LOWERING THE POOL TO N` line verbatim for the results doc.

- [ ] **Step 6: Restore the repo-matching sync policy** — Run: `kubectl -n argocd patch app halogen --type=merge -p '{"spec":{"syncPolicy":{"automated":{"enabled":false,"prune":true,"selfHeal":true}}}}'` then assert `kubectl -n argocd get app halogen -o jsonpath='{.spec.syncPolicy.automated.enabled}'` is `false` — Expected: false.

### Task 5: Benchmark and record results

**Files:**
- Create: `docs/benchmarks/halogen-vs-llamacpp-2026-11-27.md`

**Interfaces:**
- Consumes: running Halogen pod from Task 4, llama.cpp numbers from the earlier session (prefill 347/330/280 tok/s, drafted decode 23.9 tok/s).

- [ ] **Step 1: Find the benchmark CLI in the image** — Run: `kubectl -n ollama exec deploy/halogen -- sh -c 'command -v halogen || command -v flash_serve || ls /usr/local/bin'` — Expected: exact executable path recorded for the next steps.

- [ ] **Step 2: Run the decode benchmark** — Run: `kubectl -n ollama exec deploy/halogen -- <CLI> bench serial,mtp 256 low 3 | tee /tmp/halogen-bench.txt` — Expected: output contains `serial` and `mtp` rows with `tok/s` values.

- [ ] **Step 3: Run the cold prefill sweep** — Run: `kubectl -n ollama exec deploy/halogen -- env HALOGEN_PROMPT_CACHE=0 <CLI> sweep -p 8192,32768 -n 128 | tee /tmp/halogen-sweep.txt` — Expected: output contains prefill rates at 8192 and 32768. If the CLI ignores the env override, start one short-lived pod from the same image with `HALOGEN_PROMPT_CACHE=0` set and run the sweep there; do not alter the serving Deployment.

- [ ] **Step 4: Handle GGUF refusal (conditional)** — If Step 2 or Task 4 Step 5 shows the GGUF was refused or the pool was lowered below 262144, edit the `HALOGEN_CHECKPOINT` entry in `charts/halogen/values.yaml` to `/root/.ollama/qwen38-27b-ht4.hgn`, commit `fix(halogen): fall back to ht4 checkpoint`, push, re-trigger the sync as in Task 4 steps 3 and 6, and rerun steps 2–3. Record both attempts in the results doc.

- [ ] **Step 5: Write `docs/benchmarks/halogen-vs-llamacpp-2026-11-27.md`** with a table whose rows are: published Halogen 0.21.0 ht4 (37.9 / 15.1 / 578 / 605 / 530), measured llama.cpp Swift Q6_K Vulkan RADV (23.9 / not measured / 347 / 330 / 280), measured Halogen GGUF (values from Step 2–3), and measured Halogen ht4 if Step 4 ran. Add a section listing the two forced deviations, the actual pool from Task 4 Step 5, and the caveat that published numbers are a 128 GB / 85 W mean while this box is 64 GB on a shared k3s node.

- [ ] **Step 6: Commit and push** — Run: `git add docs/benchmarks/halogen-vs-llamacpp-2026-11-27.md && git commit -m "docs: record measured Halogen GGUF benchmark" && git push` — Expected: results doc on the open PR; PR still unmerged.
