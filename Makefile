.PHONY: help build up down logs shell deploy undeploy k8s-logs k8s-shell status

NAMESPACE := odoo
IMAGE_NAME := odoo-k8s
IMAGE_TAG := 19.0

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Docker ─────────────────────────────────────────

build: ## Build custom Odoo Docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) -f docker/Dockerfile docker/

up: ## Start local dev environment (docker-compose)
	docker compose up -d

down: ## Stop local dev environment
	docker compose down

logs: ## Tail Odoo container logs (docker-compose)
	docker compose logs -f odoo

shell: ## Open shell in Odoo container
	docker compose exec odoo bash

# ─── Kubernetes ─────────────────────────────────────

deploy: ## Deploy to Kubernetes
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/secrets.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/postgres/
	@echo "Waiting for PostgreSQL..."
	kubectl -n $(NAMESPACE) rollout status statefulset/postgres --timeout=120s
	kubectl apply -f k8s/odoo/
	@echo "Waiting for Odoo..."
	kubectl -n $(NAMESPACE) rollout status deployment/odoo --timeout=180s
	kubectl apply -f k8s/ingress.yaml
	@echo "✅ Deployment complete!"
	@kubectl -n $(NAMESPACE) get pods

undeploy: ## Remove from Kubernetes (preserves PVCs)
	kubectl delete -f k8s/ingress.yaml --ignore-not-found
	kubectl delete -f k8s/odoo/ --ignore-not-found
	kubectl delete -f k8s/postgres/ --ignore-not-found
	kubectl delete -f k8s/configmap.yaml --ignore-not-found
	kubectl delete -f k8s/secrets.yaml --ignore-not-found
	@echo "⚠️  Namespace and PVCs preserved. To fully clean up:"
	@echo "   kubectl delete namespace $(NAMESPACE)"

status: ## Show K8s resources status
	@echo "=== Pods ==="
	@kubectl -n $(NAMESPACE) get pods
	@echo "\n=== Services ==="
	@kubectl -n $(NAMESPACE) get svc
	@echo "\n=== PVCs ==="
	@kubectl -n $(NAMESPACE) get pvc
	@echo "\n=== Ingress ==="
	@kubectl -n $(NAMESPACE) get ingress

k8s-logs: ## Tail Odoo pod logs in K8s
	kubectl -n $(NAMESPACE) logs -f deployment/odoo

k8s-shell: ## Open shell in Odoo pod
	kubectl -n $(NAMESPACE) exec -it deployment/odoo -- bash

port-forward: ## Port-forward Odoo (no Ingress needed)
	@echo "Odoo available at http://localhost:8069"
	kubectl -n $(NAMESPACE) port-forward svc/odoo 8069:8069 8072:8072
