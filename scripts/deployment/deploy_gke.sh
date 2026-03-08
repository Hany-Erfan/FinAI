#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$SCRIPT_DIR/k8s"

# ----------------------------
# --- Install jq if not present ---
# ----------------------------
if ! command -v jq &> /dev/null; then
  echo "jq not found. Installing jq..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install jq
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt-get update && sudo apt-get install -y jq
  fi
fi

# ----------------------------
# --- Load .env file first ---
# ----------------------------
if [ -f .env ]; then
  echo "Loading environment from .env file..."
  set -a
  source .env
  set +a
else
  echo "No .env file found, using defaults"
fi

if [ -f .env.secrets ]; then
  echo "Loading secrets from .env.secrets file..."
  set -a
  source .env.secrets
  set +a
else
  echo "WARNING: No .env.secrets file found. API keys will not be set."
fi

# ----------------------------
# --- Required secrets/env validation ---
# ----------------------------
: "${GOOGLE_API_KEY:?GOOGLE_API_KEY is required}"
: "${ORCHESTRATOR_GOOGLE_API_KEY:?ORCHESTRATOR_GOOGLE_API_KEY is required}"
: "${SERVICES_GOOGLE_API_KEY:?SERVICES_GOOGLE_API_KEY is required}"
: "${GUARDRAILS_API_KEY:?GUARDRAILS_API_KEY is required}"
: "${GUARDRAILS_LLM_MODEL:?GUARDRAILS_LLM_MODEL is required}"

# ----------------------------
# --- Cluster Configuration ---
# ----------------------------
# These can be overridden via .env or environment variables
PROJECT_ID="${GCP_PROJECT_ID:-agentixbuddy-dev}"
REGION="${GCP_REGION:-europe-west3}"
REPO="${GCP_REPO:-agentixbuddy-repo}"
NAMESPACE="${K8S_NAMESPACE:-agentixbuddy}"
CLUSTER_NAME="${GKE_CLUSTER_NAME:-agentixbuddy-cluster}"

# ----------------------------
# --- GCloud Auth & Cluster ---
# ----------------------------
echo "Using project: $PROJECT_ID, region: $REGION, cluster: $CLUSTER_NAME"

gcloud auth login --quiet
gcloud config set project $PROJECT_ID

# ----------------------------
# --- Create/Get GKE Cluster ---
# ----------------------------
if ! gcloud container clusters describe $CLUSTER_NAME --region $REGION > /dev/null 2>&1; then
  echo "GKE Autopilot cluster not found. Creating Autopilot cluster..."
  gcloud container clusters create-auto $CLUSTER_NAME \
    --region $REGION \
    --release-channel regular
else
  echo "GKE Autopilot cluster already exists."
fi

gcloud container clusters get-credentials $CLUSTER_NAME --region $REGION

# ----------------------------
# --- Reserve/Get Static IP for Ingress LoadBalancer ---
# ----------------------------
STATIC_IP_NAME="agentixbuddy-ingress-ip"
if [ -z "$(gcloud compute addresses describe "$STATIC_IP_NAME" --region "$REGION" --format=json 2>/dev/null | jq -r '.address // empty')" ]; then
  echo "Static IP not found. Creating static IP: $STATIC_IP_NAME ..."
  gcloud compute addresses create "$STATIC_IP_NAME" --region "$REGION"
else
  echo "Static IP already exists: $STATIC_IP_NAME"
fi
INGRESS_STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" --region "$REGION" --format="get(address)")
echo "Ingress static IP: $INGRESS_STATIC_IP"

# Authenticate Docker to Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Create Artifact Registry repository if it doesn't exist
if ! gcloud artifacts repositories describe $REPO --location=$REGION > /dev/null 2>&1; then
  echo "Creating Artifact Registry repository..."
  gcloud artifacts repositories create $REPO \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for AgentixBuddy"
fi

# Create Kubernetes namespace if it doesn't exist
kubectl get namespace $NAMESPACE >/dev/null 2>&1 || kubectl create namespace $NAMESPACE

# ----------------------------
# --- Create Secret for API Keys ---
# ----------------------------
echo "Creating Kubernetes secret for API keys..."
kubectl create secret generic api-keys \
  --from-env-file=.env.secrets \
  -n $NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

# ----------------------------
# --- Create ConfigMap from .env ---
# ----------------------------
kubectl create configmap app-env \
  --from-env-file=.env \
  -n $NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

# ----------------------------
# --- CLEANUP EXISTING RESOURCES ---
# ----------------------------
if [ "${SKIP_DB}" = "1" ]; then
  echo "Cleaning up app deployments only (keeping database)..."
  kubectl delete deployment --all -n $NAMESPACE --ignore-not-found
  kubectl delete job --all -n $NAMESPACE --ignore-not-found
else
  echo "Cleaning up all deployments, statefulsets, jobs, pods, services, PVCs in $NAMESPACE..."
  kubectl delete deployment --all -n $NAMESPACE --ignore-not-found
  kubectl delete statefulset --all -n $NAMESPACE --ignore-not-found
  kubectl delete job --all -n $NAMESPACE --ignore-not-found
  kubectl delete pod --all -n $NAMESPACE --ignore-not-found
  kubectl delete service --all -n $NAMESPACE --ignore-not-found
  kubectl delete pvc --all -n $NAMESPACE --ignore-not-found
fi

# ----------------------------
# --- Deploy Qdrant (Vector Database) ---
# ----------------------------
if [ "${SKIP_DB}" != "1" ]; then
  echo "Deploying Qdrant..."
  kubectl apply -n $NAMESPACE -f "$K8S_DIR/qdrant.yaml"

  # Wait for Qdrant to be ready
  echo "Waiting for Qdrant to be ready..."
  kubectl rollout status statefulset/qdrant -n $NAMESPACE --timeout=300s
else
  echo "Skipping database deployment (SKIP_DB=1)"
fi

# ----------------------------
# --- Deploy Postgres DB ---
# ----------------------------
if [ "${SKIP_DB}" != "1" ]; then
  echo "Deploying Postgres..."
  kubectl apply -n $NAMESPACE -f "$K8S_DIR/postgres/postgres-secrets.yaml"
  kubectl apply -n $NAMESPACE -f "$K8S_DIR/postgres/postgres-pvc.yaml"
  kubectl apply -n $NAMESPACE -f "$K8S_DIR/postgres/postgres-service.yaml"
  kubectl apply -n $NAMESPACE -f "$K8S_DIR/postgres/postgres.yaml"

  echo "Waiting for Postgres to be ready..."
  kubectl rollout status deployment/postgres-db -n $NAMESPACE --timeout=300s
else
  echo "Skipping database deployment (SKIP_DB=1)"
fi

# ----------------------------
# --- Build and Deploy Services ---
# ----------------------------
SERVICES="frontend host-agent faq-agent summary-agent vector-db-service guardrails-service repository-service"

for service in $SERVICES; do
  # Define per-service variables
  case "$service" in
    "frontend")
      DOCKERFILE="frontend/Dockerfile"
      BUILD_CONTEXT="frontend"
      ;;
    "host-agent")
      DOCKERFILE="backend/host_agent/Dockerfile"
      BUILD_CONTEXT="."
      ;;
    "faq-agent")
      DOCKERFILE="backend/agents/faq_agent/Dockerfile"
      BUILD_CONTEXT="."
      ;;
    "summary-agent")
      DOCKERFILE="backend/agents/summary_agent/Dockerfile"
      BUILD_CONTEXT="."
      ;;
    "vector-db-service")
      DOCKERFILE="backend/services/vector_db_service/Dockerfile"
      BUILD_CONTEXT="."
      ;;
    "guardrails-service")
      DOCKERFILE="backend/services/guardrails/Dockerfile"
      BUILD_CONTEXT="."
      ;;
    "repository-service")
      DOCKERFILE="backend/services/repository_service/Dockerfile"
      BUILD_CONTEXT="."
      ;;
  esac

  IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${service}:latest"

  echo "Building $service..."

  if [ "$service" = "guardrails-service" ]; then
    : "${GUARDRAILS_API_KEY:?GUARDRAILS_API_KEY is required for guardrails-service build}"
    : "${GUARDRAILS_LLM_MODEL:?GUARDRAILS_LLM_MODEL is required for guardrails-service build}"

    docker build \
      --platform linux/amd64 \
      --build-arg GUARDRAILS_API_KEY="$GUARDRAILS_API_KEY" \
      --build-arg GUARDRAILS_LLM_MODEL="$GUARDRAILS_LLM_MODEL" \
      -t "$IMAGE" \
      -f "$DOCKERFILE" \
      "$BUILD_CONTEXT"
  else
    docker build \
      --platform linux/amd64 \
      -t "$IMAGE" \
      -f "$DOCKERFILE" \
      "$BUILD_CONTEXT"
  fi

  echo "Pushing $service..."
  docker push "$IMAGE"

  echo "Deploying $service..."
  # Replace IMAGE_PLACEHOLDER with actual image and apply
  sed "s|IMAGE_PLACEHOLDER|$IMAGE|g" "$K8S_DIR/${service}.yaml" | kubectl apply -n $NAMESPACE -f -

  if [ "$service" = "guardrails-service" ]; then
    kubectl set resources deployment/guardrails-service -n $NAMESPACE \
      --requests=cpu=500m,memory=1Gi,ephemeral-storage=1Gi \
      --limits=cpu=1,memory=2Gi,ephemeral-storage=1Gi
  fi
done

# ----------------------------
# --- Deploy Gateway (Nginx) ---
# ----------------------------
echo "Deploying Gateway with static IP: $INGRESS_STATIC_IP"
sed "s/STATIC_IP_PLACEHOLDER/$INGRESS_STATIC_IP/g" "$K8S_DIR/gateway.yaml" | kubectl apply -n $NAMESPACE -f -

echo ""
echo "--------------------------------------------------------"
echo "Deployment Complete!"
echo "Application accessible at: http://$INGRESS_STATIC_IP"
echo "--------------------------------------------------------"