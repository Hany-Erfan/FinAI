.PHONY: help up down restart logs status build rebuild deploy-cluster deploy-status deploy-logs deploy-cost-estimate teardown-cluster deploy-service deploy-frontend deploy-host-agent deploy-faq-agent

# Load environment variables (POSIX-safe)
ifneq (,$(wildcard .env))
	include .env
	export
endif

help: ## Show this help message
	@echo 'Usage: make [target]'
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

deploy-cluster: ## Deploy GKE cluster and application (requires gcloud auth)
	./scripts/deployment/deploy_gke.sh

teardown-cluster: ## Teardown GKE cluster and release resources (requires gcloud auth)
	./scripts/deployment/teardown_gke.sh

deploy-status: ## Show GKE deployment status and resource usage
	@echo "=== Cluster Info ==="
	@gcloud container clusters describe agentixbuddy-cluster --region europe-west3 --format="value(name,location,currentMasterVersion,status)" || echo "Cluster not found"
	@echo ""
	@echo "=== Pods Status ==="
	@kubectl get pods -n agentixbuddy -o wide || echo "Namespace not found"
	@echo ""
	@echo "=== Resource Usage ==="
	@kubectl top pods -n agentixbuddy 2>/dev/null || echo "Metrics not available yet"
	@echo ""
	@echo "=== Services ==="
	@kubectl get svc -n agentixbuddy || echo "Namespace not found"
	@echo ""
	@echo "=== Ingress ==="
	@kubectl get ingress -n agentixbuddy || echo "Namespace not found"

deploy-logs: ## Tail logs from all GKE pods
	@echo "Tailing logs from all pods in agentixbuddy namespace..."
	@kubectl logs -f -n agentixbuddy --all-containers=true --max-log-requests=20 -l 'app' --prefix=true

deploy-cost-estimate: ## Show estimated GKE costs and resource breakdown
	@echo "=== GKE Autopilot Resource Summary ==="
	@echo ""
	@echo "Cluster Mode:"
	@gcloud container clusters describe agentixbuddy-cluster --region europe-west3 --format="value(autopilot.enabled)" | sed 's/True/Autopilot Enabled - Pay per Pod/' || echo "Cluster not found"
	@echo ""
	@echo "Pod Resources:"
	@kubectl get pods -n agentixbuddy -o json 2>/dev/null | jq -r '.items[] | "\(.metadata.name): CPU=\(.spec.containers[0].resources.requests.cpu // "N/A"), Memory=\(.spec.containers[0].resources.requests.memory // "N/A")"' || echo "Cannot fetch pod resources"
	@echo ""
	@echo "Spot Pods (60-90% discount):"
	@kubectl get pods -n agentixbuddy -o json 2>/dev/null | jq -r '.items[] | select(.spec.nodeSelector["cloud.google.com/gke-spot"] == "true") | .metadata.name' | sed 's/^/  /' || echo "No spot pods found"
	@echo ""
	@echo "Storage:"
	@kubectl get pvc -n agentixbuddy -o custom-columns=NAME:.metadata.name,SIZE:.spec.resources.requests.storage,CLASS:.spec.storageClassName 2>/dev/null || echo "No PVCs found"
	@echo ""
	@echo "Estimated Monthly Cost: Visit https://cloud.google.com/products/calculator"
	@echo "Autopilot charges: ~\$$0.0445/vCPU-hour, ~\$$0.00491/GB-hour"

# ============================================
# Individual Service Deployments (for updates)
# ============================================

PROJECT_ID=agentixbuddy-dev
REGION=europe-west3
REPO=agentixbuddy-repo
NAMESPACE=agentixbuddy

deploy-frontend: ## Rebuild and deploy frontend only
	@echo "Building and pushing frontend..."
	docker build --no-cache --platform linux/amd64 -t $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/frontend:latest -f frontend/Dockerfile frontend
	docker push $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/frontend:latest
	kubectl delete pod -l app=frontend -n $(NAMESPACE)
	kubectl rollout status deployment/frontend -n $(NAMESPACE) --timeout=120s

deploy-host-agent: ## Rebuild and deploy host-agent only
	@echo "Building and pushing host-agent..."
	docker build --no-cache --platform linux/amd64 -t $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/host-agent:latest -f backend/host_agent/Dockerfile .
	docker push $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/host-agent:latest
	kubectl delete pod -l app=host-agent -n $(NAMESPACE)
	kubectl rollout status deployment/host-agent -n $(NAMESPACE) --timeout=120s

deploy-faq-agent: ## Rebuild and deploy faq-agent only
	@echo "Building and pushing faq-agent..."
	docker build --no-cache --platform linux/amd64 -t $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/faq-agent:latest -f backend/agents/faq_agent/Dockerfile .
	docker push $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/faq-agent:latest
	kubectl delete pod -l app=faq-agent -n $(NAMESPACE)
	kubectl rollout status deployment/faq-agent -n $(NAMESPACE) --timeout=120s

deploy-vector-db: ## Rebuild and deploy vector-db-service only
	@echo "Building and pushing vector-db-service..."
	docker build --no-cache --platform linux/amd64 -t $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/vector-db-service:latest -f backend/services/vector_db_service/Dockerfile .
	docker push $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/vector-db-service:latest
	kubectl delete pod -l app=vector-db-service -n $(NAMESPACE)
	kubectl rollout status deployment/vector-db-service -n $(NAMESPACE) --timeout=120s

deploy-guardrails: ## Rebuild and deploy guardrails-service only
	@echo "Building and pushing guardrails-service..."
	docker build --no-cache --platform linux/amd64 -t $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/guardrails-service:latest -f backend/services/guardrails/Dockerfile .
	docker push $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/guardrails-service:latest
	kubectl delete pod -l app=guardrails-service -n $(NAMESPACE)
	kubectl rollout status deployment/guardrails-service -n $(NAMESPACE) --timeout=120s