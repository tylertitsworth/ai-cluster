# Airflow (Apache Airflow 3)

Airflow 3 dashboard for the ai-cluster. The API server component serves both
the web UI and the REST API; it is exposed on the tailnet via a Tailscale
Ingress: **https://airflow.tail79a5c8.ts.net** (admin / admin).

The DAG in `airflow/dags/ray_train_workflow.py` mirrors the Flyte
`train_workflow` (`download_dataset -> train_model`) on KubeRay: each task
submits a `RayJob` CR that boots a throwaway RayCluster
(`rayproject/ray:2.55.0`) and runs an inline demo script, then waits for the
job to succeed.

## Why a custom operator instead of a "ray provider"?

There is no Apache Ray provider for Airflow 3 (`apache-airflow-providers-apache-ray`
does not exist; the legacy `airflow-provider-ray` is archived and Airflow-2-era).
The DAG therefore talks to KubeRay directly through the in-tree
`cncf-kubernetes` provider (`KubernetesHook`), which is bundled in the official
image and falls back to in-cluster config with zero Connection setup.

## How the pieces fit

- ArgoCD Application `apps/ai/airflow.yaml` (stack `ai`) installs the official
  `airflow` helm chart (1.22.0, Airflow 3.2.2, default CeleryExecutor) and
  applies `manifests/airflow/rayjob-rbac.yaml` (ClusterRole/Binding so the
  scheduler + worker service accounts can create/read `rayjobs` in the
  `kuberay` namespace).
- DAGs are synced from this repo via git-sync (`dags.gitSync`), subPath
  `airflow/dags`, pinned to the `add/airflow` branch.
- RayJobs run in the `kuberay` namespace (KubeRay operator watches all
  namespaces). Each RayJob uses `shutdownAfterJobFinishes: true`, so its
  RayCluster is torn down when the job ends.
- Postgres (metadata DB) and Redis (Celery broker) persist on `longhorn`.

## Deploy / update

From `main`, once this branch has merged (see notes below):

```sh
kubectl apply -f apps/ai/airflow.yaml
argocd app sync airflow
```

ArgoCD sync renders the chart + RBAC and applies everything in the `airflow`
namespace. DAGs appear in the UI within ~1 minute (git-sync period 5s) and the
scheduler picks up `ray_train_workflow` automatically.

## Notes / follow-ups after the `add/airflow` branch merges

- Flip `dags.gitSync.branch`/`ref` and the manifests source `targetRevision`
  in `apps/ai/airflow.yaml` from `add/airflow` to `main`.
- `config.api.base_url` is hardcoded to the current MagicDNS name; update if
  the tailnet/ingress host changes.
- The entrypoint scripts are demos; swap in the real dataset + training code
  (the operator is generic).
