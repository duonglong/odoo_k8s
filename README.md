# Odoo on Kubernetes

Deploy Odoo 19.0 with PostgreSQL on Kubernetes.

## Project Structure

```
odoo_k8s/
├── docker/                  # Docker image files
│   ├── Dockerfile
│   ├── odoo.conf
│   ├── entrypoint.sh
│   └── wait-for-it.sh
├── addons/                  # Custom Odoo addons
├── k8s/                     # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── ingress.yaml
│   ├── postgres/
│   │   ├── statefulset.yaml
│   │   └── service.yaml
│   └── odoo/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── pvc.yaml
├── docker-compose.yaml      # Local dev
├── Makefile                 # Shortcuts
└── README.md
```

## Option A: Quick Start — Local Dev (Docker Compose)

The fastest way to get Odoo running locally. No Kubernetes needed.

```bash
cd ~/PycharmProjects/odoo_k8s

# Start Odoo + PostgreSQL
docker compose up -d

# Open http://localhost:8069 in your browser
# Odoo's database manager will appear

# View logs
docker compose logs -f odoo

# Stop
docker compose down
```

Or use the Makefile shortcuts: `make up`, `make logs`, `make down`.

---

## Option B: Kubernetes Deployment

### Step 1 — Install kubectl

```bash
# Ubuntu/Debian
sudo snap install kubectl --classic

# Verify
kubectl version --client
```

### Step 2 — Choose Your Cluster Setup

Pick one of the three options below based on your goals:

| Option | Setup Time | Realism | Best For |
|--------|-----------|---------|----------|
| **B1: Minikube (Simple)** | 5 min | ~70% | Quick testing, learning K8s basics |
| **B2: Minikube + VirtualBox** | 10 min | ~85% | Production simulation with VM isolation |
| **B3: kubeadm (Manual)** | 1-2 hours | ~95% | Learning K8s internals, real production setup |

---

<details>
<summary><b>B1: Minikube — Simple (Docker driver)</b></summary>

#### Install

```bash
sudo snap install minikube
```

#### Start

```bash
minikube start --memory=4096 --cpus=2
```

#### Enable Ingress

```bash
minikube addons enable ingress
```

</details>

---

<details>
<summary><b>B2: Minikube + VirtualBox — Multi-Node (Recommended for production simulation)</b></summary>

Runs multiple K8s nodes as separate VirtualBox VMs. Closer to a real production cluster.

#### Prerequisites

```bash
# Install VirtualBox
sudo apt update
sudo apt install -y virtualbox virtualbox-dkms

# Install minikube
sudo snap install minikube

# Verify hardware virtualization is enabled
grep -E '(vmx|svm)' /proc/cpuinfo | head -1
# If output is empty → enable VT-x/AMD-V in BIOS
```

#### Start Multi-Node Cluster

```bash
minikube start \
  --driver=virtualbox \
  --nodes=3 \
  --memory=4096 \
  --cpus=2 \
  --disk-size=30g \
  --kubernetes-version=v1.29.0
```

This creates:
- **Node 1** — Control plane + worker
- **Node 2** — Worker
- **Node 3** — Worker

#### Enable Ingress

```bash
minikube addons enable ingress
```

#### Verify Nodes

```bash
kubectl get nodes
# NAME           STATUS   ROLES           AGE   VERSION
# minikube       Ready    control-plane   1m    v1.29.0
# minikube-m02   Ready    <none>          1m    v1.29.0
# minikube-m03   Ready    <none>          1m    v1.29.0
```

</details>

---

<details>
<summary><b>B3: kubeadm — Manual Setup (Host as Control Plane + VM Workers)</b></summary>

Your laptop runs the **control plane**, VirtualBox VMs run as **worker nodes**. This is how real production clusters are built.

#### Architecture

```
┌────────────────────────────────────────────────┐
│ Your Laptop (Host) — Control Plane             │
│  • kube-apiserver, etcd, scheduler             │
│  • kubectl configured here                     │
│                                                │
│   ┌──────────────────┐  ┌──────────────────┐   │
│   │ VirtualBox VM 1  │  │ VirtualBox VM 2  │   │
│   │ Worker Node      │  │ Worker Node      │   │
│   │ 192.168.56.101   │  │ 192.168.56.102   │   │
│   │ 2 CPU, 4GB RAM   │  │ 2 CPU, 4GB RAM   │   │
│   └──────────────────┘  └──────────────────┘   │
└────────────────────────────────────────────────┘
```

#### 3.1 — Create VirtualBox VMs

1. Download [Ubuntu Server 22.04 ISO](https://ubuntu.com/download/server)
2. Create 2 VMs in VirtualBox:
   - **CPU**: 2 cores, **RAM**: 4096 MB, **Disk**: 20 GB
   - **Network Adapter 1**: NAT (for internet)
   - **Network Adapter 2**: Host-Only Adapter (`vboxnet0`, for cluster communication)
3. Install Ubuntu Server on each VM
4. Assign static IPs on the Host-Only interface:

```bash
# On VM 1 — edit /etc/netplan/01-host-only.yaml
network:
  version: 2
  ethernets:
    enp0s8:
      addresses: [192.168.56.101/24]

# On VM 2
network:
  version: 2
  ethernets:
    enp0s8:
      addresses: [192.168.56.102/24]

# Apply
sudo netplan apply
```

#### 3.2 — Install Container Runtime (ALL machines: host + VMs)

```bash
# Load required kernel modules
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
sudo modprobe overlay
sudo modprobe br_netfilter

# Sysctl settings
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sudo sysctl --system

# Install containerd
sudo apt update
sudo apt install -y containerd
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml
# Enable SystemdCgroup
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd

# Disable swap
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab
```

#### 3.3 — Install kubeadm, kubelet, kubectl (ALL machines)

```bash
sudo apt install -y apt-transport-https ca-certificates curl gpg

curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | \
  sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' | \
  sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt update
sudo apt install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```

#### 3.4 — Initialize Control Plane (on your laptop only)

```bash
sudo kubeadm init \
  --apiserver-advertise-address=192.168.56.1 \
  --pod-network-cidr=10.244.0.0/16

# Set up kubectl for your user
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Install Flannel CNI (pod network)
# IMPORTANT: must specify --iface-regex so Flannel uses the Host-Only adapter,
# not the NAT adapter. Host uses 'vboxnet0', VMs use 'enp0s8'.
curl -o /tmp/flannel.yaml https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
sed -i '/- --kube-subnet-mgr/a\        - --iface-regex=vboxnet0|enp0s8' /tmp/flannel.yaml
kubectl apply -f /tmp/flannel.yaml
```

#### 3.5 — Join Worker Nodes (on each VM)

The `kubeadm init` output will print a join command. Run it on each VM:

```bash
# On VM 1 and VM 2
sudo kubeadm join 192.168.56.1:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash>
```

If you lost the token, regenerate it on the host:
```bash
kubeadm token create --print-join-command
```

#### 3.5.1 — Fix Kubelet Node IP (VirtualBox only — IMPORTANT!)

> ⚠️ **VirtualBox VMs have two network adapters**: NAT (`10.0.2.15`) and Host-Only (`192.168.56.x`). By default, kubelet registers with the NAT IP, which is **unreachable from the host**. This causes `i/o timeout` errors when the control plane tries to talk to pods on the workers.

On **each worker VM**, configure kubelet to use the Host-Only IP:

```bash
# On VM 1 (worker-1)
echo 'KUBELET_EXTRA_ARGS="--node-ip=192.168.56.101"' | sudo tee /etc/default/kubelet
sudo systemctl restart kubelet

# On VM 2 (worker-2)
echo 'KUBELET_EXTRA_ARGS="--node-ip=192.168.56.102"' | sudo tee /etc/default/kubelet
sudo systemctl restart kubelet
```

#### 3.6 — Verify Cluster

```bash
# On your laptop — check nodes show the 192.168.56.x IPs (not 10.0.2.15)
kubectl get nodes -o wide
# NAME        STATUS   ROLES           AGE   VERSION   INTERNAL-IP
# laptop      Ready    control-plane   2m    v1.29.0   192.168.56.1
# worker-1    Ready    <none>          1m    v1.29.0   192.168.56.101
# worker-2    Ready    <none>          1m    v1.29.0   192.168.56.102
```

#### 3.7 — Install Nginx Ingress Controller

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/baremetal/deploy.yaml
```

#### 3.8 — Install Storage Provisioner

kubeadm clusters don't include a storage provisioner by default, so PersistentVolumeClaims will stay `Pending` without one.

```bash
# Install local-path-provisioner (by Rancher)
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml

# Set it as the default StorageClass
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Verify
kubectl get storageclass
# NAME                   PROVISIONER             AGE
# local-path (default)   rancher.io/local-path   10s
```

</details>

---

### Step 3 — Deploy Odoo

Run these commands **in order** from the project root (same for all cluster options):

```bash
cd ~/PycharmProjects/odoo_k8s

# 1. Create the namespace
kubectl apply -f k8s/namespace.yaml

# 2. Create secrets & config
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml

# 3. Deploy PostgreSQL and wait for it
kubectl apply -f k8s/postgres/
kubectl -n odoo rollout status statefulset/postgres --timeout=120s

# 4. Deploy Odoo and wait for it
kubectl apply -f k8s/odoo/
kubectl -n odoo rollout status deployment/odoo --timeout=180s

# 5. Create Ingress
kubectl apply -f k8s/ingress.yaml
```

Or simply run **`make deploy`** — it does all of the above in order.

### Step 4 — Access Odoo

**Port-forward** (works with any setup):
```bash
kubectl -n odoo port-forward svc/odoo 8069:8069 8072:8072
# → http://localhost:8069
```

**Via Ingress** (minikube):
```bash
minikube ip
# Add to /etc/hosts: <IP>  odoo.local
# → http://odoo.local
```

**Via Ingress** (kubeadm):
```bash
# → http://odoo.local (add 192.168.56.1 odoo.local to /etc/hosts)
```

### Step 5 — Verify & Manage

```bash
make status       # Show all pods, services, PVCs
make k8s-logs     # Tail Odoo logs
make k8s-shell    # Shell into Odoo container
```

### Tear Down

```bash
make undeploy                    # Remove (preserves data volumes)
kubectl delete namespace odoo    # Full cleanup

# Minikube
minikube stop                    # Stop cluster
minikube delete                  # Delete cluster

# kubeadm (on each worker VM)
sudo kubeadm reset
# kubeadm (on host)
sudo kubeadm reset
```

### All Makefile Commands

```bash
make help        # Show all available commands
make build       # Build custom Docker image
make push        # Push image to registry
make up / down   # Docker Compose lifecycle
make deploy      # Deploy to K8s
make undeploy    # Remove from K8s
make status      # Show K8s resource status
make k8s-logs    # Tail Odoo pod logs
make k8s-shell   # Shell into Odoo pod
make psql        # Connect to PostgreSQL (psql)
make odoo-shell  # Open Odoo interactive shell
make port-forward # Port-forward Odoo locally
```

## Rolling Out Changes

### New Addons (code only, no new Python deps)

```bash
# 1. Update addons/ directory with your module
# 2. Restart pods to pick up new code
kubectl -n odoo rollout restart deployment/odoo
kubectl -n odoo rollout status deployment/odoo
```

### New Python Dependencies

```bash
# 1. Update addons/requirements.txt
# 2. Rebuild & push image
make build
make push

# 3. Restart pods (pulls new image due to imagePullPolicy: Always)
kubectl -n odoo rollout restart deployment/odoo
```

### Odoo Config Changes (odoo.conf)

```bash
# 1. Edit k8s/configmap.yaml
# 2. Apply the new config
kubectl apply -f k8s/configmap.yaml

# 3. Restart pods to pick up the new config
kubectl -n odoo rollout restart deployment/odoo
```

### K8s Manifest Changes (resources, replicas, etc.)

```bash
# 1. Edit the YAML file (e.g. k8s/odoo/deployment.yaml)
# 2. Apply — K8s will do a rolling update automatically
kubectl apply -f k8s/odoo/deployment.yaml
kubectl -n odoo rollout status deployment/odoo
```

### Rollback (if something goes wrong)

```bash
# Undo the last deployment change
kubectl -n odoo rollout undo deployment/odoo

# Check rollout history
kubectl -n odoo rollout history deployment/odoo
```

## Configuration

### Odoo Config

Edit `k8s/configmap.yaml` to change `odoo.conf` settings (workers, limits, etc.).

### Secrets

Update `k8s/secrets.yaml` with your credentials (base64 encoded):

```bash
echo -n 'your-password' | base64
```

> ⚠️ For production, use [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) or [HashiCorp Vault](https://www.vaultproject.io/).

### Custom Addons

Place custom addon modules in the `addons/` directory. They are mounted at `/mnt/extra-addons` inside the container.

### TLS / HTTPS

Uncomment the TLS section in `k8s/ingress.yaml` and configure [cert-manager](https://cert-manager.io/) for automatic Let's Encrypt certificates.

### Autoscaling (HPA)

Odoo automatically scales from **1 to 5 pods** based on CPU and memory usage using a Kubernetes [Horizontal Pod Autoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/).

| Metric | Scale-up threshold | Scale-down threshold |
|--------|-------------------|---------------------|
| CPU | > 70% average | < 70% (with 5min cooldown) |
| Memory | > 80% average | < 80% (with 5min cooldown) |

**Prerequisites** — Install Metrics Server (HPA reads metrics from it):

```bash
# For kubeadm / kind
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# For kubeadm with self-signed certs, you may need:
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'

# For minikube
minikube addons enable metrics-server
```

**Apply HPA**:
```bash
kubectl apply -f k8s/odoo/hpa.yaml
```

**Monitor scaling**:
```bash
# Watch HPA status
kubectl -n odoo get hpa -w

# Current resource usage
kubectl -n odoo top pods
```

**Scaling behavior**:
- **Scale up**: Adds up to 2 pods per minute when thresholds exceeded
- **Scale down**: Removes 1 pod every 2 minutes, with 5-minute stabilization to prevent flapping

> ⚠️ **Note**: `workers = 0` (gevent mode) is required in `configmap.yaml` for multi-replica scaling. Multi-process mode (`workers > 0`) should only be used with a single replica.

### Monitoring (Prometheus + Grafana + Loki)

Full production monitoring stack with metrics, dashboards, logs, and alerts.

```
┌─────────────────────────────────────────────────────┐
│                 Grafana (UI)                         │
│   Dashboards · Alerts · Logs   http://localhost:3000 │
└─────────┬──────────────────┬────────────────────────┘
          │                  │
   ┌──────▼──────┐    ┌─────▼─────┐
   │ Prometheus  │    │   Loki    │
   │  (metrics)  │    │  (logs)   │
   └──┬──────┬───┘    └─────┬─────┘
      │      │              │
   ┌──▼──┐ ┌─▼───────────┐ ┌▼────────┐
   │Node │ │kube-state   │ │Promtail │
   │Exp. │ │metrics + PG │ │(all pods)│
   └─────┘ │Exporter     │ └─────────┘
           └─────────────┘
```

**Prerequisites**: [Helm 3](https://helm.sh/docs/intro/install/)

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

**Deploy** (one command):
```bash
make monitor-deploy
```

**Access Grafana**:
```bash
make grafana
# Open http://localhost:3000 → login: admin / admin
```

**Pre-configured alerts** (`monitoring/alerts.yaml`):

| Alert | Severity | Triggers when |
|-------|----------|---------------|
| OdooPodCrashLooping | 🔴 Critical | Pod restarts repeatedly |
| OdooPodsUnavailable | 🔴 Critical | Zero Odoo pods running |
| OdooHighCPU | 🟡 Warning | CPU > 85% for 10 min |
| OdooHighMemory | 🟡 Warning | Memory > 90% for 5 min |
| OdooOOMKill | 🔴 Critical | Pod killed by out-of-memory |
| OdooHPAMaxedOut | 🟡 Warning | HPA at max replicas for 15 min |
| PostgresDown | 🔴 Critical | PostgreSQL not ready |
| PostgresSlowQueries | 🟡 Warning | > 5 queries running > 5 sec |
| PVCAlmostFull | 🟡 Warning | Persistent volume > 85% full |

**Useful commands**:
```bash
make monitor-status    # Check monitoring pods
make grafana           # Open Grafana
make monitor-undeploy  # Remove monitoring
```

## Architecture

```
                    ┌────────────┐
    Internet ──────►│  Ingress   │
                    │ (nginx)    │
                    └─────┬──────┘
                          │
              ┌───────────┴───────────┐
              │ :8069       :8072     │
              ▼                       ▼
         ┌─────────┐          ┌──────────┐
         │  Odoo   │          │  Odoo    │
         │  HTTP   │          │ Longpoll │
         └────┬────┘          └──────────┘
              │
         ┌────▼────┐     ┌──────────┐
         │ Odoo    │     │ Postgres │
         │ PVC     │     │ PVC      │
         │(files)  │     │ (data)   │
         └─────────┘     └──────────┘
```

## Troubleshooting (kubeadm + VirtualBox)

<details>
<summary><b>PVCs stuck in Pending — no StorageClass</b></summary>

**Symptom**: `kubectl -n odoo get pvc` shows `Pending` status for all PVCs.

**Cause**: kubeadm clusters don't include a storage provisioner by default.

**Fix**:
```bash
# Install local-path-provisioner
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml

# Set as default
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Verify
kubectl get storageclass
```

</details>

<details>
<summary><b>i/o timeout — kubelet using NAT IP (10.0.2.15)</b></summary>

**Symptom**: `kubectl logs` or `kubectl exec` returns:
```
Error from server: dial tcp 10.0.2.15:10250: i/o timeout
```

**Cause**: VirtualBox VMs have two NICs — kubelet registered with the NAT IP (`10.0.2.15`) which is unreachable from the host.

**Fix** (on each worker VM):
```bash
# VM 1
echo 'KUBELET_EXTRA_ARGS="--node-ip=192.168.56.101"' | sudo tee /etc/default/kubelet
sudo systemctl restart kubelet

# VM 2
echo 'KUBELET_EXTRA_ARGS="--node-ip=192.168.56.102"' | sudo tee /etc/default/kubelet
sudo systemctl restart kubelet
```

**Verify**: `kubectl get nodes -o wide` should show `192.168.56.x` IPs, not `10.0.2.15`.

</details>

<details>
<summary><b>DNS not resolving — Flannel using wrong interface</b></summary>

**Symptom**: Init container logs show:
```
nc: bad address 'postgres'
```
Or `nslookup` inside a pod returns `connection timed out; no servers could be reached`.

**Cause**: Flannel picked the NAT interface instead of the Host-Only adapter, so pods on different nodes can't communicate.

**Fix**:
```bash
# Download Flannel manifest
curl -o /tmp/flannel.yaml https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml

# Add --iface-regex to match both host (vboxnet0) and VMs (enp0s8)
sed -i '/- --kube-subnet-mgr/a\        - --iface-regex=vboxnet0|enp0s8' /tmp/flannel.yaml

# Reapply
kubectl delete -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
kubectl apply -f /tmp/flannel.yaml

# Verify all Flannel pods are Running
kubectl -n kube-flannel get pods
```

> **Note**: The host interface is `vboxnet0`, VMs use `enp0s8`. Adjust names if your setup differs (`ip addr` to check).

</details>
