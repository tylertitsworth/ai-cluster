# ArgoCD App and Values Files

This folder contains ArgoCD `Application` manifests, one subdirectory per `stack` label (`ai/`, `games/`, `gpu/`, `home/`, `monitoring/`, `platform/`, `servarr/`). Chart values used by multi-source applications live in that stack's `values/` subdirectory, named after the app (e.g. `apps/ai/values/ollama.yaml` for `apps/ai/ollama.yaml`).

## Prerequisites

Install ArgoCD

```sh
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# Change Service to Load Balancer for use with metallb
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "LoadBalancer"}}'
```

## Updating Applications

Apply all ArgoCD `Application` and `ApplicationSet` manifests in this folder:

```sh
rg -l '^kind:\s*(Application|ApplicationSet)$' apps --glob '*.yaml' | xargs -r -n1 kubectl apply -f
```

Each values file pairs with an application configuration. The title of the values file corresponds to the application name, and sometimes also the namespace.
