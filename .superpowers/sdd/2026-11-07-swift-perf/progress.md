# SDD ledger — plan: /home/titsw/Projects/ai-cluster/docs/superpowers/plans/2026-11-07-swift-perf.md
## Pre-flight
- Task 1 produces ~/.config/opencode/opencode.json compaction.buffer=45%; Task 2 consumes nothing from Task1 (cluster values separate).
- Task 2 produces branch tune/swift-mtp4-vulkan-hip + Argo targetRevision; Task 4 consumes it for swap.
- Task 3 produces benchmark draft spec; Task 4 consumes it.
- Conflict: live OLLAMA_CONTEXT_LENGTH 131072 vs git 262144 — Ruling: align git to live 131072 in Task 2 (why: no behavior change, fixes OutOfSync).
- Conflict: image is ROCm-only, Vulkan needs different base — Ruling: test Vulkan via OLLAMA_VULKAN env first; if libs missing, record as finding and use llama-bench outside pod (cost: extra build work if wrong).
Task 1: complete (opencode.json compaction 45%+bg, chart mirrored, tests: task1_test.py -> PASS, opencode models OK)
Task 2: complete (branch tune/swift-mtp4-vulkan-hip a1ecdf2, MTP4+ctx131072+Argo pointer, image bump deferred — Dockerfile removed in 145c026, need restore from dd046fd to rebuild; MTP patch deliberately left LLAMA_CPP_VERSION alone, cost if wrong: no new llama.cpp until rebuild)
Ruling: Argo Application self-ref won't apply from branch — must kubectl patch live Application to target tune branch (cost if wrong: OutOfSync until main merge)
Task 3: complete (benchmark draft created, table empty, tuning notes listed)
Task 4: complete (HIP MTP4 baseline 24.84/17.29/17.78/13.10/10.97, Vulkan env no-op 24.90/17.26 same ROCm, final pod 749st Healthy MTP4)
Task 4-final: complete (rebuilt 0.40.15-swift via GH Actions ai-cluster-ollama-swift:0.40.15-tuned, minimal MTP patch ported, ROCBLAS_USE_HIPBLASLT=1, q8_0, b2048, smoke MTP draft-mtp,ngram-map-k4v n-max4 verified; HIP standalone 19.44/13.86/11.93, Vulkan 15.61/13.10/12.97, prod Ollama HIP 25.99/19.76/15.33)
## Tensile lazy fix (plan docs/superpowers/plans/2026-11-08-tensile-lazy-fix.md)
- Task 1: complete (branch build/ollama-swift-tensile 2ccd122, FROM kyuz0/amd-strix-halo-toolboxes:rocm-7.1 AS rocmlib + COPY into rocm_v7_2/hipblaslt/library/ + build.sh LAZY/KERNELS asserts; local docker build/run unavailable — overlay mount unsupported in sandbox, verified via pulled kyuz0 layer tar instead)
- Task 2: complete (run 42454662496 success, digest sha256:f8b6088e7280c02aabdf02ca71bf8839fd0f9ec275a378ffd4abb79fe3e2acf0 for 0.40.15-tuned + 0.40.15-swift-tuned, layer tar confirms TensileLibrary_lazy_gfx1151.dat + Kernels.so-000-gfx1151.hsaco present; Tags covered workflow_dispatch since push trigger listens on build/ollama-swift-dockerfile only)
- Task 3: pending manual — swap prod to new digest + smoke (Tensile error gone, MTP intact) requires prod restart approval, NOT done
- Task 4: pending manual — benchmark prompt tok/s after deploy, records in docs/superpowers/benchmarks/2026-11-07-vulkan-vs-hip.md
