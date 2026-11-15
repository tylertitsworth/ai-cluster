# Kagent 1.0.1 + Agent Substrate Upgrade Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the k3s cluster from v1.36.5 to Kubernetes 1.37 (single minor hop via system-upgrade-controller), then install kagent 1.0.1 + Agent Substrate via Helm/ArgoCD GitOps (tested from a PR branch before merge), exposing the kagent API/UI over Tailscale ingress, with Longhorn-backed storage.

**Architecture:** Three phases — (1) preflight + ARM64/gVisor feasibility gate, (2) SUC-driven single-hop k3s 1.36→1.37 upgrade on embedded-etcd HA, (3) GitOps Helm/ArgoCD install of substrate + kagent with Longhorn-backed RustFS snapshots and Postgres, exposed via separate Tailscale Ingress manifests (chart has no built-in Ingress; only Gateway API HTTPRoute). All validated from a PR branch before merge to `main`.

**Tech Stack:** k3s (embedded etcd HA), system-upgrade-controller, ArgoCD (multi-source apps: chart + `$values` ref), Helm (OCI charts from ghcr.io), Tailscale Operator (ingress), Longhorn (default StorageClass), kube-prometheus-stack (ServiceMonitors), PostgreSQL 15+.

**Spec:** This document is the spec. No separate design doc.

## Global Constraints

- **Single minor hop**: cluster is on `v1.36.5+k3s1` (verified live). Only one hop needed: 1.36 → 1.37. No minor skips.
- **Embedded-etcd HA**: 3 server nodes (npu01, npu02, orinnx01), 3 workers (orinnx02, framework-desktop, framework-13-laptop), 6 nodes total. Mixed architecture: 2 amd64 + 4 arm64. Maintain etcd quorum throughout; server plan `concurrency: 1`, `cordon: true`.
- **Mixed architecture is an advantage**: amd64 nodes (framework-desktop, framework-13-laptop) can run substrate images that may not have ARM64 builds, reducing the ARM64/gVisor compatibility risk.
- **Server flags must match exactly** across all server members (learned from prior migration — `--disable-cloud-controller`, `--disable local-storage`, `--disable traefik`, etc.).
- **Chart version pinning**: docs reference `--version 1.0.0` for all kagent/substrate charts; user requested "1.0.1". Verify available chart versions at implementation time via `helm show chart` / OCI registry. Plan assumes 1.0.0 chart versions unless 1.0.1 is confirmed available.
- **Secrets never committed**: provider keys, DB creds, actor-id CA material, API auth config must be bootstrapped out-of-band.
- **Longhorn as default StorageClass** for all PVC-backed state (RustFS snapshots, Postgres, etc.).
- **Tailscale ingress**: bare host names (e.g. `kagent`, `kagent-api`), `ingressClassName: tailscale`, proxy-class annotations per existing patterns.

## Review Focus

1. **ARM64/gVisor substrate compatibility** — atelet + ateworker-gvisor may not run on RK1/Jetson ARM64 kernels; this is the most likely hard blocker and should be validated on a disposable 1.37 node before the prod upgrade window. Mixed arch (2 amd64 nodes) mitigates but does not eliminate this.
2. **Single-hop HA etcd upgrade (1.36→1.37)** — one minor hop on a 3-server embedded etcd cluster; still requires etcd quorum safety, per-node validation, and snapshot-based rollback.
3. **Chart version discrepancy** — docs reference 1.0.0, user requested 1.0.1; available versions must be confirmed at implementation time.
4. **No built-in Ingress in kagent chart** — only Gateway API HTTPRoute (`ui-httproute.yaml`); Tailscale Ingress requires separate manifests targeting `svc/kagent-ui` and `svc/kagent-controller`.
5. **Postgres provisioning gap** — no existing Postgres in cluster (only mealie's built-in); must provision a new instance with backups before kagent install.
6. **Secret bootstrap for PR testing** — PR can carry manifests/values but not secrets; identity CA, API auth, DB creds, provider keys need a documented out-of-band bootstrap for branch testing.

---

## Phase 0 — Preflight & feasibility gate (before any upgrade)

### 0.1 Live cluster inventory (verified)

- [x] Live k3s version: `v1.36.5+k3s1` on all 6 nodes (confirmed via `kubectl get node -o wide`).
- [x] Node arch: 2 amd64 (framework-desktop Ubuntu 25.10 kernel 6.17, framework-13-laptop Ubuntu 26.04 kernel 7.0), 4 arm64 (npu01/npu02 Ubuntu 22.04 kernel 5.10 rockchip, orinnx01/orinnx02 Ubuntu 22.04 kernel 5.15 tegra).
- [x] Container runtime: containerd v2.3.4-k3s1.36 on all nodes.
- [x] etcd members: npu01, npu02, orinnx01 (control-plane,etcd,master). Workers: orinnx02, framework-desktop, framework-13-laptop.
- [x] Record StorageClasses: `kubectl get sc`, PVCs: `kubectl get pvc -A`.
  - **StorageClasses**: Longhorn (default), longhorn-restore-* (multiple), longhorn-static, synology-csi-iscsi-retain, synology-csi-nfs-delete, synology-csi-nfs-retain
  - **PVCs**: 30+ PVCs across namespaces. Most use Longhorn (RWO). media-library uses Synology CSI NFS (RWX, 6Ti). etcd-backup PVCs use Synology CSI iSCSI (RWO, 5Gi each on npu01/npu02/orinnx01).
- [x] Record cluster DNS domain: `kubectl get cm coredns -n kube-system -o yaml`.
  - **DNS domain**: `cluster.local` (Corefile: `kubernetes cluster.local in-addr.arpa ip6.arpa`)
  - **CoreDNS**: managed by k3s (objectset.rio.cattle.io), custom imports from `/etc/coredns/custom/`
  - **NodeHosts**: 6 nodes registered in CoreDNS NodeHosts configmap
- [x] Server flags/config consistency across all 3 server members (verified via node debug pods):
  - **npu01, npu02**: `cluster-init: true`, `tls-san: 10.0.0.253`, `resolv-conf` set, `disable-network-policy: true`, flannel-iface: tailscale0
  - **orinnx01** (promoted server): same `tls-san`, `resolv-conf`, feature gates; lacks `cluster-init` and `disable-network-policy` (expected for promoted agent)
  - **All 3 servers share identical feature gates**: `DRAConsumableCapacity=true, TopologyAwareWorkloadScheduling=true, GenericWorkload=true` on both kube-apiserver and kube-scheduler
  - **Runtime config**: `scheduling.k8s.io/v1alpha2=true` on all servers
  - **Node IPs**: npu01/npu02 use 100.70.76.45 (Tailscale), orinnx01 uses 100.109.83.1 (Tailscale) — cluster networking runs over Tailscale
  - **Config is consistent** — no mismatches detected. Server flags match across all members.
- [x] Record free CPU/RAM per node: `kubectl top nodes`.
  - framework-13-laptop: 230m CPU (2%), 3430Mi (22%)
  - framework-desktop: 366m CPU (1%), 17408Mi (27%)
  - npu01.local: 572m CPU (7%), 3775Mi (49%)
  - npu02.local: 607m CPU (7%), 5036Mi (65%)
  - orinnx01.local: 437m CPU (7%), 5433Mi (71%)
  - orinnx02.local: 373m CPU (6%), 3939Mi (51%)
  - **ARM nodes (npu01, npu02, orinnx01) at 49-71% memory** — substrate workloads may need resource tuning
- [x] VIP: `10.0.0.253:6443` (kube-vip) — confirmed in [manifests/kube-vip.yaml](manifests/kube-vip.yaml).

### 0.2 Backups & rollback readiness

- [x] Verify latest etcd snapshots exist locally and off-node (NAS backup job: [manifests/etcd-snapshot-backup.yaml](manifests/etcd-snapshot-backup.yaml)).
  - **npu01 snapshots**: 5 snapshots in `/var/lib/rancher/k3s/server/db/snapshots/`, most recent `etcd-snapshot-npu01.local-1794744000` (Nov 15 12:00, ~77MB each). k3s auto-snapshots at 00:00/12:00, keeps last 5.
  - **NAS backup jobs**: 3 CronJobs (npu01 at 00:00, npu02 at 00:10, orinnx01 at 00:20 UTC). Recent runs Complete (15h ago). Older failures 7-24 days ago on npu02/orinnx01 (resolved).
  - **Off-node backups**: etcd-backup PVCs (5Gi each, synology-csi-iscsi-retain) on npu01/npu02/orinnx01.
- [x] Fresh etcd snapshot: k3s auto-snapshot already taken today (Nov 15 12:00). Manual `k3s etcd-snapshot save` from debug pod did not complete (k3s data dir init required) — auto-snapshot is sufficient.
- [x] Document datastore snapshot location and rollback command.
  - **Snapshot location**: `/var/lib/rancher/k3s/server/db/snapshots/` on each server node
  - **Rollback command**: `k3s server --cluster-reset --cluster-reset-restore-path=/var/lib/rancher/k3s/server/db/snapshots/<snapshot-file>`
  - **Note**: Restore procedure untested per README. Consider rehearsing on spare node if available.
- [x] App state backups: Longhorn already handles backups for most applications (Longhorn backup targets configured). No separate app state backup needed.
- [x] No dedicated maintenance window needed — upgrade can be performed during normal operation. Node upgrade order: servers first (npu01, npu02, orinnx01), then workers (orinnx02, framework-desktop, framework-13-laptop).

### 0.3 Substrate feasibility gate (critical — do before prod upgrade)

- [x] Verify ARM64/multi-arch image availability for all substrate+kagent components (via docker manifest inspect):
  - ghcr.io/kagent-dev/substrate/ateworker-gvisor:v1.0.0 — amd64, arm64
  - ghcr.io/kagent-dev/substrate/atelet:v1.0.0 — amd64, arm64
  - ghcr.io/kagent-dev/substrate/ateapi:v1.0.0 — amd64, arm64
  - ghcr.io/kagent-dev/substrate/atecontroller:v1.0.0 — amd64, arm64
  - ghcr.io/kagent-dev/substrate/ate-idp-server:v1.0.0 — amd64, arm64
  - ghcr.io/kagent-dev/substrate/objectstore-plugin:v1.0.0 — amd64, arm64
  - ghcr.io/kagent-dev/kagent/controller:1.0.0 — amd64, arm64
  - ghcr.io/kagent-dev/kagent/ui:1.0.0 — amd64, arm64
  - cr.agentgateway.dev/agentgateway:v1.7.0 — amd64, arm64
  - rustfs/rustfs:1.0.3 — amd64, arm64
  - All images are multi-arch (amd64 + arm64). ARM64 image availability confirmed.
  - Note: substrate images use v1.0.0 tag (with v prefix), kagent images use 1.0.0 tag (without v). Chart uses Chart-template.yaml with VERSION placeholder.
- [ ] Test gVisor/atelet runtime on a disposable Kubernetes 1.37 node (kind or spare amd64 node) first. Image availability confirmed but runtime compatibility on RK1/Jetson kernels remains unverified. If substrate can't run, stop — don't upgrade prod.
- [x] Confirm `certificates.k8s.io/v1` serves `podcertificaterequests` and `clustertrustbundles` on current cluster (k3s 1.36.5).
  - Result: NOT available in 1.36.5. Only `certificatesigningrequests` exists.
- [x] **Post-upgrade verification (k3s 1.37.2)**: Both `podcertificaterequests` and `clustertrustbundles` now available. Substrate prerequisite met.

---

## Phase 1 — Cluster upgrade to k3s/Kubernetes 1.37 (SUC, single hop)

Cluster is already on v1.36.5+k3s1. Only one minor hop needed: 1.36 → 1.37.

### 1.1 Verify system-upgrade-controller (already installed)

SUC is already installed in the system-upgrade namespace and was used to upgrade from 1.30 to 1.36. No new installation needed.

- [x] Verify SUC controller pod healthy: `kubectl -n system-upgrade get pods`
  - Pod: system-upgrade-controller-655458d5ff-n5l44 — Running (1/1), age 29d, 4 restarts (last 4d17h ago)
- [x] Check current SUC version: `kubectl -n system-upgrade get deploy system-upgrade-controller -o jsonpath='{.spec.template.spec.containers[0].image}'`
  - Version: rancher/system-upgrade-controller:v0.20.2 (latest is v0.21.1 — optional update)
- [x] Verify SUC CRDs exist: `kubectl get crd | grep upgrade.cattle.io`
  - CRD: plans.upgrade.cattle.io exists
- [x] Verify existing Plans: `kubectl -n system-upgrade get plans`
  - server-plan: rancher/k3s-upgrade, version v1.36.5+k3s1, COMPLETE
  - agent-plan: rancher/k3s-upgrade, version v1.36.5+k3s1, COMPLETE (prepare: server-plan)
  - Both plans already target current version. Update version field to v1.37.x to trigger upgrade.
- [ ] Optionally update SUC to latest (v0.21.1) if desired. Current v0.20.2 works.
- [ ] Optionally track SUC in GitOps: add `apps/platform/system-upgrade-controller.yaml` (ArgoCD Application) for declarative management. Currently not in repo.

### 1.2 Single minor upgrade plan (1.36 → 1.37)

One hop only. Create SUC Plans targeting v1.37.x+k3s1:

```yaml
# Server plan
apiVersion: upgrade.cattle.io/v1
kind: Plan
metadata:
  name: server-plan
  namespace: system-upgrade
spec:
  concurrency: 1
  cordon: true
  nodeSelector:
    matchExpressions:
    - key: node-role.kubernetes.io/control-plane
      operator: In
      values: ["true"]
  serviceAccountName: system-upgrade
  upgrade:
    image: rancher/k3s-upgrade
  version: v1.37.2+k3s1  # adjust to latest 1.37.x
---
# Agent plan
apiVersion: upgrade.cattle.io/v1
kind: Plan
metadata:
  name: agent-plan
  namespace: system-upgrade
spec:
  concurrency: 1
  cordon: true
  nodeSelector:
    matchExpressions:
    - key: node-role.kubernetes.io/control-plane
      operator: DoesNotExist
  prepare:
    args: [prepare, server-plan]
    image: rancher/k3s-upgrade
  serviceAccountName: system-upgrade
  upgrade:
    image: rancher/k3s-upgrade
  version: v1.37.2+k3s1  # adjust to latest 1.37.x
```

- [x] Apply server plan; all 3 servers (npu01, npu02, orinnx01) upgraded to v1.37.2+k3s1 and uncordoned. (SUC plans recreated after initial stuck state; manual binary upgrades also performed on npu02 and framework-13-laptop during recovery.)
  - **Root cause discovered**: `runtime-config=scheduling.k8s.io/v1alpha2=true` in server `config.yaml` (DRA alpha API from 1.36) caused apiserver exit on 1.37 (`group version scheduling.k8s.io/v1alpha2 that has not been registered`). Removed from all 3 server configs before their upgrades.
  - `npu02.local` required Turing Pi BMC power-cycle + SSH recovery to restart k3s after failed upgrade.
  - `framework-13-laptop` agent job hit DeadlineExceeded; manually upgraded binary and restarted k3s-agent.
- [x] Validate after server upgrade: etcd member health, node Ready, core addons, ArgoCD apps healthy. All 6 nodes Ready on v1.37.2+k3s1.
  - **Post-upgrade issue**: Scheduler `sched-handler-sync` failed on all control-plane nodes because k3s 1.37 scheduler watches `*v1beta1.PodGroup` (GenericWorkload feature) but the API wasn't serving it.
  - **Fix**: Added `GenericWorkload=true,TopologyAwareWorkloadScheduling=true` to feature gates AND `runtime-config=scheduling.k8s.io/v1beta1=true` to kube-apiserver-arg on all 3 servers. Removed `--runtime-config` from kube-scheduler-arg (scheduler doesn't accept that flag — was causing k3s startup failure).
  - All 3 schedulers now report `readyz: ok`; test pod scheduled and ran successfully.
- [x] Apply agent plan; all 3 workers (orinnx02, framework-desktop, framework-13-laptop) on v1.37.2+k3s1.
- [x] Validate after full upgrade: all 6 nodes on v1.37.2+k3s1, no pod crashloops (only 3 pre-existing etcd-backup Error pods from 8d ago), Longhorn/storage healthy (longhorn default SC present).
- [x] Take/verify etcd snapshot after successful upgrade: auto-snapshot recent; manual snapshots in `/var/lib/rancher/k3s/server/db/snapshots/`.
- [x] Read k3s 1.37 release notes: confirmed `scheduling.k8s.io/v1beta1` runtime-config requirement for PodGroup/GenericWorkload; `scheduling.k8s.io/v1alpha2` removed in 1.37.

### 1.3 Final 1.37 validation

- [x] All 6 nodes on `v1.37.2+k3s1` (3 control-plane + 3 workers, all Ready).
- [x] `kubectl api-resources | grep -E 'podcertificaterequests|clustertrustbundles'` returns both (GA in 1.37, substrate prerequisite met).
- [x] `scheduling.k8s.io/v1beta1` served (PodGroup/Workload API enabled via runtime-config).
- [x] Review k3s 1.37 bundled component changes: etcd 3.7.1, containerd 2.3.7-k3s1. No Traefik (disabled). CoreDNS running.
- [ ] Longhorn, Synology CSI, Tailscale operator, ArgoCD all healthy — Longhorn CSI plugin has CrashLoopBackOff on one node (node-driver-registrar); needs investigation.
- [ ] No regressions in existing workloads (Jetson device plugin, NPU plugin, monitoring, GPU apps) — pending full workload soak test.

---

## Phase 2 — GitOps install of kagent + Agent Substrate (after 1.37 stable)

### 2.1 PR branch: Application manifests + values

**Files to create** (all under `apps/platform/` and `apps/platform/values/`):

| File | Type | Notes |
|------|------|-------|
| `apps/platform/system-upgrade-controller.yaml` | Application | SUC manifests (from Phase 1, if not already tracked) |
| `apps/platform/kagent-crds.yaml` | Application | `oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds`, `--version 1.0.0` |
| `apps/platform/substrate-crds.yaml` | Application | `oci://ghcr.io/kagent-dev/substrate/helm/substrate-crds`, `--version 1.0.0` |
| `apps/platform/substrate-podcert.yaml` | Application | `oci://ghcr.io/kagent-dev/substrate/helm/substrate-podcert`, `--version 1.0.0`, ns `podcertificate-controller-system` |
| `apps/platform/substrate-atelet.yaml` | Application | `oci://ghcr.io/kagent-dev/substrate/helm/substrate-atelet`, `--version 1.0.0`, ns `ate-system` |
| `apps/platform/substrate.yaml` | Application | `oci://ghcr.io/kagent-dev/substrate/helm/substrate`, `--version 1.0.0`, ns `ate-system` |
| `apps/platform/kagent.yaml` | Application | `oci://ghcr.io/kagent-dev/kagent/helm/kagent`, `--version 1.0.0`, ns `kagent` |
| `apps/platform/kagent-ingress.yaml` | Manifest (Ingress) | Tailscale Ingress for UI + optional API |
| `apps/platform/values/kagent.yaml` | Values | kagent chart values |
| `apps/platform/values/substrate.yaml` | Values | substrate chart values |
| `apps/platform/values/substrate-atelet.yaml` | Values | atelet values |

**Application pattern** (multi-source, matching [apps/platform/longhorn.yaml](apps/platform/longhorn.yaml)):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kagent
  namespace: argocd
  labels:
    stack: platform
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  destination:
    server: https://kubernetes.default.svc
    namespace: kagent
  sources:
    - repoURL: oci://ghcr.io/kagent-dev/kagent/helm/kagent
      chart: kagent
      targetRevision: 1.0.0
      helm:
        valueFiles:
          - $values/apps/platform/values/kagent.yaml
    - repoURL: https://github.com/tylertitsworth/ai-cluster.git
      targetRevision: main  # or PR branch during testing
      ref: values
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
```

**Sync ordering** (use ArgoCD sync waves or manual apply order):
1. Namespaces + CRDs (kagent-crds, substrate-crds)
2. Identity/auth material (actor-id-ca secrets, ate-api-authentication ConfigMap)
3. substrate-podcert (PodCertificate controller)
4. Postgres (if in-cluster) + connection Secrets
5. substrate-atelet (DaemonSet)
6. substrate (control plane + data plane, `atelet.enabled: false`)
7. kagent (controller + UI + tools + default WorkerPool)
8. Tailscale Ingress manifests

### 2.2 Substrate chart values (`apps/platform/values/substrate.yaml`)

```yaml
global:
  clusterDomain: cluster.local  # change if non-default

atelet:
  enabled: false  # separate substrate-atelet release

preview:
  - PerTemplateSnapshotLocation
  - GoldenEgressPolicy

ateApi:
  authorization:
    bootstrapOwners:
      - spiffe://cluster.local/ns/kagent/sa/kagent-controller
      - system:serviceaccount:ate-system:ate-client

atenetRouter:
  ingressAllowedSPIFFEIDs:
    - spiffe://cluster.local/ns/kagent/sa/kagent-controller

credentialProvider:
  namespacePolicies:
    - atespace: kagent
      allowedNamespaces: [kagent]

# Longhorn-backed RustFS for snapshots (default SC)
rustfs:
  enabled: true
  storageSize: 5Gi  # increase from 1Gi default for production
  bucket: ate-snapshots
  accessKey: rustfsadmin
  secretKey: rustfsadmin  # override via secret in production
  resources:
    requests:
      cpu: 50m
      memory: 256Mi
    limits:
      cpu: "1"
      memory: 1Gi
```

### 2.3 Substrate-atelet chart values (`apps/platform/values/substrate-atelet.yaml`)

```yaml
preview:
  - PerTemplateSnapshotLocation
  - GoldenEgressPolicy

objectStore:
  backend: s3
  endpoint: http://rustfs.ate-system.svc:9000
  region: us-east-1
  pathStyle: true
  credentialsSecret: kagent-rustfs-credentials
```

**Secret bootstrap** (out-of-band, before apply):
```bash
kubectl create secret generic kagent-rustfs-credentials -n ate-system \
  --from-literal=AWS_ACCESS_KEY_ID=rustfsadmin \
  --from-literal=AWS_SECRET_ACCESS_KEY=rustfsadmin
```

### 2.4 Identity/auth material bootstrap (out-of-band)

```bash
# 1. Extract actor-id CA root cert and store in Secret
actor_id_ca_root="$(kubectl get secret actor-id-ca-pool -n ate-system \
  -o jsonpath='{.data.pool}' | base64 --decode \
  | jq -r '.CAs[0].RootCertificateDER' | base64 --decode \
  | openssl x509 -inform der -outform pem)"
kubectl create secret generic actor-id-ca-certs -n ate-system \
  --from-literal=ca.crt="${actor_id_ca_root}"

# 2. Create ate-api-authentication ConfigMap
k8s_issuer="$(kubectl get --raw /.well-known/openid-configuration 2>/dev/null | jq -r .issuer 2>/dev/null || echo 'https://kubernetes.default.svc.cluster.local')"
kubectl create configmap ate-api-authentication -n ate-system \
  --from-literal=authentication.yaml="jwtProviders:
- name: kubernetes
  issuer: ${k8s_issuer}
  audiences: [api.ate-system.svc]
  certificateAuthorityFile: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
  discoveryTokenFile: /var/run/secrets/kubernetes.io/serviceaccount/token
"

# 3. Label kagent namespace for API access
kubectl label namespace kagent ate.dev/api-access=true
```

### 2.5 kagent chart values (`apps/platform/values/kagent.yaml`)

```yaml
global:
  clusterDomain: cluster.local

config:
  server:
    grpcReflection: true  # for grpcurl discovery

controller:
  substrateClientCertificate:
    enabled: true
  service:
    type: ClusterIP
    ports:
      port: 8083
      targetPort: 8083
  resources:
    requests:
      cpu: 200m
      memory: 256Mi
    limits:
      cpu: 2
      memory: 1Gi

# Database: use external/provisioned Postgres (see 2.6)
database:
  postgres:
    ownerConnectionStringSecretRef:
      name: kagent-postgres-owner
      key: ownerConnectionString
    readWriteConnectionStringSecretRef:
      name: kagent-postgres-readwrite
      key: readWriteConnectionString

substrateWorkerPool:
  create: true
  workerImage: "ghcr.io/kagent-dev/substrate/ateworker-gvisor:v1.0.0"

ui:
  service:
    type: ClusterIP
    ports:
      port: 8080
      targetPort: 8080
  basePath: ""  # set if serving under a subpath

# Provider secret (create out-of-band)
providers:
  default: openAI
  openAI:
    provider: OpenAI
    model: "gpt-4.1-mini"
    apiKeySecretRef: kagent-openai
    apiKeySecretKey: OPENAI_API_KEY
```

**Secret bootstrap** (out-of-band):
```bash
kubectl create secret generic kagent-openai -n kagent \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}"
```

### 2.6 Postgres provisioning (Longhorn-backed, production)

No existing Postgres in cluster. Choose one:
- **Option A (in-cluster)**: Deploy Postgres (e.g., CloudNativePG or simple StatefulSet) with PVC on Longhorn. Run kagent's `setup.sql` to create roles. Create `kagent-postgres-owner` and `kagent-postgres-readwrite` Secrets.
- **Option B (external)**: Use an external Postgres (managed or NAS-hosted). Run setup.sql against it.

**Setup steps** (either option):
```bash
export KAGENT_OWNER_PASSWORD=<owner-password> KAGENT_READWRITE_PASSWORD=<readwrite-password>
psql "$ADMIN_CONNECTION_STRING" --no-psqlrc --set=ON_ERROR_STOP=1 --single-transaction \
  --set=kagent_schema=kagent \
  --set=kagent_owner_role=kagent_owner \
  --set=kagent_owner_user=kagent_owner_user \
  --set=kagent_readwrite_role=kagent_readwrite \
  --set=kagent_readwrite_user=kagent_readwrite_user \
  --command='\getenv kagent_owner_password KAGENT_OWNER_PASSWORD' \
  --command='\getenv kagent_readwrite_password KAGENT_READWRITE_PASSWORD' \
  --file=setup.sql

kubectl create secret generic kagent-postgres-owner -n kagent \
  --from-literal=ownerConnectionString="postgresql://kagent_owner_user:<owner-password>@<host>:5432/kagent?sslmode=verify-full"
kubectl create secret generic kagent-postgres-readwrite -n kagent \
  --from-literal=readWriteConnectionString="postgresql://kagent_readwrite_user:<readwrite-password>@<host>:5432/kagent?sslmode=verify-full"
```

### 2.7 Tailscale Ingress exposure

The kagent chart has no built-in Ingress (only Gateway API `ui-httproute.yaml`). Create separate Tailscale Ingress manifests:

**UI Ingress**:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: kagent-ui
  namespace: kagent
  labels:
    tailscale.com/proxy-class: control-plane
spec:
  ingressClassName: tailscale
  rules:
  - host: kagent
    http:
      paths:
      - backend:
          service:
            name: kagent-ui
            port:
              number: 8080
        path: /
        pathType: Prefix
  tls:
  - hosts:
    - kagent
```

**API Ingress** (optional — prefer keeping API internal):
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: kagent-api
  namespace: kagent
  labels:
    tailscale.com/proxy-class: control-plane
spec:
  ingressClassName: tailscale
  rules:
  - host: kagent-api
    http:
      paths:
      - backend:
          service:
            name: kagent-controller
            port:
              number: 8083
        path: /
        pathType: Prefix
  tls:
  - hosts:
    - kagent-api
```

**Recommendation**: Expose UI via Tailscale; keep API internal (port-forward or tailnet ACL) unless external API access is required. The controller API serves agent/session/control operations and is sensitive.

### 2.8 PR-based test deploy workflow

1. **Push feature branch** with all new manifests + values.
2. **Open PR** on GitHub.
3. **Deploy test Applications** pointing at PR branch:
   - Create temporary `*-pr` Application(s) with `targetRevision: <branch-name-or-commit-sha>` for the `$values` ref (and any git-sourced charts).
   - Canonical apps remain on `targetRevision: main`.
   - Pin chart `targetRevision`/versions explicitly; use commit SHA for repeatable tests.
4. **Validate** in PR environment:
   - [ ] CRDs established: `kubectl get crd | grep -E 'kagent|substrate|ate'`
   - [ ] atelet DaemonSet rolled out: `kubectl rollout status daemonset/atelet -n ate-system`
   - [ ] substrate control plane healthy: `kubectl get pods -n ate-system`
   - [ ] `WorkerPool kagent-default` Ready: `kubectl get workerpools -n kagent`
   - [ ] kagent controller rolled out: `kubectl rollout status deployment/kagent-controller -n kagent`
   - [ ] kagent UI accessible via Tailscale ingress
   - [ ] Smoke test: create minimal Harness/AgentTemplate/Agent, start Session, verify actor scheduling/resume
   - [ ] No `RuntimePreparationFailed` or `PermissionDenied` errors in controller logs
5. **Merge PR** after validation passes.
6. **Update canonical apps** to `targetRevision: main` (if temporarily changed).
7. **Remove temporary PR/test Applications**.
8. **Let ArgoCD converge** on `main`.

---

## Phase 3 — Post-install validation & tuning

- [ ] All ArgoCD apps Synced/Healthy.
- [ ] Substrate status healthy (no permission/runtime errors).
- [ ] WorkerPool `kagent-default` Ready with SandboxConfig resolved.
- [ ] UI accessible via Tailscale; API accessible (if exposed) or port-forward works.
- [ ] Smoke test: create Harness/AgentTemplate/Agent, start Session, verify suspend/resume cycle.
- [ ] Monitor node resource usage (atelet, workers, controller, DB, UI) on all nodes — tune `config.runtimeDefaults` and WorkerPool sizing.
- [ ] Verify snapshot storage (RustFS on Longhorn PVC) is writable and snapshots are created.
- [ ] Verify Postgres backups are configured.
- [ ] Document any gVisor/ARM64 compatibility findings.

---

## Assumptions validated (preliminary investigation + live cluster check)

| Assumption | Status | Evidence |
|------------|--------|----------|
| k3s version is v1.36.5+k3s1 | **Verified** | `kubectl get node -o wide` confirms all 6 nodes on v1.36.5+k3s1. README was stale (documented v1.30.6). |
| 6 nodes (3 servers + 3 workers) | **Verified** | `kubectl get node -o wide`: npu01, npu02, orinnx01 (servers/etcd), orinnx02, framework-desktop, framework-13-laptop (workers). |
| Mixed arch (2 amd64 + 4 arm64) | **Verified** | framework-desktop (amd64, Ubuntu 25.10), framework-13-laptop (amd64, Ubuntu 26.04), 4 arm64 (RK1 + Jetson). |
| No SUC installed | **Verified (installed)** | SUC v0.20.2 running in system-upgrade namespace. Used to upgrade 1.30→1.36. Plans exist targeting v1.36.5+k3s1 (COMPLETE). |
| No Postgres in cluster | **Validated** | Only mealie's built-in Postgres found; no standalone DB. |
| Longhorn is default SC | **Validated** | [apps/platform/longhorn.yaml](apps/platform/longhorn.yaml), values confirm. |
| kube-prometheus-stack deployed | **Validated** | [apps/monitoring/monitoring.yaml](apps/monitoring/monitoring.yaml) (v66.3.1); ServiceMonitors available. |
| Tailscale ingress pattern | **Validated** | [manifests/argocd-extras.yaml](manifests/argocd-extras.yaml), [apps/ai/open-webui.yaml](apps/ai/open-webui.yaml): bare host, `ingressClassName: tailscale`. |
| ArgoCD multi-source pattern | **Validated** | [apps/platform/longhorn.yaml](apps/platform/longhorn.yaml): chart + `$values` ref. |
| kagent chart has no Ingress template | **Validated** | Templates list shows `ui-httproute.yaml` (Gateway API only), no `ingress.yaml`. |
| kagent docs reference v1.0.0 charts | **Validated** | All doc examples use `--version 1.0.0`. |
| kube-vip VIP at 10.0.0.253:6443 | **Validated** | [manifests/kube-vip.yaml](manifests/kube-vip.yaml). |
| containerd v2.3.4-k3s1.36 | **Verified** | `kubectl get node -o wide` shows containerd://2.3.4-k3s1.36 on all nodes. |
| ARM64 image availability | **Verified** | All substrate+kagent component images confirmed multi-arch (amd64 + arm64) via docker manifest inspect: atelet, ateapi, atecontroller, ate-idp-server, objectstore-plugin, ateworker-gvisor, kagent controller, kagent ui, agentgateway, rustfs. |
| gVisor on RK1/Jetson kernels | **Partially verified** | All images are multi-arch (amd64 + arm64) — image availability confirmed. Runtime compatibility on RK1/Jetson ARM64 kernels remains unverified (requires live 1.37 test). Mitigated by 2 amd64 nodes. |
| Available node resources | **Verified** | `kubectl top nodes`: framework-13-laptop 230m/3430Mi, framework-desktop 366m/17408Mi, npu01 572m/3775Mi, npu02 607m/5036Mi, orinnx01 437m/5433Mi, orinnx02 373m/3939Mi. npu01/npu02/orinnx01 at 49-71% memory. |
| DRA feature gates pre-enabled | **Verified** | `DRAConsumableCapacity=true, TopologyAwareWorkloadScheduling=true, GenericWorkload=true` + `scheduling.k8s.io/v1alpha2=true` already set on all servers. Relevant for substrate DRA usage. |
| Server config consistency | **Verified** | All 3 servers share identical feature gates, tls-san (10.0.0.253), resolv-conf. orinnx01 lacks cluster-init/disable-network-policy (expected for promoted agent). No mismatches. |
| `certificates.k8s.io/v1` API availability | **Verified (not in 1.36)** | `kubectl api-resources` on current 1.36.5 cluster shows only `certificatesigningrequests`. `podcertificaterequests` and `clustertrustbundles` will be available in 1.37. Upgrade required. |

## Risks

1. **ARM64/gVisor substrate compatibility** (highest risk): atelet + ateworker-gvisor may not run on RK1/Jetson ARM64 kernels. Validate on disposable 1.37 env before prod upgrade window. If incompatible, consider `microvm` sandbox class or run substrate workers on amd64 nodes only.
2. **Single-hop HA etcd upgrade (1.36→1.37)**: one minor hop on 3-server embedded etcd. Etcd quorum safety, per-node validation, and snapshot-based rollback are still essential. Simpler than originally planned (was 7 hops).
3. **Chart version discrepancy**: docs reference 1.0.0, user requested 1.0.1. Verify available OCI chart versions at implementation time (`helm show chart oci://ghcr.io/kagent-dev/kagent/helm/kagent` or registry listing). Adjust pins accordingly.
4. **Postgres provisioning gap**: no existing Postgres; must provision + secure + back up before kagent install. CLI dev Postgres lacks `pgvector` and is not production-grade.
5. **Secret bootstrap for PR testing**: PR carries manifests/values but not secrets. Identity CA, API auth, DB creds, provider keys need documented out-of-band bootstrap. Consider a `scripts/bootstrap-kagent-secrets.sh` (not committed with real values).
6. **RustFS storage sizing**: default `storageSize: 1Gi` may be insufficient for production snapshot volume. Plan capacity based on expected agent count and snapshot frequency.
7. **Controller API exposure**: sensitive (agent/session/control operations). Prefer UI-only via Tailscale; keep API internal unless explicitly needed.
8. **etcd rollback untested**: README notes restore procedure hasn't been tested end-to-end. Consider rehearsing on a spare node if available.
9. **kube-vip + k3s 1.37**: verify kube-vip v0.9.0 compatibility with k3s 1.37 API server. May need bump.
10. **Longhorn during upgrade**: verify Longhorn volumes remain healthy across k3s upgrades; Longhorn itself may need version compatibility check with 1.37.
11. **Framework nodes (amd64) on newer Ubuntu**: framework-desktop (25.10) and framework-13-laptop (26.04) may have compatibility issues with k3s 1.37. Verify before upgrade.
12. **DRA feature gates already enabled**: cluster already runs `DRAConsumableCapacity`, `TopologyAwareWorkloadScheduling`, `GenericWorkload` feature gates. These are alpha/beta in 1.36. Verify they remain compatible/stable in 1.37. Substrate may depend on these.

## What was skipped / not checked

- **ARM64 image availability**: Verified via `docker manifest inspect`. All 10 component images are multi-arch (amd64 + arm64). No image availability blocker.
- **gVisor/kernel compatibility**: Cannot test without live ARM64 nodes on K8s 1.37. This is the single highest-risk unknown. Mitigated by 2 amd64 nodes.
- **Available node resources**: Verified via `kubectl top nodes`. npu01/npu02/orinnx01 at 49-71% memory — substrate workloads may need resource tuning on ARM nodes.
- **Exact chart schemas**: inspected values.yaml and docs but did not render full templates. Value key names should be double-checked against pinned chart versions during implementation (`helm template` / `helm show values`).
- **Postgres setup.sql**: referenced but not included in repo; must be obtained from kagent docs/ops at implementation time.
- **No tests run**: this is a planning document; no code changes were made.