# [Turing Pi](https://turingpi.com/) 2.5.2 Cluster

This is a repository for all of the information related to my journey with the Turing Pi line of homelab products. I'm an MLOps Engineer by trade so I plan to use this as a Kubernetes cluster for Edge AI Inference and other weird experiments on arm. This build took about 3 weeks to ship, and another 2 weeks to get completely flashed and assembled, with a good portion of those 2 weeks spent on just one step (more on that below).

![Finished Build](https://github.com/user-attachments/assets/2a9bb39f-f53c-4f68-b98d-19f580fa804b)
![Inside Finished Build](https://github.com/user-attachments/assets/9333f08e-3807-4ad6-8256-c259e3f027c8)

> Finished Turing Pi sitting on the shelf next to my Computer, where it runs 24/7

This document can be divided into two sections, the front half being the spark notes of the installation and setup process for everything, followed by the application side where I go into what I've actually done with the nodes.

## Assembly

Upon opening and inspecting all of the parts I didn't find any issues. I quickly started adding heatsinks to modules and assmebling with the rough approximation found in the image below:

![Plan](https://github.com/user-attachments/assets/78dcc608-8914-43de-851d-dc4f5788fe2f)

Jetsons get more storage because I knew that they would require an entire suite of drivers and software just to run the GPU, and the flashing process might require some extra scratch space.

Once I started adding the modules to the board, I noticed that a lot of pressure had to be applied to the node slots to actually get something to click in, similar to a RAM stick on a cheap motherboard. Similarly, with the node storage M.2 slots on the back of the board, the process of swapping a node for flashing became very tedious. I'm not sure how Turing could've worked around this given that this is a space optimization.

My 2nd RK1 install had a slight hiccup with the fan cable getting in the way of the fan, meaning I had to play around with how it routed in order to not cause any noise/damage to the cable. In my photo above, you can see how it's routed weirdly to the opposite side of the connector. I'm not sure how I messed that up, but I couldn't get it to route nicely.

### Parts

I spent about ~$1600 for all of the parts to make this cluster, including the case that is going to come at the end of January.

1x [Turing Pi 2.5.2](https://turingpi.com/product/turing-pi-2-5/)

> With [24pin PSU](https://turingpi.com/product/pico-psu/)

2x [Turing RK1](https://turingpi.com/product/turing-rk1/?attribute_ram=8+GB) Compute Modules

> With [Heatsink + Fan](https://turingpi.com/product/rk1-heatsink/)

2x Nvidia Jetson Nano

> Via Arrow

2x 256GB M.2 SSDs

> For the 2 RK1s

2x 1TB M.2 SSDs

> For the Jetson Orin Nano's

1x 12V 12A Power Supply

> Vendor Neural, the one I grabbed goes up to 144W and was slightly cheaper than what is on Turing Pi's site

1x [Turing Pi Case](https://turingpi.com/product/turing-mini-itx-case/)

### BMC

Powering on the board gave a satisfying light-up, and before long, I was able to access the BMC at `turingpi.local`. With the default credentials being `root/turing`, I had a sigh of relief that everything was working as intended and I could power on a node without issue.

I quickly found that switching to an SSH connection was much more convenient because the BMC doesn't actually refresh the state of the nodes on the board. All it does is send commands via an API. This might seem like a small thing, but what it means in reality is that the web UI doesn't actually tell you whether your nodes are on/off. It also lacks a [UART](https://docs.turingpi.com/docs/tpi-uart) log output, which is necessary for any kind of debugging.

## Flashing & OS Setup

By default, nothing is flashed to these compute modules, and so I need to use the BMC to flash these boards and install Ubuntu onto them. Furthermore, my router doesn't really recognize these devices so I just want to put a quick note in here that I found their IP by using [UART](https://docs.turingpi.com/docs/tpi-uart) log outputs with a command like `tpi uart -n 1 set --cmd 'ip a'` and `tpi uart -n 1 get`.

### Turing RK1

I went with the [BMC UI method](https://docs.turingpi.com/docs/turing-rk1-flashing-os) for flashing both RK1s, I used Ubuntu 22.04 LTS server since I won't have any use for a GUI. The process was reletively uneventful. I was able to move my eMMC OS Installation to my NVMe drive using `ubuntu-rockchip-install`.

### Nvidia Jetson Orin Nano

I have the SOCM from the Jetson Orin NX Developer Kit and the Jetson Orin Nano Super Developer Kit, both are the same board with a different model name. Both have 8GB of memory shared with both the CPU and GPU.

Flashing the Orin NX took about a week and a half or so. I wrote down my experience with the Jetson in a [separate document](./JETSON.md). The super was the same experience but in about 2 hours.

## K3s Installation

I installed K3s on Node 1 on the Turing Pi and as nodes got up and running I added them to the cluster. I decided not to use Ansible for this project because I'm using a trivial amount of nodes that have very different configurations.

Setting up any Node in K3s is trivial, and I'm super happy that it's this way:

```sh
# Master
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644 --disable servicelb --token <my-token> --node-ip 192.168.1.41 --disable-cloud-controller --disable local-storage
# Get kubeconfig from /etc/rancher/k3s/k3s.yaml, replace server field with K3S_URL
# Worker
curl -sfL https://get.k3s.io | K3S_URL=https://192.168.1.41:6443 K3S_TOKEN=<my-token> sh -
```

Afterwards, you get something like this:

```txt
$ kubectl get node -o wide
NAME             STATUS   ROLES                  AGE    VERSION        INTERNAL-IP    EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION      CONTAINER-RUNTIME
npu01.local      Ready    control-plane,master   55d    v1.30.6+k3s1   192.168.1.41   <none>        Ubuntu 22.04.5 LTS   5.10.160-rockchip   containerd://1.7.22-k3s1
npu02.local      Ready    control-plane          55d    v1.30.6+k3s1   192.168.1.44   <none>        Ubuntu 22.04.5 LTS   5.10.160-rockchip   containerd://1.7.22-k3s1
orinnx01.local   Ready    worker                 7d4h   v1.30.6+k3s1   192.168.1.15   <none>        Ubuntu 22.04.5 LTS   5.15.148-tegra      containerd://1.7.22-k3s1
orinnx02.local   Ready    worker                 7d5h   v1.30.6+k3s1   192.168.1.14   <none>        Ubuntu 22.04.5 LTS   5.15.148-tegra      containerd://1.7.22-k3s1
```

> The RK1's have the label `node-type=npu` and the Jetson `node-type=jetson`. This will be important later.

I also needed to [uninstall](https://docs.k3s.io/installation/uninstall) k3s-agent a couple of times to get the naming I wanted just right.

### Networking

After following the basic instructions to install [MetalLB](https://docs.turingpi.com/docs/turing-pi2-kubernetes-network-configuration#metallb) I added an address pool for `192.168.1.80-192.168.1.90` and then reserved all of those spaces on my router along with the turing nodes.

Now whenever I have an application that I want to make available on the private network, I can set the service type to `LoadBalancer` and it'll automatically get an IP from that range. Additionally, storage is handled by Longhorn, which I intially added and then removed later in favor of managing with ArgoCD. The same is true for Traefik.

### Tailscale

After setting up the cluster I started deploying apps on it, and then I wanted to invite some of my friends. Rather than exposing anything on a public network, I instead went with Tailscale's free plan to allow 2 of my friends to have access to some specific addresses so they can learn Kuberentes.

Additionally, I installed a [subnet router](https://tailscale.com/kb/1185/kubernetes#subnet-router) so that way all of the cluster addresses could be reached on any of the private network's machines. This little application saves the pain of having to use `kubectl port-forward`. Additionally, any hosts that have a configured Ingress can take advantage of k3s [coredns](https://coredns.io/). Simply add that route to the `coredns` `ConfigMap`:

```txt
.:53 {
  ...
  hosts /etc/coredns/NodeHosts {
    192.168.1.80 open-webui.k3s
    ...
  }
  ...
}
```

> In my case, I can just run `kubectl patch configmap coredns -n kube-system --type merge -p "{\"data\":{\"Corefile\":\"$(cat manifests/Corefile | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')\"}}"`

Then restart coredns, and add the `kube-dns` service IP as a global nameserver in Tailscale. Make sure to override all local DNS and voila! Your subnet router now routes traffic through coreDNS, which acts as a DNS server for the entire tailscale network.

### Nvidia Device Plugin

There is some additional setup required to make sure that the GPU is accessible. The Jetson uses the same device plugin daemonset that any other card uses, and the [documentation](https://docs.turingpi.com/docs/turing-pi2-kubernetes-cluster-nvidia-jetson) for this setup has a lot of unecessary steps. All of the networking stuff was not really required. Like I mention in the Nvidia Flashing & OS Setup document, there is a lot of out of date information surrounding the Orin + Turing Pi, but once `./deviceQuery` runs without fail in a pod I officially had compute on K3s.

Afterwards, I wrote the [Jetson Exporter](./jetson-exporter/README.md) which from what I can tell is the only implementation of jetson stats in Kubernetes.

### NPU

Each RK1 Device has an NPU, and while this NPU is sparsely supported in OSS it has basically no support in the cloud native ecosystem. Since a device plugin for the NPU doesn't exist, I created one. To use the npu in Kubernetes I created a [basic demo](./npu-device-plugin/test.yaml) that runs inference on a pre-converted resnet18 model. The next step is to [serve](https://github.com/airockchip/rknn-llm/tree/main/examples/rkllm_server_demo) an rknn converted llm and utilize it with Open WebUI.

To use an NPU on the cluster, make these additions to the pod spec:

```yaml
spec:
  containers:
    - ...
      resources:
        requests:
          rockchip.com/npu: 1
    #   securityContext:
    #     privileged: true # Required for rknn-toolkit2/rknn-llm
  tolerations:
    - key: "npu"
      operator: "Equal"
      value: "enabled"
      effect: "NoSchedule"
```

## Applications

Now that all of the cluster resources are abstracted, I can get rid of the need to SSH and start deploying applications on Kubernetes.

![Architecture Diagram](https://github.com/user-attachments/assets/6667cff7-26f2-4692-8bb9-e81a655697cf)

> An architecture block diagram of the cluster as it exists today

### Networking

After setting up MetalLB to start load balancing on my private network I added [nginx](https://nginx.org/en/) to the ingress list of supported ingress providers since Flyte doesn't work with Traefik. This variety of ingress classes means that when deploying and application I can just choose whichever is the easiest to implement. Since nginx and traefik are load balanced by Metal they route to specific IP addresses.

[Traefik](https://doc.traefik.io/traefik/) has the [`IngressRoute`](https://doc.traefik.io/traefik/v2.2/routing/providers/kubernetes-crd/#kind-ingressroute) CRD which allows multiple application routes to the same ip address, unlike nginx. This means that I prefer using Traefik over nginx when possible.

Because my private network doesn't have a DNS server, all of these routes need to be manually modified on the client's `/etc/hosts` (`C:\Windows\System32\drivers\etc\hosts` on Windows).

### ArgoCD

One of the first orders of business is to replace the existing longhorn and traefik configurations and add them as [ArgoCD](https://argo-cd.readthedocs.io/en/stable/) [Applications](https://argo-cd.readthedocs.io/en/stable/core_concepts/). ArgoCD is the GitOps application of choice, we can modify and maintain complex deployments from its UI and automatically update applications as new chart versions release.

![ArgoCD Dashboard](https://github.com/user-attachments/assets/865c10a4-f6cb-4ba0-81e2-15bd3c68b5b6)

> The ArgoCD Dashboard

Each values file associated with each application is stored in the [agrocd](./manifests/argocd/README.md) folder. Adding a new application is just about finding a helm chart and customizing to fit the cluster before deploying it using ArgoCD's UI. Once we've completed the deployment and like our configuration, we can modify the application manifest to use the file in this repo as a values file for the application:

```yaml
# from source: to
sources:
  - repoURL: ...
    path: ...
    targetRevision: HEAD
    helm:
      valueFiles:
        - $values/manifests/argocd/<application-name>.yaml
  - repoURL: https://github.com/tylertitsworth/ai-cluster
    targetRevision: HEAD
    ref: values
```

Then we can enable automatic updates, self healing, and pruning.

### Monitoring

Metrics and scraped by [Prometheus](https://prometheus.io/) and then Aggregated by [Grafana](https://grafana.com/). There are a few ways to deploy these applications so I went with the [kube-prom-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack). Namely because I wanted both tools to work together out of the box, and I wanted [Prometheus Operator](https://prometheus-operator.dev/) and [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) as well.

Afterwards I wrote some dashboards:

![K3s Dashboard](https://github.com/user-attachments/assets/7ce9594b-d68d-4cd1-8c14-9d4503cbcdd8)

> K3s Cluster [Dashboard](./grafana/k3s_dashboard.json)

![Jetson Dashboard](https://github.com/user-attachments/assets/b8b9978f-0acb-440f-a573-404d32c72ee2)

> Nvidia Jetson [Dashboard](./grafana/jetson_dashboard.json) using the [jetson exporter](./jetson-exporter/README.md)

Because of how Prometheus is deployed, it's managed by a [`Prometheus`](https://github.com/prometheus-operator/prometheus-operator?tab=readme-ov-file#customresourcedefinitions) CRD. A [`ServiceMonitor`](https://prometheus-operator.dev/docs/developer/getting-started/#using-servicemonitors) has to contain the label `prometheus: monitoring-kube-prometheus-prometheus` in order to be picked up by prometheus and exist on the same namespace that prometheus was deployed on.

#### Logs

Logs are aggregated by [Loki](https://grafana.com/docs/loki/latest/) with the [loki-stack](https://github.com/grafana/helm-charts/tree/main/charts/loki-stack) chart. The stack deploys [Promtail](https://grafana.com/docs/loki/latest/send-data/promtail/). Promtail is the metric aggregator for Loki, which then formats and forwards those logs to Grafana for viewing. To add Loki as a datasource in Grafana, simply add a new Loki datasource and it give it the the connection url `http://loki:3100`.

We need Loki because we can add it as a logging linker in [Flyte](#flyte) to view the task logs without going and searching for them with `kubectl` and `k9s`.

### Flyte

[Flyte](https://github.com/flyteorg/flyte) is an ML Orchestration application that I'm trialing at my workplace. It's intended to replace tools like [Argo Workflows](https://argoproj.github.io/workflows/) and uses postgres and s3 to be a completely stateless ML platform.

Deploying Flyte on anything other than AWS is very difficult, and I tried to leverage a community guide called [Flyte the Hard Way](https://github.com/davidmirror-ops/flyte-the-hard-way), but found that much of the instructions were inaccurate. After seeking further help in the community Slack I was eventually able to deploy Flyte.

For those who are trying to deploy Flyte, and have search far and wide for solutions to their issues, here's the K3s solution:

- Use nginx instead of Traefik
- Check out my [values.yaml](./manifests/argocd/flyte.yaml) file for the [flyte-binary](https://github.com/flyteorg/flyte/tree/master/charts/flyte-binary) chart
- Create a config file at `~/.flyte/config` with the following:

```yaml
admin:
  endpoint: dns:///flyte.k3s
  authType: Pkce
  insecure: false
  caCertFilePath: /home/<username>/.flyte/ca.crt
```

> You will need to create `ca.crt`

#### Distributed Training on NVIDIA Jetsons

The standard use-case for a Jetson, or any Edge AI device is inference. We know this to be true, however, the kinds of devices that are designed for training AI models are prohibitively expensive. If you are a homelabber, and want to train AI models, you aren't going to be using ARM in the present year.

The obvious aside, I'm going to still scale on two Jetsons. And I'm going to do it on Flyte so the process is reproducable. Here's what I did:

1. Create a docker image based on `dustynv/l4t-pytorch:r36.4.0`
   1. I discovered that we can't use the flyte `ImageSpec` to create containers in python because it uses `uv`, and `uv` refuses to install anything whose dependencies don't come from the same index
   2. I created a [builder](https://docs.docker.com/build/builders/) in k3s so that my images would be built on ARM by ARM
   3. I pushed this image to a public dockerhub repository at the tag `totalsundae/ai-cluster:jetson-flyte`
2. Deploy the [KubeFlow Training Operator](https://github.com/kubeflow/training-operator)
   1. Despite having pytorch plugin configured in my flyte values file, Flyte doesn't have the permissions to create or modify the `PyTorchJob` CRD that's used to do the distributed training so we need to modify its cluster role:

      ```yaml
      - apiGroups:
        - kubeflow.org
      resources:
        - pytorchjobs
      verbs:
        - create
        - delete
        - get
        - list
        - patch
        - update
        - watch
      ```

3. Run the existing [PyTorch Lightning Distributed Training Example](https://docs.flyte.org/en/latest/flytesnacks/examples/kfpytorch_plugin/pytorch_lightning_mnist_autoencoder.html).
   1. This workflow does not work out of the box on a Jetson, namely we get the error `nvmlDeviceGetP2PStatus(0,0,NVML_P2P_CAPS_INDEX_READ) failed: Not Supported`. This means that we can't use the `nccl` backend because nvidia didn't add support for P2P on the Jetson. Instead we'll just use `gloo`.
   2. When you make a change to your container, the pods deployed don't have `imagePullPolicy: Always`, so we need to create a [`PodTemplate`](./jetson-flyte/train.py#L27-49)
   3. At the same time, these pods are not using the same shared storage, so I created a [`pvc`](./manifests/flyte-extras.yaml) that is always used in my `PodTemplate`.

After doing these steps I noticed that the Jetsons were barely being used by the benchmark along with a bunch of other small issues I saw. So I intended to remake the benchmark training ResNet50 on CIFAR100. This would ensure that the time between epochs is still small enough to sit down and watch, while still being long enough to hear the Jetson fans spin.

![usage-graphs](https://github.com/user-attachments/assets/a70e8290-3195-46b1-b7db-f25fb116e9f1)
> K3s Dashboard Output in Grafana showing the utilization of the [Flyte Training Workflow](./jetson-flyte/train.py)

#### Logging Workflows

Further configuration like metrics and logging came when I was developing the [`train.py`](./jetson-flyte/train.py), subsequent workflow iterations were a nightmare to debug, and there's this very convenient `Logs` header in the task view that seemed to indicate that the Pod logs could be aggregated, however, the [documentation](https://docs.flyte.org/en/latest/user_guide/productionizing/configuring_logging_links_in_the_ui.html) for logging both on the workflow side and the deployment side are either not obvious enough, or completely absent. Flyte either can't, or doesn't aggregate kubernetes logs like you can with `kubectl`. Instead, it needs a log aggregator and it has this function where you can configure the deployment to use one like [Cloudwatch](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html).

If you're not using AWS though, you can use Loki for this, and flyte will generate a URL using some templating for each run. This means that we can link to Grafana using the Loki datasource and get the live output of the target task's logs from kubernetes.

### Open WebUI

[Open WebUI](https://github.com/open-webui/open-webui) is a playground for Large Language Models and is primarily used in conjunction with [Ollama](https://ollama.com/). I've deployed [Chroma](https://www.trychroma.com/) separately to manage the database separate of Open WebUI as I'm not very impressed with Open WebUI as a cloud native tool.

It was with Open WebUI where I originally found the ISCSI issue with the Nvidia Jetson node because I wanted to add Persistence to Ollama since I was testing out models and if the container failed with an OOM error I wouldn't have to re-download everything all over again.

Open WebUI is a great place to store data for RAG usage and test out new tools/functions in a sandbox environment. It has a lot of way to hook up tools like [Stable Diffusion](https://stabledifffusion.com/), Web Search, [Whisper](https://openai.com/index/whisper/), etc.

### Cert-Manager

[Cert-Manager](https://cert-manager.io/) is a tool to configure SSL for applications deployed on Kubernetes, and in general do certificate management for Cloud Native environments. I wanted to enable SSL because it enables certain features on the browser that could be worth exploring later, mainly to do with accessing audio devices to do text-to-speech.

Because my applications are only available on a private network I can't take advantage of a tool like [letsencrypt](https://letsencrypt.org/), so instead I have to configure self-signed certificates and then install them manually into my browser. During this process we don't actually have to create any certificates manually on linux, instead cert-manager will do that for us, and re-create/issue certificates if any changes are made or if a certificate would expire.

```mermaid
flowchart LR
    subgraph Cert-Manager[" "]
        direction TB
        A["Self-Signed<br/>Issuer"] -->|Creates| B["Root CA"]
        B -->|Signs| C["Wildcard<br/>Certificate"]
    end

    subgraph Traefik[" "]
        direction TB
        D["TLS Store"] -->|Configures| E["Traefik<br/>Proxy"]
        E -->|Routes| F["IngressRoutes"]
    end

    C -->|Stored in| D

    style A fill:#2d4f3c,stroke:#50a37d,color:#fff
    style B fill:#2d4f3c,stroke:#50a37d,color:#fff
    style C fill:#2d4f3c,stroke:#50a37d,color:#fff
    style D fill:#2b4465,stroke:#6c8ebf,color:#fff
    style E fill:#2b4465,stroke:#6c8ebf,color:#fff
    style F fill:#2b4465,stroke:#6c8ebf,color:#fff
    style Cert-Manager fill:none,stroke:none
    style Traefik fill:none,stroke:none
```

> A Flowchart showing the relationship between all [cert-manager objects](./manifests/k3s-ssl.yaml) and [traefik objects](./manifests/traefik-routes.yaml)

Along the way I learned that wildcards don't really work with the `Certificate` object, and instead I had to list out all of my DNS Names. Additionally, each `IngressRoute` needs to point to a `Middleware` in its namespace that redirects traffic to https to ensure SSL is actually used. If SSL would break for whatever reason, we still have http as an option just in case.

<!--

### [WikiJS](https://js.wiki/)

TODO: Nathan

-->

## Troubleshooting

This concerns topics that are more sporatic and random than anything under a topic above.

<details>

<summary>No Space Left on Device</summary>

Images are stored on `/run` in a temporary filesystem rather than on each nvme device. Because of this they have very little space due to memory constraints. If this becomes a bigger issue the directory will have to be moved to another volume, but in the meantime you can increase the size of the directory with `sudo mount -o remount,size=<Size>G /run`.

Before running this command, run a prune command just in case that solves the issue.

</details>

<details>

<summary>kube-prometheus-stack fails to sync in ArgoCD</summary>

If you are receiving an error like `one or more synchronization tasks completed unsuccessfully, reason: error when patching "/dev/shm/119925187": CustomResourceDefinition.apiextensions.k8s.io "prometheuses.monitoring.coreos.com" is invalid: metadata.annotations: Too long: must have at most 262144 bytes` this means that the annotations of the resource exceed Kubernetes' size limit, to resolve this simply enable server-side apply for all future syncing.

</details>
