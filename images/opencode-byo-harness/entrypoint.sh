#!/bin/bash
set -e
mkdir -p /home/kagent/.config/opencode

MODEL="${OPENCODE_MODEL:-}"
if [ -z "$MODEL" ]; then
  MODEL="ollama/swift-qwen3.8-27b:q6k-map-k4v"
fi

# Parse provider/model
PROVIDER="${MODEL%%/*}"
MODEL_NAME="${MODEL#*/}"
if [ "$PROVIDER" = "$MODEL" ]; then
  PROVIDER="ollama"
fi

# Determine base URL
if [ -n "${OPENAI_BASE_URL:-}" ]; then
  BASE_URL="$OPENAI_BASE_URL"
elif [ -n "${OLLAMA_HOST:-}" ]; then
  HOST="$OLLAMA_HOST"
  case "$HOST" in
    */v1) BASE_URL="$HOST" ;;
    *) BASE_URL="${HOST%/}/v1" ;;
  esac
else
  BASE_URL="http://ollama.ollama.svc.cluster.local:11434/v1"
fi

# Sanitize model key for config
KEY=$(printf '%s' "$MODEL_NAME" | tr -c '[:alnum:]._-' '-')

cat > /home/kagent/.config/opencode/opencode.json <<EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "model": "$MODEL",
  "provider": {
    "$PROVIDER": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "$PROVIDER",
      "options": {
        "baseURL": "$BASE_URL"
      },
      "models": {
        "$KEY": {
          "name": "$MODEL_NAME",
          "id": "$MODEL_NAME"
        }
      }
    }
  }
}
EOF
chown -R 65532:65532 /home/kagent/.config
export XDG_DATA_HOME=/data
if [ -n "${OLLAMA_HOST:-}" ]; then
  export OLLAMA_HOST="$OLLAMA_HOST"
fi
if [ -n "${OPENAI_BASE_URL:-}" ]; then
  export OPENAI_BASE_URL="$OPENAI_BASE_URL"
fi
export OPENCODE_AUTO="${OPENCODE_AUTO:-true}"
exec /app
