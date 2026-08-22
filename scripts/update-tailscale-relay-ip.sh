#!/usr/bin/env bash
# Manual one-shot relay endpoint updater.
# Useful as emergency fallback if the CronJob is unhealthy.
# Requires: kubectl, curl
set -euo pipefail

RELAY_PORT="${RELAY_PORT:-41641}"
WAN_PORT_BASE="${WAN_PORT_BASE:-41641}"
NAMESPACE="${NAMESPACE:-tailscale}"
LABEL="${LABEL:-tailscale.com/parent-resource=relay,tailscale.com/parent-resource-type=peerrelay}"
CONTAINER="${CONTAINER:-tailscaled}"
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

PODS="$(kubectl get pods -n "${NAMESPACE}" -l "${LABEL}" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | sort)"
if [[ -z "${PODS}" ]]; then
  echo "No relay pods found for selector: ${LABEL}" >&2
  exit 1
fi

echo "Updating relay pods one-by-one..."
# Replica N is reachable on WAN port WAN_PORT_BASE+N (router forwards it to the
# replica's VIP); every replica listens internally on RELAY_PORT.
for pod in ${PODS}; do
  idx="${pod##*-}"
  wan_port=$((WAN_PORT_BASE + idx))
  echo "  -> ${pod} (${RELAY_IP}:${wan_port})"
  success=0
  for attempt in 1 2 3; do
    if kubectl exec -n "${NAMESPACE}" "${pod}" -c "${CONTAINER}" -- tailscale set --relay-server-port="${RELAY_PORT}" --relay-server-static-endpoints="${RELAY_IP}:${wan_port}"; then
      kubectl exec -n "${NAMESPACE}" "${pod}" -c "${CONTAINER}" -- tailscale debug peer-relay-servers || true
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

echo "Done. Relay endpoints applied across relay pods."
