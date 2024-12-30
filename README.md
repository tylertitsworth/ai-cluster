# [Turing Pi](https://turingpi.com/) 2.5.2 Cluster

This is a repository for all of the information related to my journey with the Turing Pi line of homelab products. I'm an MLOps Engineer by trade so I plan to use this as a Kubernetes cluster for Edge AI Inference and other weird experiments on arm. This build took about 3 weeks to ship, and another 2 weeks to get completely flashed and assembled, with a good portion of those 2 weeks spent on just one step (more on that below).

![Finished Build](https://github.com/user-attachments/assets/a314233f-29f0-43ab-90db-0c06ddc6abf3)

> Finished Turing Pi sitting on the shelf next to my Computer, where it runs 24/7

This document can be divided into two sections, the front half being the spark notes of the installation and setup process for everything, followed by the application side where I go into what I've actually done with the nodes.

## Assembly

Upon opening and inspecting all of the parts I didn't find any issues. I quickly started adding heatsinks to modules and assmebling with the rough approximation found in the image below:

![Plan](https://github.com/user-attachments/assets/78dcc608-8914-43de-851d-dc4f5788fe2f)

Jetsons get more storage because I knew that they would require an entire suite of drivers and software just to run the GPU, and the flashing process might require some extra scratch space.

Once I started adding the modules to the board, I noticed that a lot of pressure had to be applied to the node slots to actually get something to click in, similar to a RAM stick on a cheap motherboard. Similarly, with the node storage M.2 slots on the back of the board, the process of swapping a node for flashing became very tedious. I'm not sure how Turing could've worked around this given that this is a space optimization.

My 2nd RK1 install had a slight hiccup with the fan cable getting in the way of the fan, meaning I had to play around with how it routed in order to not cause any noise/damage to the cable. In my photo above, you can see how it's routed weirdly to the opposite side of the connector. I'm not sure how I messed that up, but I couldn't get it to route nicely.

### Parts

I live in Oregon, which doesn't have sales tax, so considering that, I spent about ~$1300 on all of these parts, with a further upgrade to the new Jetson NX Super for an additional $250 in 2025. Rounding out this cluster to ~$1600 for 4 computers in a form factor that's smaller than ITX.

1x [Turing Pi 2.5.2](https://turingpi.com/product/turing-pi-2-5/)

> With [24pin PSU](https://turingpi.com/product/pico-psu/)

2x [Turing RK1](https://turingpi.com/product/turing-rk1/?attribute_ram=8+GB) Compute Modules

> With [Heatsink + Fan](https://turingpi.com/product/rk1-heatsink/)

1x Nvidia Jetson Orin NX 8GB

> Via Arrow, Waveshare Compatible Heatsink + Fan sold separately

2x Teamgroup MP33 256GB Gen3x4 M.2 SSDs

> For the 2 RK1s

1x Crucial P3 Plus 1TB Gen4x4 M.2 SSD

> For the Jetson Orin NX

1x Intel 7260.HMW Dual Band Wireless AC Network Adapter 802.11 b/a/g/n/ac (Optional)

> This card may or may not work with the board, I may have to return it

1x 128GB Micro SD Card (Optional)

> Just in case

1x 12V 12A Power Supply

> Vendor Neural, the one I grabbed goes up to 144W and was slightly cheaper than what is on Turing Pi's site

1x PC Open Frame Test Bench with Acrylic Stand

> This is a placeholder until the [official case](https://turingpi.com/product/turing-mini-itx-case/) arrives

### BMC

Powering on the board gave a satisfying light-up, and before long, I was able to access the BMC at `turingpi.local`. With the default credentials being `root/turing`, I had a sigh of relief that everything was working as intended and I could power on a node without issue.

I quickly found that switching to an SSH connection was much more convenient because the BMC doesn't actually refresh the state of the nodes on the board. All it does is send commands via an API. This might seem like a small thing, but what it means in reality is that the web UI doesn't actually tell you whether your nodes are on/off. It also lacks a [UART](https://docs.turingpi.com/docs/tpi-uart) log output, which is necessary for any kind of debugging.

## Flashing & OS Setup

By default, nothing is flashed to these compute modules, and so I need to use the BMC to flash these boards and install Ubuntu onto them. Furthermore, my router doesn't really recognize these devices so I just want to put a quick note in here that I found their IP by using [UART](https://docs.turingpi.com/docs/tpi-uart) log outputs with a command like `tpi uart -n 1 set --cmd 'ip a'` and `tpi uart -n 1 get`.

### RK1

I went with the [BMC UI method](https://docs.turingpi.com/docs/turing-rk1-flashing-os) for flashing both RK1s, I used Ubuntu 22.04 LTS server since I won't have any use for a GUI. The process was reletively uneventful. I was able to move my eMMC OS Installation to my NVMe drive using `ubuntu-rockchip-install`.

### Nvidia Orin NX

Flashing the Orin NX took about a week and a half or so. I wrote down my experience with the Jetson in a [separate document](./JETSON.md).

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
NAME             STATUS   ROLES                  AGE   VERSION        INTERNAL-IP    EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION      CONTAINER-RUNTIME
npu01.local      Ready    control-plane,master   37d   v1.30.6+k3s1   192.168.1.41   <none>        Ubuntu 22.04.5 LTS   5.10.160-rockchip   containerd://1.7.22-k3s1
npu02.local      Ready    control-plane          37d   v1.30.6+k3s1   192.168.1.44   <none>        Ubuntu 22.04.5 LTS   5.10.160-rockchip   containerd://1.7.22-k3s1
orinnx01.local   Ready    worker                 30d   v1.30.6+k3s1   192.168.1.14   <none>        Ubuntu 22.04.5 LTS   5.15.148-tegra      containerd://1.7.22-k3s1
```

> The RK1's have the label `node-type=npu` and the Jetson `node-type=jetson`. This will be important later.

I also needed to [uninstall](https://docs.k3s.io/installation/uninstall) k3s-agent a couple of times to get the naming I wanted just right.

### Networking

After following the basic instructions to install [MetalLB](https://docs.turingpi.com/docs/turing-pi2-kubernetes-network-configuration#metallb) I added an address pool for `192.168.1.80-192.168.1.90` and then reserved all of those spaces on my router along with the turing nodes.

Now whenever I have an application that I want to make available on the private network, I can set our service type to `LoadBalancer` and it'll automatically get an IP from that range. Additionally, storage is handled by Longhorn, which I intially added and then removed later in favor of managing with ArgoCD. The same is true for Traefik.

### Tailscale

After setting up the cluster I started deploying apps on it, and then I wanted to invite some of my friends. Rather than exposing anything on a public network, I instead went with Tailscale's free plan to allow 2 of my friends to have access to some specific addresses so they can learn Kuberentes.

Additionally, I installed a [subnet router](https://tailscale.com/kb/1185/kubernetes#subnet-router) so that way all of the cluster addresses could be reached on any of our machines. This little application saves the pain of having to use `kubectl port-forward`.

### Nvidia Device Plugin

There is some additional setup required to make sure that the GPU is accessible. The Jetson uses the same device plugin daemonset that any other card uses, and the [documentation](https://docs.turingpi.com/docs/turing-pi2-kubernetes-cluster-nvidia-jetson) for this setup has a lot of unecessary steps. All of the networking stuff was not really required. Like I mention in the Nvidia Flashing & OS Setup document, there is a lot of out of date information surrounding the Orin NX, but once `./deviceQuery` runs without fail in a pod I officially had compute.

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

One of the first orders of business is to replace the existing longhorn and traefik configurations and add them as [ArgoCD](https://argo-cd.readthedocs.io/en/stable/) [Applications](https://argo-cd.readthedocs.io/en/stable/core_concepts/). ArgoCD is our GitOps application of choice, we can modify and maintain complex deployments from its UI and automatically update applications as new chart versions release.

![ArgoCD Dashboard](https://github.com/user-attachments/assets/865c10a4-f6cb-4ba0-81e2-15bd3c68b5b6)

> The ArgoCD Dashboard

Each values file associated with each application is stored in the [agrocd](./manifests/argocd/README.md) folder. Adding a new application is just about finding a helm chart and customizing to fit the cluster before deploying it using ArgoCD's UI.

### Prometheus & Grafana

Metrics and scraped by [Prometheus](https://prometheus.io/) and then Aggregated by [Grafana](https://grafana.com/). There are a few ways to deploy these applications so I went with the [kube-prom-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack). Namely because I wanted both tools to work together out of the box, and I wanted [Prometheus Operator](https://prometheus-operator.dev/) and [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) as well.

Afterwards I wrote some dashboards:

![K3s Dashboard](https://github.com/user-attachments/assets/7ce9594b-d68d-4cd1-8c14-9d4503cbcdd8)

> K3s Cluster [Dashboard](./grafana/k3s_dashboard.json)

![Jetson Dashboard](https://github.com/user-attachments/assets/b8b9978f-0acb-440f-a573-404d32c72ee2)

> Nvidia Jetson [Dashboard](./grafana/jetson_dashboard.json) using the [jetson exporter](./jetson-exporter/README.md)

Because of how Prometheus is deployed, it's managed by a [`Prometheus`](https://github.com/prometheus-operator/prometheus-operator?tab=readme-ov-file#customresourcedefinitions) CRD. A [`ServiceMonitor`](https://prometheus-operator.dev/docs/developer/getting-started/#using-servicemonitors) has to contain the label `prometheus: monitoring-kube-prometheus-prometheus` in order to be picked up by prometheus and exist on the same namespace that prometheus was deployed on.

### Flyte

[Flyte](https://github.com/flyteorg/flyte) is an ML Orchestration application that I'm trialing at my workplace. It's intended to replace tools like [Argo Workflows](https://argoproj.github.io/workflows/) that aren't very ML-centric and I'm hoping to get some mileage out of it on this cluster. Any kind of workflow that requires multiple steps in different containers can be done in Flyte using Python and `flytectl`.

### Open WebUI

[Open WebUI](https://github.com/open-webui/open-webui) is a playground for Large Language Models and is primarily used in conjunction with [Ollama](https://ollama.com/). I've deployed [Chroma](https://www.trychroma.com/) separately to manage the database separate of Open WebUI as I'm not very impressed with Open WebUI as a cloud native tool.

It was with Open WebUI where I originally found the ISCSI issue with the Nvidia Jetson node because I wanted to add Persistence to Ollama since I was testing out models and if the container failed with an OOM error I wouldn't have to re-download everything all over again.

Open WebUI is a great place to store data for RAG usage and test out new tools/functions in a sandbox environment. It has a lot of way to hook up tools like [Stable Diffusion](https://stabledifffusion.com/), Web Search, [Whisper](https://openai.com/index/whisper/), etc.

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
