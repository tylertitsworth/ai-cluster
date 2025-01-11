# Jetson Exporter

Jetson Exporter is a Prometheus exporter for NVIDIA Jetson devices. It collects various metrics from the Jetson hardware and exposes them for Prometheus to scrape. This exporter can be deployed on a Kubernetes cluster and visualized using Grafana.

## Setup

### Docker

Build the docker image on an arm64 device (or use `docker buildx build`)

```sh
# Build
# -t : tag image with name
docker buildx build --platform=arm64 -t jetson-exporter .
# Run
# -d : detach from terminal (run in background)
# -p : port-forward using bridge
docker run -d \
    -v /run/jtop.sock:/run/jtop.sock \
    -p 8000:8000 \
    --name jetson-exporter \
    jetson-exporter
# Test
curl localhost:8000/metrics
# Cleanup
docker container stop jetson-exporter
```

### Kubernetes

Deploy to Kubernetes using the combined manifest file:

```sh
kubectl apply -n monitoring \
    -f exporter.yaml
```

This manifest containers 3 resources:

1. DaemonSet - 1 Pod per `node-type: jetson`
2. Service - All Pods under 1 ClusterIP
3. ServiceMonitor - Prometheus Configuration for Service

With a few notes:

- Each container creates a hostpath volume to `/run/jtop.sock`. If the Jetson node doesn't have jtop installed and running this may fail
- The ServiceMonitor assumes a prometheus resource configuration `prometheus: monitoring-kube-prometheus-prometheus`
- The Service keeps the same port `8000` value
- Each pod has `imagePullPolicy: Always` for new revisions of the same tag

## Development

On a compatible Jetson device, the metrics can be accessed from the python interpreter.

```python
from jtop import jtop
# import jtop
test = jtop()
# initialize jtop object
test.start()
# start jtop
test.ok()
# True
dir(test)
# Print all options
```

If these values change for whatever reason, it's because the base container `rbonghi/jetson_stats:latest` has changed. After making changes, build the docker image and push it to the public registry.

```sh
docker login
docker tag jetson-exporter totalsundae/ai-cluster:jetson-exporter
docker push totalsundae/ai-cluster:jetson-exporter
```

Then, restart the DaemonSet.

```sh
kubectl rollout -n monitoring restart daemonset/jetson-exporter
```

Afterwards, verify your results in Prometheus and Grafana.
