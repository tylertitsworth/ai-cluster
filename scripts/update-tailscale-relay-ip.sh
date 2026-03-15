#!/usr/bin/env bash
# Manual one-shot relay endpoint updater.
# Useful as emergency fallback if the CronJob is unhealthy.
# Requires: kubectl, curl
set -euo pipefail

RELAY_PORT="${RELAY_PORT:-40000}"
NAMESPACE="${NAMESPACE:-tailscale}"
LABEL="${LABEL:-tailscale.com/parent-resource=egress,tailscale.com/parent-resource-type=proxygroup}"
RELAY_IP="${RELAY_IP:-}"

if [[ -z "${RELAY_IP}" ]]; then
  echo "Fetching current public IP..."
  RELAY_IP="$(curl -sSf --max-time 10 https://ifconfig.me 2>/dev/null || curl -sSf --max-time 10 https://api.ipify.org 2>/dev/null || true)"
fi

if [[ -z "${RELAY_IP}" ]]; then
  echo "Failed to get public IP. Set RELAY_IP and retry." >&2
  exit 1
fi
if [[ ! "${RELAY_IP}" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  echo "Invalid RELAY_IP: ${RELAY_IP}" >&2
  exit 1
fi
echo "Using relay endpoint ${RELAY_IP}:${RELAY_PORT}"

PODS="$(kubectl get pods -n "${NAMESPACE}" -l "${LABEL}" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')"
if [[ -z "${PODS}" ]]; then
  echo "No egress pods found for selector: ${LABEL}" >&2
  exit 1
fi

echo "Updating egress pods one-by-one..."
for pod in ${PODS}; do
  echo "  -> ${pod}"
  success=0
  for attempt in 1 2 3; do
    if kubectl exec -n "${NAMESPACE}" "${pod}" -c tailscale -- tailscale set --relay-server-port="${RELAY_PORT}" --relay-server-static-endpoints="${RELAY_IP}:${RELAY_PORT}"; then
      kubectl exec -n "${NAMESPACE}" "${pod}" -c tailscale -- tailscale debug peer-relay-servers || true
      success=1
      break
    fi
    sleep $((attempt * 5))
  done
  if [[ "${success}" -ne 1 ]]; then
    echo "Failed updating ${pod} after retries" >&2
    exit 1
  fi
done

echo "Done. Relay endpoint applied across egress pods."
