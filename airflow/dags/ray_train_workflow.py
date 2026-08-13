"""
Ray train workflow.

Mirrors flyte/train.py (download_dataset -> train_model) on KubeRay: each task
submits a RayJob CR that boots a throwaway RayCluster (rayproject/ray:2.55.0)
and runs an inline demo script.

There is no Apache Ray provider for Airflow 3 (the legacy airflow-provider-ray
is archived and Airflow-2-era), so we talk to KubeRay directly through the
in-tree cncf-kubernetes provider (KubernetesHook), which falls back to
in-cluster config with no Connection setup.

To train for real, replace the entrypoint scripts with the actual training
code; the operator is generic and stays.
"""

import re
import time
from datetime import datetime

from kubernetes import client
from kubernetes.client.rest import ApiException

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.models import BaseOperator
from airflow.providers.cncf.kubernetes.hooks.kubernetes import KubernetesHook

RAY_IMAGE = "rayproject/ray:2.55.0"
RAY_NAMESPACE = "kuberay"
RAY_GROUP, RAY_VERSION, RAY_PLURAL = "ray.io", "v1", "rayjobs"

# KubeRay runs the RayJob entrypoint via `bash -lc <entrypoint>`.
DOWNLOAD_DATASET = """\
cat > /tmp/download_dataset.py <<'PYEOF'
import ray
from ray.data import from_items

ray.init()
N, CLASSES, SHARDS = 10_000, 100, 8


@ray.remote
def make_shard(i):
    return [{"sample_id": j, "label": j % CLASSES} for j in range(i, N, SHARDS)]


rows = [r for f in ray.get([make_shard.remote(i) for i in range(SHARDS)]) for r in f]
ds = from_items(rows)
print(f"[download_dataset] samples={ds.count()} classes={len(ds.unique('label'))}")
print("[download_dataset] done")
PYEOF
python /tmp/download_dataset.py
"""

TRAIN_MODEL = """\
cat > /tmp/train_model.py <<'PYEOF'
import ray
from ray.data import from_items

ray.init()
N, CLASSES, EPOCHS = 10_000, 100, 5
ds = from_items([{"sample_id": j, "label": j % CLASSES} for j in range(N)])


@ray.remote
def fit_fold(fold_ds, epochs, seed):
    import random

    rng = random.Random(seed)
    loss = 2.0
    for _ in range(epochs):
        loss = loss * 0.7 + rng.random() * 0.01  # fake SGD progress
    return loss


folds = ds.repartition(8).split(8)
futures = [fit_fold.remote(fold, EPOCHS, seed=i) for i, fold in enumerate(folds)]
losses = ray.get(futures)
print(f"[train_model] folds={len(losses)} mean_loss={sum(losses)/len(losses):.4f}")
print("[train_model] done")
PYEOF
python /tmp/train_model.py
"""

_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "STOPPED", "SUBMIT_FAILED", "KUBERAY_UNHEALTHY"}


def _sanitize_name(raw: str) -> str:
    name = re.sub(r"[^a-z0-9.-]+", "-", raw.lower()).strip("-")
    return name[:63].rstrip(".-")


class RayJobOperator(BaseOperator):
    """Submit a KubeRay RayJob CR and wait until it succeeds."""

    template_fields = ("ray_job_name",)

    def __init__(
        self,
        *,
        ray_job_name: str,
        entrypoint: str,
        worker_cpus: int = 1,
        worker_replicas: int = 2,
        poll_interval: int = 10,
        timeout: int = 900,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.ray_job_name = ray_job_name
        self.entrypoint = entrypoint
        self.worker_cpus = worker_cpus
        self.worker_replicas = worker_replicas
        self.poll_interval = poll_interval
        self.timeout = timeout

    def _rayjob(self, name: str) -> dict:
        return {
            "apiVersion": f"{RAY_GROUP}/{RAY_VERSION}",
            "kind": "RayJob",
            "metadata": {"name": name, "namespace": RAY_NAMESPACE},
            "spec": {
                "entrypoint": self.entrypoint,
                "shutdownAfterJobFinishes": True,
                "rayClusterSpec": {
                    "headGroupSpec": {
                        "rayStartParams": {"num-cpus": "0"},
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "ray-head",
                                        "image": RAY_IMAGE,
                                        "resources": {
                                            "requests": {"cpu": "1", "memory": "2Gi"},
                                            "limits": {"memory": "2Gi"},
                                        },
                                    }
                                ]
                            }
                        },
                    },
                    "workerGroupSpecs": [
                        {
                            "groupName": "workers",
                            "replicas": self.worker_replicas,
                            "minReplicas": self.worker_replicas,
                            "maxReplicas": self.worker_replicas,
                            "rayStartParams": {"num-cpus": str(self.worker_cpus)},
                            "template": {
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "ray-worker",
                                            "image": RAY_IMAGE,
                                            "resources": {
                                                "requests": {
                                                    "cpu": str(self.worker_cpus),
                                                    "memory": "2Gi",
                                                },
                                                "limits": {"memory": "2Gi"},
                                            },
                                        }
                                    ]
                                }
                            },
                        }
                    ],
                },
            },
        }

    def execute(self, context):
        name = _sanitize_name(self.ray_job_name)
        if not name:
            raise AirflowException(f"Invalid RayJob name: {self.ray_job_name!r}")
        hook = KubernetesHook(conn_id="kubernetes_default")
        api = hook.get_conn().CustomObjectsApi()
        try:
            api.create_namespaced_custom_object(
                RAY_GROUP, RAY_VERSION, RAY_NAMESPACE, RAY_PLURAL, self._rayjob(name)
            )
            self.log.info("Submitted RayJob %s in namespace %s", name, RAY_NAMESPACE)
        except ApiException as exc:
            if exc.status != 409:
                raise
            # Already exists from a previous attempt of this task run: resume.
            self.log.info("RayJob %s already exists, resuming wait", name)
        deadline = time.monotonic() + self.timeout
        job_status = "NEW"
        while time.monotonic() < deadline:
            time.sleep(self.poll_interval)
            status = api.get_namespaced_custom_object_status(
                RAY_GROUP, RAY_VERSION, RAY_NAMESPACE, RAY_PLURAL, name
            ).get("status", {})
            job_status = status.get("jobStatus", "NEW")
            self.log.info("RayJob %s status: %s", name, job_status)
            if job_status in _TERMINAL_STATUSES:
                break
        else:
            self._cleanup(api, name)
            raise AirflowException(f"RayJob {name} did not finish within {self.timeout}s")
        if job_status != "SUCCEEDED":
            self._cleanup(api, name)
            raise AirflowException(f"RayJob {name} finished with status {job_status!r}")
        return job_status

    def _cleanup(self, api, name):
        try:
            api.delete_namespaced_custom_object(
                RAY_GROUP, RAY_VERSION, RAY_NAMESPACE, RAY_PLURAL, name
            )
        except Exception as exc:  # best-effort
            self.log.warning("Failed to delete RayJob %s: %s", name, exc)


with DAG(
    dag_id="ray_train_workflow",
    schedule=None,
    start_date=datetime(2026, 8, 13),
    catchup=False,
    default_args={"owner": "airflow", "retries": 0},
    max_active_runs=1,
    tags=["ray", "demo", "kuberay"],
) as dag:
    download_dataset = RayJobOperator(
        task_id="download_dataset",
        ray_job_name="download-dataset-{{ run_id }}",
        entrypoint=DOWNLOAD_DATASET,
        worker_cpus=1,
        worker_replicas=2,
        timeout=900,
    )
    train_model = RayJobOperator(
        task_id="train_model",
        ray_job_name="train-model-{{ run_id }}",
        entrypoint=TRAIN_MODEL,
        worker_cpus=1,
        worker_replicas=2,
        timeout=900,
    )

    download_dataset >> train_model
