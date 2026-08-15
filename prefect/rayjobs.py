"""
Ray train workflow for Prefect.

Mirrors dagster/rayjobs.py and airflow/dags/ray_train_workflow.py on KubeRay:
each task submits a RayJob CR that boots a throwaway RayCluster
(rayproject/ray:2.55.0) and runs an inline demo script, then waits for the
job to succeed.

The flow runs with the Prefect API pointed at the self-hosted server
(PREFECT_API_URL=http://prefect-server.prefect.svc.cluster.local:4200/api)
so runs are recorded in the server.

To train for real, replace the entrypoint scripts with the actual training
code; the tasks are generic and stay.
"""

import re
import time

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from prefect import flow, task

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

_TERMINAL_STATUSES = {
    "SUCCEEDED",
    "FAILED",
    "ABORTED",
    "STOPPED",
    "SUBMIT_FAILED",
    "KUBERAY_UNHEALTHY",
}


def _sanitize_name(raw: str) -> str:
    name = re.sub(r"[^a-z0-9.-]+", "-", raw.lower()).strip("-")
    return name[:63].rstrip(".-")


def _rayjob(name, entrypoint, worker_replicas, worker_cpus):
    return {
        "apiVersion": f"{RAY_GROUP}/{RAY_VERSION}",
        "kind": "RayJob",
        "metadata": {"name": name, "namespace": RAY_NAMESPACE},
        "spec": {
            "entrypoint": entrypoint,
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
                        "replicas": worker_replicas,
                        "minReplicas": worker_replicas,
                        "maxReplicas": worker_replicas,
                        "rayStartParams": {"num-cpus": str(worker_cpus)},
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "ray-worker",
                                        "image": RAY_IMAGE,
                                        "resources": {
                                            "requests": {
                                                "cpu": str(worker_cpus),
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


def _run_rayjob(name, entrypoint, worker_replicas=2, worker_cpus=1, poll_interval=10, timeout=900):
    name = _sanitize_name(name)
    config.load_incluster_config()
    api = client.CustomObjectsApi()
    try:
        api.create_namespaced_custom_object(
            RAY_GROUP, RAY_VERSION, RAY_NAMESPACE, RAY_PLURAL,
            _rayjob(name, entrypoint, worker_replicas, worker_cpus),
        )
    except ApiException as exc:
        if exc.status != 409:
            raise
    deadline = time.monotonic() + timeout
    job_status = "NEW"
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        status = api.get_namespaced_custom_object(
            RAY_GROUP, RAY_VERSION, RAY_NAMESPACE, RAY_PLURAL, name
        ).get("status", {})
        job_status = status.get("jobStatus", "NEW")
        if job_status in _TERMINAL_STATUSES:
            break
    else:
        _cleanup(api, name)
        raise TimeoutError(f"RayJob {name} did not finish within {timeout}s")
    if job_status != "SUCCEEDED":
        _cleanup(api, name)
        raise RuntimeError(f"RayJob {name} finished with status {job_status!r}")
    return job_status


def _cleanup(api, name):
    try:
        api.delete_namespaced_custom_object(
            RAY_GROUP, RAY_VERSION, RAY_NAMESPACE, RAY_PLURAL, name
        )
    except Exception:
        pass


@task(name="download_dataset")
def download_dataset():
    return _run_rayjob("prefect-download-dataset", DOWNLOAD_DATASET)


@task(name="train_model")
def train_model(downloaded: str):
    return _run_rayjob("prefect-train-model", TRAIN_MODEL)


@flow(name="ray_train_workflow")
def ray_train_workflow():
    train_model(download_dataset())


if __name__ == "__main__":
    spec = _rayjob("check", "echo hi", 2, 1)
    assert spec["apiVersion"] == "ray.io/v1"
    assert spec["spec"]["rayClusterSpec"]["workerGroupSpecs"][0]["replicas"] == 2
    assert spec["spec"]["shutdownAfterJobFinishes"] is True
    assert _sanitize_name("  My.Job_Name!! ") == "my.job-name"
    print("rayjobs.py self-check OK")
