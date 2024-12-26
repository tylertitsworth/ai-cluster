# ArgoCD Values Files

This repository contains the values files used for configuring ArgoCD applications.

## Prerequisites

Install ArgoCD

```sh
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# Change Service to Load Balancer for use with metallb
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "LoadBalancer"}}'
```

## Installation

Each values file pairs with an application configuration. The title of the file corresponds to the application name, and sometimes also the namespace.

Each file has a repo URL, path, and target revision associated with the file as a comment at the beginning of the file.