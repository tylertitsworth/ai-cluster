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
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644 --disable servicelb --token <my-token> --node-ip 192.168.0.41 --disable-cloud-controller --disable local-storage
# Get kubeconfig from /etc/rancher/k3s/k3s.yaml, replace server field with K3S_URL
# Worker
curl -sfL https://get.k3s.io | K3S_URL=https://192.168.0.41:6443 K3S_TOKEN=<my-token> sh -
```

Afterwards, you get something like this:

```txt
$ kubectl get node -o wide
NAME             STATUS   ROLES                  AGE    VERSION        INTERNAL-IP    EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION      CONTAINER-RUNTIME
npu01.local      Ready    control-plane,master   55d    v1.30.6+k3s1   192.168.0.41   <none>        Ubuntu 22.04.5 LTS   5.10.160-rockchip   containerd://1.7.22-k3s1
npu02.local      Ready    control-plane          55d    v1.30.6+k3s1   192.168.0.44   <none>        Ubuntu 22.04.5 LTS   5.10.160-rockchip   containerd://1.7.22-k3s1
orinnx01.local   Ready    worker                 7d4h   v1.30.6+k3s1   192.168.0.15   <none>        Ubuntu 22.04.5 LTS   5.15.148-tegra      containerd://1.7.22-k3s1
orinnx02.local   Ready    worker                 7d5h   v1.30.6+k3s1   192.168.0.14   <none>        Ubuntu 22.04.5 LTS   5.15.148-tegra      containerd://1.7.22-k3s1
```

> The RK1's have the label `node-type=npu` and the Jetson `node-type=jetson`. This will be important later.

I also needed to [uninstall](https://docs.k3s.io/installation/uninstall) k3s-agent a couple of times to get the naming I wanted just right.

### Networking

I originally used [MetalLB](https://docs.turingpi.com/docs/turing-pi2-kubernetes-network-configuration#metallb) for a LoadBalancer IP pool so any app I wanted on the private network could just set `type: LoadBalancer` and get an address. That's gone now — see [Productionizing the Cluster](#productionizing-the-cluster) for why and what replaced it.

### Storage

[Longhorn](https://longhorn.io/) is the default StorageClass. I added it, removed it early on thinking ArgoCD-managed apps didn't need it, and quickly found out I was wrong — it's back as a proper [`Application`](./apps/longhorn-app.yaml) instead of whatever half-managed state it was in before.

The second storage backend is a Synology NAS, added through the [synology-csi](https://github.com/SynologyOpenSource/synology-csi) driver. It provisions NFS volumes for anything that needs to be shared across pods/nodes (like the `media-library` PVC the [servarr stack](#the-servarr-stack) uses) and iSCSI volumes for anything single-node that benefits from Btrfs-level snapshots (the etcd backup volumes covered below). Both protocols run off the same DSM instance, just different StorageClasses (`synology-csi-nfs-retain`/`-delete`, `synology-csi-iscsi-retain`/`-delete`).

### Tailscale

After setting up the cluster I started deploying apps on it, and then I wanted to invite some of my friends. Rather than exposing anything on a public network, I instead went with Tailscale's free plan to allow 2 of my friends to have access to some specific addresses so they can learn Kuberentes. The Tailscale Operator was added to act as an Ingress Controller for the cluster. Additionally, the operator acts as an API proxy, subnet router,and  control plane egress.

#### Peer Relay Operations (Dynamic WAN IP)

Peer relay for the `egress` ProxyGroup is configured with:

- `manifests/tailscale.yaml` for ProxyClass/ProxyGroup and NodePort exposure
- `manifests/tailscale-relay-updater.yaml` for automatic public IP detection and endpoint refresh

Apply/update:

```sh
kubectl apply -f manifests/tailscale.yaml
kubectl apply -f manifests/tailscale-relay-updater.yaml
```

The updater runs every 5 minutes and only changes relay configuration when WAN IP changes.

Validation checks:

```sh
kubectl get proxygroup egress -o jsonpath='{range .status.conditions[*]}{.type}={.status}{"\n"}{end}'
kubectl -n tailscale get cronjob tailscale-relay-updater
kubectl -n tailscale get jobs --sort-by=.metadata.creationTimestamp | tail -n 5
kubectl exec -n tailscale egress-0 -c tailscale -- tailscale debug peer-relay-servers
kubectl exec -n tailscale egress-1 -c tailscale -- tailscale debug peer-relay-servers
```

Manual recovery (if CronJob fails):

```sh
./scripts/update-tailscale-relay-ip.sh
# or force a specific public IP:
RELAY_IP=<public-ip> ./scripts/update-tailscale-relay-ip.sh
```

Rollback / disable automation:

```sh
kubectl -n tailscale delete cronjob tailscale-relay-updater
kubectl -n tailscale delete rolebinding tailscale-relay-updater
kubectl -n tailscale delete role tailscale-relay-updater
kubectl -n tailscale delete serviceaccount tailscale-relay-updater
```

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

## Productionizing the Cluster

For a long time this cluster's entire state lived in a single SQLite file on npu01. That's fine for a homelab until it isn't — one bad SD card and everything ArgoCD, Longhorn, and every app config knows about the cluster is gone. It also never actually matched what I originally set out to build: both RK1s were supposed to be control-plane. When I finally went looking, I found npu02 had been running as a plain `k3s agent` the whole time, just wearing a `control-plane` label that nothing was actually enforcing.

### From SQLite to Embedded etcd

k3s can run its own embedded etcd instead of SQLite, which is what real HA needs — multiple members voting on cluster state instead of one file on one disk. The migration went in two phases.

**Phase 1** converted npu01 alone to a single-member etcd datastore: add `cluster-init: true` to `/etc/rancher/k3s/config.yaml`, restart `k3s`. That's the whole migration — k3s moves the old `state.db` aside to `state.db.migrated` and starts writing to etcd on its own. I took a full local backup first (a plain tarball of `/var/lib/rancher/k3s/server/db`) since this touches the one thing every other piece of the cluster depends on.

**Phase 2** promoted npu02 and orinnx01 from agents to full etcd members, going straight from 1 to 3 rather than stopping at 2 — 2 members buys you nothing, since etcd quorum needs a majority and you still only survive 0 failures. Promoting an agent to a server turned out simpler than expected: stop `k3s-agent`, point a new `k3s server` unit at the same node using its existing `K3S_URL`/`K3S_TOKEN`, and it joins as a voting member with no drain or re-add needed. The first attempt failed immediately with `critical configuration mismatched: disable-cloud-controller` — k3s enforces that certain flags (`--disable-cloud-controller`, `--disable local-storage`, `--disable traefik`, etc.) match exactly across every server member, and my first pass at the new unit was missing them. Copying npu01's exact flag set fixed it on the second try.

Both migrations landed with zero pods evicted and the cluster's container-restart count essentially unchanged before/after, which was the actual bar I was trying to clear, not just "it came back up."

### Losing MetalLB, Gaining kube-vip

Once I actually looked at what MetalLB was doing for me, the answer was "not much" — every service that had a LoadBalancer IP from it also already had independent access through the Tailscale Operator (as an `Ingress`, or the `tailscale.com/expose` annotation for non-HTTP things like Terraria). Tailscale's proxies talk to a Service over its `ClusterIP` regardless of the Service's own `type`, so dropping `LoadBalancer` for `ClusterIP` on those services changed nothing about how they were actually reached.

That left MetalLB doing exactly one useful thing: giving the API server a stable address that doesn't depend on which specific control-plane node happens to answer. [kube-vip](https://kube-vip.io/) does that one job directly, in **control-plane-only mode** (no `--services`, so it never touches the LoadBalancer role MetalLB used to have) — an ARP-advertised, leader-elected VIP at `10.0.0.253:6443` running as a DaemonSet across the 3 etcd nodes. Getting there needed each server's TLS cert extended with the VIP as a SAN (`tls-san` in `config.yaml`) before kube-vip could actually serve traffic for it, one node at a time so the other two kept quorum the whole time.

With that in place, `K3S_URL` on every node that isn't npu01, npu02, or orinnx01 got repointed from a specific node's IP to the VIP — the whole reason for doing this in the first place. Before, if npu01 was down, no other node could ever rejoin the cluster; now it doesn't matter which member is up.

### Backing Up etcd, Independently, Per Node

k3s already takes local etcd snapshots on its own (00:00/12:00, keeping the last 5) — that part needed no work at all. The actual gap was that those snapshots sit on the same disk as the live data they're backing up. Lose that node's disk and you lose both copies together.

Since all 3 etcd members hold identical Raft state, any single member's snapshot is already a complete backup of the whole cluster — so instead of one off-node copy job, each node runs its own, independently: a `CronJob` per node, pinned via `nodeName`, that rsyncs the local snapshot directory onto a small per-node iSCSI volume on the NAS, then takes a CSI `VolumeSnapshot` of that volume for a proper Btrfs-level point-in-time copy, pruning both the files and the snapshot objects past 7 days. Separate volumes per node instead of one shared one, since iSCSI is single-attach and I didn't want 3 nodes' CronJobs fighting over the same PV if their schedules ever overlapped.

Building the actual container images for this turned into its own small tour of "which kubectl image actually works": `bitnami/kubectl` no longer publishes any tags at all, `rancher/kubectl` has no shell in it whatsoever (`exec: sh: executable file not found in $PATH`), and [`alpine/k8s`](https://github.com/alpine-docker/k8s) was the one that actually had both a shell and `kubectl`. Then the retention-pruning script broke on the very last piece — BusyBox's `date` doesn't understand GNU's `-d "7 days ago"` relative-date syntax, so that had to become plain arithmetic (`$(date +%s) - 7*86400`) instead.

**What's not done yet**: the actual restore procedure (`k3s server --cluster-reset --cluster-reset-restore-path=<snapshot>`) hasn't been tested end-to-end. It's destructive enough that I'm not willing to run it against a live cluster just to prove it works, and I don't have a spare node to rehearse it on. Worth knowing before you actually need it.

## Applications

Now that all of the cluster resources are abstracted, I can get rid of the need to SSH and start deploying applications on Kubernetes.

### ArgoCD

One of the first orders of business is to replace the existing longhorn configuration and add it as [ArgoCD](https://argo-cd.readthedocs.io/en/stable/) [Applications](https://argo-cd.readthedocs.io/en/stable/core_concepts/). ArgoCD is the GitOps application of choice, we can modify and maintain complex deployments from its UI and automatically update applications as new chart versions release.

![ArgoCD Dashboard](https://github.com/user-attachments/assets/20945b0c-00af-4e87-b83a-c391df75a6cd)


> The ArgoCD Dashboard

Each application's manifest lives under [apps/](./apps/), grouped into one subdirectory per `stack` label (`ai/`, `games/`, `gpu/`, `home/`, `monitoring/`, `platform/`, `servarr/`); its values file, if it has one, lives in that stack's `values/` subdirectory named after the app. Adding a new application is just about finding a helm chart and customizing to fit the cluster before deploying it using ArgoCD's UI. Once we've completed the deployment and like our configuration, we can modify the application manifest to use the file in this repo as a values file for the application:

```yaml
# from source: to
sources:
  - repoURL: ...
    path: ...
    targetRevision: main
    helm:
      valueFiles:
        - $values/apps/<stack>/values/<application-name>.yaml
  - repoURL: https://github.com/tylertitsworth/ai-cluster
    targetRevision: main
    ref: values
```

Then we can enable automatic updates, self healing, and pruning.

Apply all Argo CD `Application` and `ApplicationSet` manifests after pushing to `main`:

```sh
rg -l '^kind:\s*(Application|ApplicationSet)$' apps --glob '*.yaml' | xargs -r -n1 kubectl apply -f
```

### Monitoring

Metrics and scraped by [Prometheus](https://prometheus.io/) and then Aggregated by [Grafana](https://grafana.com/). There are a few ways to deploy these applications so I went with the [kube-prom-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack). Namely because I wanted both tools to work together out of the box, and I wanted [Prometheus Operator](https://prometheus-operator.dev/) and [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) as well.

Afterwards I wrote some dashboards:

![K3s Dashboard](https://github.com/user-attachments/assets/0b1ac428-6650-4c96-b646-49ea1f4ed127)


> K3s Cluster [Dashboard](./grafana/k3s_dashboard.json)

![Jetson Dashboard](https://github.com/user-attachments/assets/b8b9978f-0acb-440f-a573-404d32c72ee2)

> Nvidia Jetson [Dashboard](./grafana/jetson_dashboard.json) using the [jetson exporter](./jetson-exporter/README.md)

Because of how Prometheus is deployed, it's managed by a [`Prometheus`](https://github.com/prometheus-operator/prometheus-operator?tab=readme-ov-file#customresourcedefinitions) CRD. A [`ServiceMonitor`](https://prometheus-operator.dev/docs/developer/getting-started/#using-servicemonitors) has to contain the label `prometheus: monitoring-kube-prometheus-prometheus` in order to be picked up by prometheus and exist on the same namespace that prometheus was deployed on.

#### Logs

Logs are aggregated by [Loki](https://grafana.com/docs/loki/latest/) with the [loki-stack](https://github.com/grafana/helm-charts/tree/main/charts/loki-stack) chart. The stack deploys [Promtail](https://grafana.com/docs/loki/latest/send-data/promtail/). Promtail is the metric aggregator for Loki, which then formats and forwards those logs to Grafana for viewing. To add Loki as a datasource in Grafana, simply add a new Loki datasource and it give it the the connection url `http://loki:3100`.

Grafana's Loki datasource makes it easy to pull up logs for anything running on the cluster without reaching for `kubectl` and `k9s` every time.

### Other Applications

A few smaller things that don't need their own full section:

- **[Mealie](https://mealie.io/)** — a recipe manager with its own Postgres instance, mostly so household recipes don't live in a dozen browser tabs.
- **[KubeRay](https://github.com/ray-project/kuberay)** — the Ray operator + API server, for running Ray clusters on top of k3s instead of standing up dedicated hardware for it.
- **[kubernetes-mcp-server](https://github.com/containers/kubernetes-mcp-server)** — exposes an MCP server over Tailscale so an LLM client can query the cluster directly instead of me pasting `kubectl` output into a chat window.
- **[restart-operator](https://archsyscall.github.io/restart-operator)** — a small third-party operator (amd64-only, so it only runs on framework-desktop) for scheduling pod restarts on a cron.
- **[Foundry VTT](https://foundryvtt.com/)** — a virtual tabletop for running D&D-style games, deployed as an umbrella chart pulling in the upstream `foundry-vtt` chart plus a Tailscale ingress template.
- **[Pi-hole](https://pi-hole.net/)** — network-wide ad blocking.
- **[Terraria](https://terraria.org/)** — a dedicated game server, exposed directly over Tailscale via the `tailscale.com/expose` Service annotation instead of an `Ingress`, since it isn't HTTP.

### The servarr Stack

The bulk of what actually runs on this cluster day to day is a media-automation stack, commonly known by the loose "servarr" naming convention that describes most of it: [Sonarr](https://sonarr.tv/) and [Radarr](https://radarr.video/) for TV/movie management, [Prowlarr](https://prowlarr.com/) as the shared indexer manager for both, [Bazarr](https://www.bazarr.media/) for subtitles, [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) as a Cloudflare-bypass proxy some indexers need, [qBittorrent](https://www.qbittorrentofficial.com/) behind a VPN sidecar, [Plex](https://www.plex.tv/) as the actual media server, [Tautulli](https://tautulli.com/) for Plex stats, [Overseerr](https://overseerr.dev/) (now running the community "Seerr" fork, `ghcr.io/seerr-team/seerr`) for request management, [Maintainerr](https://github.com/jorenn92/Maintainerr) and [Profilarr](https://github.com/Dictionarry-Hub/profilarr) for library/quality-profile housekeeping, and [Kavita](https://www.kavitareader.com/)/[Bookshelf](https://www.audiobookshelf.org/) for comics/manga and audiobooks. [FileFlows](https://fileflows.com/) handles any transcoding/processing that needs to happen outside the individual apps. Every one of these is its own Helm chart under `charts/servarr/*`, its own `ArgoCD` `Application`, sharing one `servarr` namespace and a `stack: servarr` label.

It didn't arrive all at once, and not everything I tried stuck. [Kapowarr](https://github.com/Casvt/Kapowarr) and [Kaizoku](https://github.com/oae/kaizoku) (comic and manga tracking, respectively) both went in and came back out again — neither was worth the maintenance for how little I actually used them.

A few things grew up around the stack once it was clear it wasn't going anywhere:

- **ArgoCD Image Updater** (`manifests/image-updater-servarr.yaml`) tracks the latest image digest for every servarr app so they stay current without me manually bumping tags.
- **An SMB share** (`manifests/samba-shares.yaml`) exposes the shared media library over the network for anything that isn't running in the cluster.
- **A `RestartSchedule` CRD** (`charts/restart-operator-crds/`, using the [restart-operator](#other-applications) above) handles the handful of apps that just need a periodic kick — qBittorrent-VPN every 3 hours to keep its VPN connection healthy, Plex weekly on Sunday mornings.

And since Plex needed real hardware for transcoding, the cluster grew a fifth node for it: `framework-desktop`, an amd64 box with an AMD GPU, running the [ROCm device plugin](https://rocm.github.io/k8s-device-plugin) so Plex (and qBittorrent-VPN, for networking reasons) can actually use it. It's the only non-ARM node in the cluster.

### Open WebUI

[Open WebUI](https://github.com/open-webui/open-webui) is a playground for Large Language Models and is primarily used in conjunction with [Ollama](https://ollama.com/).

It was with Open WebUI where I originally found the ISCSI issue with the Nvidia Jetson node because I wanted to add Persistence to Ollama since I was testing out models and if the container failed with an OOM error I wouldn't have to re-download everything all over again.

Open WebUI is a great place to store data for RAG usage and test out new tools/functions in a sandbox environment. It has a lot of way to hook up tools like [Stable Diffusion](https://stabledifffusion.com/), Web Search, [Whisper](https://openai.com/index/whisper/), etc.

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
