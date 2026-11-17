# OpenCode BYO Harness for kagent

Minimal BYO A2A harness that runs `opencode run` per incoming message.

- Binary built against kagent ADK v1.0.1 (`go/core/test/opencodebyo` pattern).
- Requires `opencode` CLI in image.
- Env vars:
  - `OPENCODE_MODEL` (e.g. `ollama/swift-qwen3.8-27b:q6k-map-k4v` for in-cluster Ollama, or a provider/model configured in opencode)
  - `OPENCODE_AGENT` (optional)
  - `OPENCODE_AUTO` (default true; set `false` to disable `--auto`)
  - `OPENCODE_FORMAT` (default `default`, can be `json`)
  - `OPENCODE_WORKDIR` (default `/workspace`)

## Using free models (no OpenCode API key)
- **Recommended in this cluster:** use Ollama (e.g. `OPENCODE_MODEL=ollama/swift-qwen3.8-27b:q6k-map-k4v`) and point opencode/Ollama host to `http://ollama.ollama.svc.cluster.local:11434` via opencode config/env as needed.
- **OpenCode free models:** opencode supports free models in its own ecosystem, but availability/auth/endpoint behavior can change and may require opencode-specific config or login in some cases. Test with your desired `--model` in a running container.
- `apps/platform/opencode-templates.yaml` includes keyless kagent `ModelConfig`s for Go endpoint models reported as $0 (`beam-free`, `iceman-contributor-free`, `longcat-2.5-free`) — apply/use only if the endpoint accepts unauthenticated requests for your case.

Build: `./build.sh` or `docker build -t <image> .` Push and use the image digest in the Harness `spec.workload.image`.
