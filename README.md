# Odoo on Kubernetes

Deploy Odoo 19.0 on Kubernetes.

## Project Structure

```
odoo_k8s/
├── docker/                      # Docker image files
│   ├── Dockerfile               #   extends odoo:19.0
│   ├── requirements.txt         #   Python dependencies
│   ├── entrypoint.sh            #   official Odoo entrypoint
│   └── wait-for-psql.py         #   DB readiness check
├── addons/                      # Custom Odoo addons (baked into image)
├── k8s/                         # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml           #   odoo.conf + shared env vars
│   ├── secrets.yaml             #   plain-text secrets (⚠️ gitignored)
│   ├── sealed-secrets.yaml      #   encrypted secrets (safe to commit)
│   ├── sealed-secrets-controller.yaml  # Sealed Secrets controller
│   ├── ingress.yaml             #   routing rules
│   ├── ingress-nginx.yaml       #   Nginx Ingress controller
│   ├── metallb-native.yaml      #   MetalLB load balancer
│   ├── metallb-config.yaml      #   MetalLB IP pool
│   └── odoo/
│       ├── deployment.yaml      #   Odoo web pods (stateless, no cron)
│       ├── cron-deployment.yaml #   Odoo cron worker (single replica)
│       ├── service.yaml         #   ClusterIP service
│       └── hpa.yaml             #   Horizontal Pod Autoscaler
├── monitoring/                  # Prometheus + Grafana stack
├── Makefile                     # All commands (make help)
├── .env                         # Registry/image config
└── README.md
```

## Kubernetes Deployment

### Step 1 — Install kubectl

```bash
# Ubuntu/Debian
sudo snap install kubectl --classic

# Verify
kubectl version --client
```

### Step 2 — Cluster Setup (kubeadm)

Your **control plane** node manages the cluster, **worker nodes** run Odoo. All nodes should be on the same network and reachable by IP.

#### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Network: 10.0.0.0/24                                    │
│                                                         │
│ ┌───────────────────┐                                   │
│ │ Control Plane     │  10.0.0.10                        │
│ │ • kube-apiserver  │  • Ubuntu 22.04+                  │
│ │ • etcd, scheduler │  • 2 CPU, 4GB RAM, 30GB disk      │
│ │ • kubectl         │                                   │
│ └───────────────────┘                                   │
│                                                         │
│ ┌───────────────────┐  ┌───────────────────┐            │
│ │ Worker Node 1     │  │ Worker Node 2     │            │
│ │ 10.0.0.11         │  │ 10.0.0.12         │            │
│ │ 2 CPU, 4GB RAM    │  │ 2 CPU, 4GB RAM    │            │
│ │ 30GB disk         │  │ 30GB disk         │            │
│ └───────────────────┘  └───────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

> Replace `10.0.0.x` with your actual server IPs throughout this guide.

#### 2.1 — Prerequisites (ALL nodes)

Ensure all nodes have:
- Ubuntu 22.04+ (or equivalent)
- Static IPs assigned
- SSH access configured
- Unique hostnames: `sudo hostnamectl set-hostname <name>`

<details>
<summary>📦 Using VirtualBox VMs instead of real servers?</summary>

1. Create 2+ VMs in VirtualBox:
   - **CPU**: 2 cores, **RAM**: 4GB, **Disk**: 30GB
   - **Network Adapter 1**: NAT (for internet)
   - **Network Adapter 2**: Host-Only Adapter (`vboxnet0`, for cluster communication)
2. Assign static IPs on the Host-Only interface:
```bash
# /etc/netplan/01-host-only.yaml (on each VM)
network:
  version: 2
  ethernets:
    enp0s8:
      addresses: [192.168.56.101/24]  # .102 for VM 2, etc.

sudo netplan apply
```
</details>

#### 2.2 — Install Container Runtime (ALL nodes)

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

#### 2.3 — Install kubeadm, kubelet, kubectl (ALL nodes)

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

#### 2.4 — Initialize Control Plane (control plane node only)

```bash
sudo kubeadm init \
  --apiserver-advertise-address=10.0.0.10 \
  --pod-network-cidr=10.244.0.0/16

# Set up kubectl for your user
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Install Flannel CNI (pod network)
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
```

<details>
<summary>⚠️ Using VirtualBox? Flannel needs an extra flag</summary>

VirtualBox VMs have two network adapters (NAT + Host-Only). Flannel may pick the wrong one. Fix:
```bash
# Download, patch, and apply Flannel
curl -o /tmp/flannel.yaml https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
sed -i '/- --kube-subnet-mgr/a\        - --iface-regex=vboxnet0|enp0s8' /tmp/flannel.yaml
kubectl apply -f /tmp/flannel.yaml
```
</details>

#### 2.5 — Join Worker Nodes (on each worker)

The `kubeadm init` output prints a join command. Run it on each worker:

```bash
sudo kubeadm join 10.0.0.10:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash>
```

If you lost the token, regenerate on the control plane:
```bash
kubeadm token create --print-join-command
```

<details>
<summary>⚠️ Using VirtualBox? Fix kubelet node IP</summary>

VirtualBox VMs register with the NAT IP (`10.0.2.15`) by default, which is unreachable. Fix on **each worker VM**:
```bash
# On VM 1
echo 'KUBELET_EXTRA_ARGS="--node-ip=192.168.56.101"' | sudo tee /etc/default/kubelet
sudo systemctl restart kubelet

# On VM 2
echo 'KUBELET_EXTRA_ARGS="--node-ip=192.168.56.102"' | sudo tee /etc/default/kubelet
sudo systemctl restart kubelet
```
Verify nodes show `192.168.56.x` IPs (not `10.0.2.15`) in `kubectl get nodes -o wide`.
</details>

#### 2.6 — Verify Cluster

```bash
kubectl get nodes -o wide
# NAME           STATUS   ROLES           AGE   VERSION   INTERNAL-IP
# control-plane  Ready    control-plane   2m    v1.29.0   10.0.0.10
# worker-1       Ready    <none>          1m    v1.29.0   10.0.0.11
# worker-2       Ready    <none>          1m    v1.29.0   10.0.0.12
```

#### 2.7 — Install Nginx Ingress Controller

```bash
kubectl apply -f k8s/ingress-nginx.yaml
```


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

# 3. Deploy Odoo and wait for it
kubectl apply -f k8s/odoo/
kubectl -n odoo rollout status deployment/odoo --timeout=180s

# 4. Create Ingress
kubectl apply -f k8s/ingress.yaml
```

Or simply run **`make deploy`** — it does all of the above in order.

### Step 4 — Access Odoo

**Port-forward** (works with any setup):
```bash
kubectl -n odoo port-forward svc/odoo 8069:8069 8072:8072
# → http://localhost:8069
```


**Via Ingress** (kubeadm + MetalLB):
```bash
# 1. Install MetalLB (gives LoadBalancer IPs on bare-metal)
kubectl apply -f k8s/metallb-native.yaml
kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=90s

# 2. Configure IP pool
kubectl apply -f k8s/metallb-config.yaml

# 3. Switch Ingress controller to LoadBalancer
kubectl -n ingress-nginx patch svc ingress-nginx-controller \
  -p '{"spec":{"type":"LoadBalancer"}}'

# 4. Get the assigned external IP
kubectl -n ingress-nginx get svc ingress-nginx-controller
# EXTERNAL-IP: 10.0.0.200

# 5. Add to /etc/hosts (or configure DNS)
echo "10.0.0.200 odoo.local" | sudo tee -a /etc/hosts

# → http://odoo.local
```

### Step 5 — Verify & Manage

```bash
make status       # Show all pods, services, PVCs
make k8s-logs     # Tail Odoo logs
make k8s-shell    # Shell into Odoo container
```

---

### Secrets Management (Sealed Secrets)

Secrets are encrypted with [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) — safe to commit to git.

```
k8s/secrets.yaml              k8s/sealed-secrets.yaml
(plain text, gitignored)       (encrypted, committed to git)
        │                              │
        └── make seal-secrets ─────────┘
                                       │
                              kubectl apply → controller decrypts → K8s Secret
```

#### How it works

- A **controller** in the cluster holds a private key
- `kubeseal` encrypts secrets with the controller's public key
- Only the cluster can decrypt → sealed file is safe in git
- The controller creates a standard K8s Secret that pods read normally

#### Updating secrets

```bash
# 1. Edit plain-text secrets locally
vim k8s/secrets.yaml    # update base64-encoded values

# 2. Re-seal
make seal-secrets

# 3. Apply and restart
kubectl apply -f k8s/sealed-secrets.yaml
make restart

# 4. Commit the sealed version
git add k8s/sealed-secrets.yaml
git commit -m "Update sealed secrets"
```

> [!IMPORTANT]
> **Backup the controller's private key!** If you lose it (cluster rebuild), you can't decrypt existing sealed secrets.
> ```bash
> kubectl -n kube-system get secret -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > sealed-secrets-key-backup.yaml
> # Store this backup securely — NOT in git!
> ```

### Tear Down

```bash
make undeploy                    # Remove Odoo from K8s
kubectl delete namespace odoo    # Full cleanup

# Reset kubeadm (on each worker node)
sudo kubeadm reset
# Reset kubeadm (on control plane)
sudo kubeadm reset
```

---

### Troubleshooting

<details>
<summary><b>502 Bad Gateway</b></summary>

Ingress can't reach the backend pods.

```bash
# Check if pods are running and ready
kubectl -n odoo get pods -l app.kubernetes.io/component=web

# Check Ingress has endpoints
kubectl -n odoo get endpoints odoo
# Should show pod IPs, not <none>

# Check Ingress resource exists
kubectl -n odoo get ingress
# If empty → kubectl apply -f k8s/ingress.yaml
```

**Common causes:**
- Pods still starting (wait for `1/1 Running`)
- Ingress not applied (`kubectl apply -f k8s/ingress.yaml`)
- Service selector doesn't match pod labels
</details>

<details>
<summary><b>CrashLoopBackOff</b></summary>

Pod starts but crashes immediately.

```bash
# Check why it crashed
kubectl -n odoo logs <pod-name> -c odoo --previous

# Check init container logs
kubectl -n odoo logs <pod-name> -c build-config
kubectl -n odoo logs <pod-name> -c wait-for-db
```

**Common causes:**
- PostgreSQL unreachable (check `pg_hba.conf` and `listen_addresses`)
- Wrong DB credentials in `secrets.yaml`
- Using `command` instead of `args` (bypasses entrypoint)
</details>

<details>
<summary><b>PostgreSQL connection refused</b></summary>

```
connection to server at "192.168.56.1", port 5432 failed: FATAL: no pg_hba.conf entry
```

Fix on your PostgreSQL host:

```bash
# 1. Allow connections from your network
echo "host all all 192.168.56.0/24 md5" | sudo tee -a /etc/postgresql/*/main/pg_hba.conf

# 2. Listen on all interfaces
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/*/main/postgresql.conf

# 3. Restart
sudo systemctl restart postgresql
```
</details>

<details>
<summary><b>Pod evicted — disk pressure</b></summary>

```
The node was low on resource: ephemeral-storage
```

Worker node disk is full.

```bash
# Check disk on the node
ssh <node> 'df -h / && sudo crictl rmi --prune'

# If still low, resize the disk (VirtualBox example)
VBoxManage modifymedium disk /path/to/disk.vdi --resize 30720
# Then expand LVM inside the VM
ssh <node>
sudo growpart /dev/sda 3
sudo pvresize /dev/sda3
sudo lvextend -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv
sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv
```

**Minimum recommended**: 30GB per node.
</details>

<details>
<summary><b>HPA: unable to get metrics</b></summary>

```
failed to get cpu utilization: unable to get metrics for resource cpu
```

Metrics server is not working.

```bash
# Check if metrics-server is running
kubectl -n kube-system get pods -l k8s-app=metrics-server

# Test metrics
kubectl top nodes
kubectl top pods -n odoo

# If not installed
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# For kubeadm with self-signed certs
kubectl -n kube-system patch deployment metrics-server --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```
</details>

<details>
<summary><b>Ingress returns 404</b></summary>

Pods are running but Ingress returns 404.

```bash
# Check Ingress exists
kubectl -n odoo get ingress
# If empty → kubectl apply -f k8s/ingress.yaml

# Verify host matches
kubectl -n odoo describe ingress odoo-ingress
# Host should match what's in /etc/hosts

# Check /etc/hosts
cat /etc/hosts | grep odoo
# Should point to MetalLB external IP
kubectl -n ingress-nginx get svc ingress-nginx-controller
```
</details>

<details>
<summary><b>Pods stuck in Pending — node taints</b></summary>

```
0/3 nodes are available: 1 node(s) had untolerated taint {node-role.kubernetes.io/control-plane: }
```

```bash
# Check node taints
kubectl describe nodes | grep -A2 Taints

# Allow scheduling on control plane (dev/testing only)
kubectl taint nodes <control-plane> node-role.kubernetes.io/control-plane:NoSchedule-

# Check if worker nodes are Ready
kubectl get nodes
# If NotReady — check kubelet logs on the worker
ssh <node> 'sudo journalctl -u kubelet --no-pager -n 50'
```
</details>


### All Makefile Commands

```bash
make help         # Show all available commands
make build        # Build custom Docker image
make push         # Push image to registry
make deploy       # Deploy everything to K8s
make undeploy     # Remove from K8s
make restart      # Rolling restart (after code/image changes)
make status       # Show K8s resource status
make k8s-logs     # Tail Odoo pod logs
make k8s-shell    # Shell into Odoo pod
make psql         # Connect to PostgreSQL (psql)
make odoo-shell   # Open Odoo interactive shell
make port-forward # Port-forward Odoo locally
make seal-secrets # Encrypt secrets (safe to commit)
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

## Testing Load Balancing

> ⚠️ `port-forward` connects to a **single pod** only. To test real load balancing, go through the Ingress or Service.

**Via Ingress (NodePort):**
```bash
# Find the NodePort
kubectl -n ingress-nginx get svc ingress-nginx-controller

# Send requests through Ingress (replace 31080 with your NodePort)
for i in $(seq 1 20); do
  curl -s -o /dev/null -H "Host: odoo.local" http://192.168.56.101:31080/web/health &
done
wait

# Check which pods handled requests
kubectl -n odoo logs -l app.kubernetes.io/name=odoo --tail=10 --prefix
```

**Via Service (from inside the cluster):**
```bash
kubectl run test --rm -it --image=busybox -- sh -c '
  for i in $(seq 1 20); do
    wget -qO- http://odoo.odoo:8069/web/health 2>/dev/null &
  done
  wait
'
```

**Verify endpoints** (both pod IPs should be listed):
```bash
kubectl -n odoo get endpoints odoo
# Should show: 10.244.1.x:8069, 10.244.2.x:8069
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
