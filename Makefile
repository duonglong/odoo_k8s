.PHONY: help build push deploy undeploy restart status k8s-logs k8s-shell \
       psql odoo-shell port-forward setup-metallb \
       monitor-deploy monitor-undeploy grafana monitor-status

# Load config from .env (single source of truth for registry/image)
include .env
export

NAMESPACE := odoo
FULL_IMAGE := $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Docker ─────────────────────────────────────────

build: ## Build custom Odoo Docker image
	docker build -t $(FULL_IMAGE) -f docker/Dockerfile .

push: ## Push image to registry
	docker push $(FULL_IMAGE)

# ─── Kubernetes ─────────────────────────────────────

deploy: ## Deploy everything to Kubernetes (except monitoring)
	@echo "=== Setting up MetalLB ==="
	kubectl apply -f k8s/metallb-native.yaml
	kubectl -n metallb-system wait --for=condition=ready pod -l app=metallb --timeout=90s 2>/dev/null || true
	kubectl apply -f k8s/metallb-config.yaml
	@echo "=== Setting up Ingress Controller ==="
	kubectl apply -f k8s/ingress-nginx.yaml
	kubectl -n ingress-nginx wait --for=condition=ready pod -l app.kubernetes.io/component=controller --timeout=120s 2>/dev/null || true
	kubectl -n ingress-nginx patch svc ingress-nginx-controller -p '{"spec":{"type":"LoadBalancer"}}' 2>/dev/null || true
	@echo "=== Deploying Odoo ==="
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/secrets.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/odoo/
	kubectl -n $(NAMESPACE) set image deployment/odoo odoo=$(FULL_IMAGE)
	@echo "Waiting for Odoo..."
	kubectl -n $(NAMESPACE) rollout status deployment/odoo --timeout=180s
	kubectl apply -f k8s/ingress.yaml
	@echo "✅ Deployment complete! Image: $(FULL_IMAGE)"
	@kubectl -n ingress-nginx get svc ingress-nginx-controller
	@kubectl -n $(NAMESPACE) get pods -o wide

undeploy: ## Remove from Kubernetes
	kubectl delete -f k8s/ingress.yaml --ignore-not-found
	kubectl delete -f k8s/odoo/ --ignore-not-found
	kubectl delete -f k8s/configmap.yaml --ignore-not-found
	kubectl delete -f k8s/secrets.yaml --ignore-not-found
	@echo "⚠️  Namespace preserved. To fully clean up:"
	@echo "   kubectl delete namespace $(NAMESPACE)"

restart: ## Rolling restart Odoo pods (after addon/image changes)
	kubectl apply -f k8s/odoo/
	kubectl -n $(NAMESPACE) set image deployment/odoo odoo=$(FULL_IMAGE)
	kubectl -n $(NAMESPACE) rollout restart deployment/odoo
	kubectl -n $(NAMESPACE) rollout status deployment/odoo --timeout=180s

status: ## Show K8s resources status
	@echo "=== Nodes ==="
	@kubectl get nodes -o wide
	@echo "\n=== Odoo Pods ==="
	@kubectl -n $(NAMESPACE) get pods -o wide
	@echo "\n=== Services ==="
	@kubectl -n $(NAMESPACE) get svc
	@echo "\n=== Ingress ==="
	@kubectl -n $(NAMESPACE) get ingress
	@echo "\n=== HPA ==="
	@kubectl -n $(NAMESPACE) get hpa

k8s-logs: ## Tail Odoo pod logs in K8s
	kubectl -n $(NAMESPACE) logs -f -l app.kubernetes.io/name=odoo --prefix

k8s-shell: ## Open shell in Odoo pod
	kubectl -n $(NAMESPACE) exec -it deployment/odoo -- bash

psql: ## Connect to PostgreSQL (external)
	psql -h 192.168.56.1 -U odoo -d $(DB_NAME)

odoo-shell: ## Open Odoo interactive shell
	kubectl -n $(NAMESPACE) exec -it deployment/odoo -- odoo shell -d $(DB_NAME) --no-http

port-forward: ## Port-forward Odoo (no Ingress needed)
	@echo "Odoo available at http://localhost:8069"
	kubectl -n $(NAMESPACE) port-forward svc/odoo 8069:8069 8072:8072

# ─── Infrastructure ────────────────────────────────

setup-metallb: ## Install MetalLB load balancer
	kubectl apply -f k8s/metallb-native.yaml
	kubectl -n metallb-system wait --for=condition=ready pod --all --timeout=90s
	kubectl apply -f k8s/metallb-config.yaml
	kubectl -n ingress-nginx patch svc ingress-nginx-controller \
		-p '{"spec":{"type":"LoadBalancer"}}'
	@echo "✅ MetalLB configured! Check external IP:"
	@kubectl -n ingress-nginx get svc ingress-nginx-controller

# ─── Monitoring ────────────────────────────────────

monitor-deploy: ## Deploy full monitoring stack (Prometheus + Grafana + Loki)
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
	helm repo add grafana https://grafana.github.io/helm-charts
	helm repo update
	helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
		-n monitoring --create-namespace -f monitoring/prometheus-values.yaml
	helm upgrade --install loki grafana/loki-stack \
		-n monitoring -f monitoring/loki-values.yaml
	helm upgrade --install pg-exporter prometheus-community/prometheus-postgres-exporter \
		-n $(NAMESPACE) -f monitoring/postgres-exporter-values.yaml
	kubectl apply -f monitoring/alerts.yaml
	@echo "✅ Monitoring deployed! Run 'make grafana' to access Grafana."

monitor-undeploy: ## Remove monitoring stack
	kubectl delete -f monitoring/alerts.yaml --ignore-not-found
	helm uninstall pg-exporter -n $(NAMESPACE) --ignore-not-found 2>/dev/null || true
	helm uninstall loki -n monitoring --ignore-not-found 2>/dev/null || true
	helm uninstall monitoring -n monitoring --ignore-not-found 2>/dev/null || true
	@echo "⚠️  Monitoring namespace preserved. To fully clean: kubectl delete namespace monitoring"

grafana: ## Open Grafana dashboard (port-forward)
	@echo "Grafana available at http://localhost:3000 (admin/admin)"
	kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80

monitor-status: ## Show monitoring stack status
	@echo "=== Monitoring Pods ==="
	@kubectl -n monitoring get pods 2>/dev/null || echo "Monitoring not deployed"
	@echo "\n=== PostgreSQL Exporter ==="
	@kubectl -n $(NAMESPACE) get pods -l app.kubernetes.io/name=prometheus-postgres-exporter 2>/dev/null || echo "Not deployed"
	@echo "\n=== Alerts ==="
	@kubectl -n monitoring get prometheusrules 2>/dev/null || echo "No alert rules"
