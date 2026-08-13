# Dagster

Dagster dashboard for the ai-cluster, exposed on the tailnet via a Tailscale
Ingress: **https://dagster.tail79a5c8.ts.net** (local default account).

The code location in `dagster/rayjobs.py` mirrors the Airflow
`ray_train_workflow` (`download_dataset -> train_model`) on KubeRay: each op
submits a `RayJob` CR that boots a throwaway RayCluster
(`rayproject/ray:2.55.0`) and runs an inline demo script, then waits for the
job to succeed. Launch it from the UI's Launchpad (job `ray_train_workflow`).

## How the pieces fit

- ArgoCD Application `apps/ai/dagster.yaml` (stack `ai`) installs the official
  `dagster` helm chart (1.13.17, `K8sRunLauncher`) and applies
  `manifests/dagster/rayjob-rbac.yaml` (binds the shared `airflow-rayjob`
  ClusterRole to the run pods' `default` service account so ops can
  create/read `rayjobs` in the `kuberay` namespace).
- Code syncs from this repo via git-sync (init container clones once, a sidecar
  keeps it in sync), pinned to the `add/dagster` branch; `includeConfigInLaunchedRuns`
  carries the same volumes/containers into each K8s run pod.
- RayJobs run in the `kuberay` namespace (KubeRay operator watches all
  namespaces). Each RayJob uses `shutdownAfterJobFinishes: true`, so its
  RayCluster is torn down when the job ends.
- Postgres (metadata DB) persists on `longhorn`.

## Deploy / update

From `main`, once this branch has merged (see notes below):

```sh
kubectl apply -f apps/ai/dagster.yaml
argocd app sync dagster
```

ArgoCD sync renders the chart + RBAC and applies everything in the `dagster`
namespace. The code location appears in the UI within ~1 minute (git-sync
period) and the run pod spins up a RayJob per op.

## Notes / follow-ups after the `add/dagster` branch merges

- Flip the git-sync `--branch` and the manifests source `targetRevision` in
  `apps/ai/dagster.yaml` from `add/dagster` to `main`.
- The entrypoint scripts are demos; swap in the real dataset + training code
  (the ops are generic).
