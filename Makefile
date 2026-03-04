.PHONY: help up down restart logs status build rebuild deploy-cluster deploy-services deploy-apps deploy-status deploy-logs deploy-cost-estimate teardown-cluster deploy-frontend deploy-host-agent deploy-faq-agent deploy-vector-db deploy-guardrails

# Load environment variables (POSIX-safe)
ifneq (,$(wildcard .env))
	include .env
	export
endif

# ============================================
# GCP Configuration (override via environment)
# ============================================
GCP_PROJECT_ID ?= agentixbuddy-dev
GCP_REGION ?= europe-west3
GCP_REPO ?= agentixbuddy-repo
K8S_NAMESPACE ?= agentixbuddy
GKE_CLUSTER_NAME ?= agentixbuddy-cluster

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Configuration (override via environment):'
	@echo '  GCP_PROJECT_ID=$(GCP_PROJECT_ID)'
	@echo '  GCP_REGION=$(GCP_REGION)'
	@echo '  K8S_NAMESPACE=$(K8S_NAMESPACE)'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================
# Local Development (Docker Compose)
# ============================================

up: ## Start all services locally
	docker-compose up -d

down: ## Stop containers and remove volumes
	docker-compose down -v --remove-orphans

restart: ## Restart all services
	docker-compose restart

logs: ## Follow logs for all services
	docker-compose logs -f

status: ## Show status of all services
	docker-compose ps

build: ## Build all containers
	docker-compose build

rebuild: ## Rebuild all containers without cache
	docker-compose build --no-cache

# ============================================
# Cloud Deployment (GKE)
# ============================================

deploy-cluster: ## Deploy full GKE cluster, database, and all services (requires gcloud auth)
	./scripts/deployment/deploy_gke.sh

deploy-services: ## Redeploy secrets, config, and all services (keeps database and data)
	SKIP_DB=1 ./scripts/deployment/deploy_gke.sh

teardown-cluster: ## Teardown GKE cluster and release resources (requires gcloud auth)
	./scripts/deployment/teardown_gke.sh

deploy-status: ## Show GKE deployment status and resource usage
	@echo "=== Cluster Info ==="
	@gcloud container clusters describe $(GKE_CLUSTER_NAME) --region $(GCP_REGION) --format="value(name,location,currentMasterVersion,status)" || echo "Cluster not found"
	@echo ""
	@echo "=== Pods Status ==="
	@kubectl get pods -n $(K8S_NAMESPACE) -o wide || echo "Namespace not found"
	@echo ""
	@echo "=== Resource Usage ==="
	@kubectl top pods -n $(K8S_NAMESPACE) 2>/dev/null || echo "Metrics not available yet"
	@echo ""
	@echo "=== Services ==="
	@kubectl get svc -n $(K8S_NAMESPACE) || echo "Namespace not found"
	@echo ""
	@echo "=== Ingress ==="
	@kubectl get ingress -n $(K8S_NAMESPACE) || echo "Namespace not found"

deploy-logs: ## Tail logs from all GKE pods
	@echo "Tailing logs from all pods in $(K8S_NAMESPACE) namespace..."
	@kubectl logs -f -n $(K8S_NAMESPACE) --all-containers=true --max-log-requests=20 -l 'app' --prefix=true

deploy-cost-estimate: ## Show estimated GKE costs and resource breakdown
	@echo "=== GKE Autopilot Resource Summary ==="
	@echo ""
	@echo "Cluster Mode:"
	@gcloud container clusters describe $(GKE_CLUSTER_NAME) --region $(GCP_REGION) --format="value(autopilot.enabled)" | sed 's/True/Autopilot Enabled - Pay per Pod/' || echo "Cluster not found"
	@echo ""
	@echo "Pod Resources:"
	@kubectl get pods -n $(K8S_NAMESPACE) -o json 2>/dev/null | jq -r '.items[] | "\(.metadata.name): CPU=\(.spec.containers[0].resources.requests.cpu // "N/A"), Memory=\(.spec.containers[0].resources.requests.memory // "N/A")"' || echo "Cannot fetch pod resources"
	@echo ""
	@echo "Spot Pods (60-90% discount):"
	@kubectl get pods -n $(K8S_NAMESPACE) -o json 2>/dev/null | jq -r '.items[] | select(.spec.nodeSelector["cloud.google.com/gke-spot"] == "true") | .metadata.name' | sed 's/^/  /' || echo "No spot pods found"
	@echo ""
	@echo "Storage:"
	@kubectl get pvc -n $(K8S_NAMESPACE) -o custom-columns=NAME:.metadata.name,SIZE:.spec.resources.requests.storage,CLASS:.spec.storageClassName 2>/dev/null || echo "No PVCs found"
	@echo ""
	@echo "Estimated Monthly Cost: Visit https://cloud.google.com/products/calculator"
	@echo "Autopilot charges: ~\$$0.0445/vCPU-hour, ~\$$0.00491/GB-hour"

deploy-apps: deploy-frontend deploy-host-agent deploy-faq-agent deploy-vector-db deploy-guardrails ## Rebuild and deploy all app services (keeps databases)

# ============================================
# Individual Service Deployments (for updates)
# ============================================

deploy-frontend: ## Rebuild and deploy frontend only
	@echo "Building and pushing frontend..."
	docker build --no-cache --platform linux/amd64 -t $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/frontend:latest -f frontend/Dockerfile frontend
	docker push $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/frontend:latest
	kubectl delete pod -l app=frontend -n $(K8S_NAMESPACE)
	kubectl rollout status deployment/frontend -n $(K8S_NAMESPACE) --timeout=120s

deploy-host-agent: ## Rebuild and deploy host-agent only
	@echo "Building and pushing host-agent..."
	docker build --no-cache --platform linux/amd64 -t $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/host-agent:latest -f backend/host_agent/Dockerfile .
	docker push $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/host-agent:latest
	kubectl delete pod -l app=host-agent -n $(K8S_NAMESPACE)
	kubectl rollout status deployment/host-agent -n $(K8S_NAMESPACE) --timeout=120s

deploy-faq-agent: ## Rebuild and deploy faq-agent only
	@echo "Building and pushing faq-agent..."
	docker build --no-cache --platform linux/amd64 -t $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/faq-agent:latest -f backend/agents/faq_agent/Dockerfile .
	docker push $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/faq-agent:latest
	kubectl delete pod -l app=faq-agent -n $(K8S_NAMESPACE)
	kubectl rollout status deployment/faq-agent -n $(K8S_NAMESPACE) --timeout=120s

deploy-vector-db: ## Rebuild and deploy vector-db-service only
	@echo "Building and pushing vector-db-service..."
	docker build --no-cache --platform linux/amd64 -t $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/vector-db-service:latest -f backend/services/vector_db_service/Dockerfile .
	docker push $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/vector-db-service:latest
	kubectl delete pod -l app=vector-db-service -n $(K8S_NAMESPACE)
	kubectl rollout status deployment/vector-db-service -n $(K8S_NAMESPACE) --timeout=120s

deploy-guardrails: ## Rebuild and deploy guardrails-service only
	@echo "Building and pushing guardrails-service..."
	docker build --no-cache --platform linux/amd64 -t $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/guardrails-service:latest -f backend/services/guardrails/Dockerfile .
	docker push $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/$(GCP_REPO)/guardrails-service:latest
	kubectl delete pod -l app=guardrails-service -n $(K8S_NAMESPACE)
	kubectl rollout status deployment/guardrails-service -n $(K8S_NAMESPACE) --timeout=120s