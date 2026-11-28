# AGENTS.md

This repository is the GitOps source of truth for a home k3s cluster (Turing Pi 2.5.2, ARM nodes plus `framework-desktop`, an amd64 node with an AMD GPU). `README.md` is the narrative record of the build; this file is the current state for agents working in the repo.

## LLM inference

- **Halogen is the inference engine.** Chart: `charts/halogen`, app: `apps/ai/halogen.yaml` (namespace `ollama`). Image `ghcr.io/peonist-ai/halogen-flash-server`, model `halogen-qwen3.8-27b` (ht4 checkpoint), 256k context, 56Gi Guaranteed QoS on `framework-desktop`.
- It serves an OpenAI-compatible API at `http://halogen.ollama.svc.cluster.local:8731/v1` (Tailscale ingress `halogen`). The kagent agents (`charts/kagent-stack`) point at it.
- Configuration is entirely `HALOGEN_*` environment variables in `charts/halogen/values.yaml`, rendered into the `halogen-config` configmap.
- The previous engines are retired but kept for rollback: `apps/ai/ollama.yaml` (replicaCount 0), `apps/ai/llama-cpp.yaml` (replicas 0), `apps/ai/vllm.yaml` (automated sync disabled). Do not treat them as active.
- Benchmark numbers for the switch are in the "Halogen" section of `README.md`.
