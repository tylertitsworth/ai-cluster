#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
IMAGE="${IMAGE:-ghcr.io/tylertitsworth/ai-cluster-opencode-byo-harness:dev}"
docker build -t "$IMAGE" .
echo "Built $IMAGE"
echo "To push and get digest: docker push $IMAGE && docker inspect --format='{{index .RepoDigests 0}}' $IMAGE"
