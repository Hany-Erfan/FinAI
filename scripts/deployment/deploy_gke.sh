#!/bin/bash
set -e

# ----------------------------
# --- GCloud Auth & Cluster ---
# ----------------------------

gcloud auth login --quiet
gcloud config set project agentixbuddy-dev

# ----------------------------
# --- Cluster Configuration ---
# ----------------------------
PROJECT_ID="agentixbuddy-dev"
REGION="europe-west3"
REPO="agentixbuddy-repo"
NAMESPACE="agentixbuddy"
CLUSTER_NAME="agentixbuddy-cluster"

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
if ! gcloud compute addresses describe "$STATIC_IP_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "Static IP not found. Creating static IP: $STATIC_IP_NAME ..."
  gcloud compute addresses create "$STATIC_IP_NAME" --region "$REGION"
else
  echo "Static IP already exists: $STATIC_IP_NAME"
fi
INGRESS_STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" --region "$REGION" --format="get(address)")
echo "Ingress static IP: $INGRESS_STATIC_IP"

# Load environment variables from .env if it exists
if [ -f .env ]; then
  echo "Loading environment from .env file..."
  set -a
  source .env
  set +a
else
  echo "No .env file found, using GCP-provided configuration"
fi

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
# --- Create ConfigMap from .env ---
# ----------------------------
kubectl create configmap app-env \
  --from-env-file=.env \
  -n $NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

# ----------------------------
# --- Configure Workload Identity ---
# ----------------------------
GSA_NAME="agentixbuddy-app-sa"
GSA_EMAIL="${GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KSA_NAME="agentixbuddy-ksa"

echo "Configuring Workload Identity..."

# 1. Create Google Service Account if it doesn't exist
if ! gcloud iam service-accounts describe "$GSA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Creating Google Service Account: $GSA_NAME"
  gcloud iam service-accounts create "$GSA_NAME" \
    --description="Service account for AgentixBuddy GKE pods" \
    --display-name="AgentixBuddy App SA" \
    --project="$PROJECT_ID"
fi

# 2. Grant roles to GSA (AI Platform User for GenAI)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${GSA_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition="None" >/dev/null

# 3. Create Kubernetes Service Account
kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: $KSA_NAME
  namespace: $NAMESPACE
  annotations:
    iam.gke.io/gcp-service-account: $GSA_EMAIL
EOF

# 4. Bind GSA to KSA for Workload Identity
gcloud iam service-accounts add-iam-policy-binding "$GSA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${NAMESPACE}/${KSA_NAME}]" \
  --condition="None" >/dev/null

# ----------------------------
# --- CLEANUP EXISTING RESOURCES ---
# ----------------------------
echo "Cleaning up all deployments, statefulsets, jobs, pods, services, PVCs in $NAMESPACE..."
kubectl delete deployment --all -n $NAMESPACE --ignore-not-found
kubectl delete statefulset --all -n $NAMESPACE --ignore-not-found
kubectl delete job --all -n $NAMESPACE --ignore-not-found
kubectl delete pod --all -n $NAMESPACE --ignore-not-found
kubectl delete service --all -n $NAMESPACE --ignore-not-found
kubectl delete pvc --all -n $NAMESPACE --ignore-not-found

# ----------------------------
# --- Deploy Qdrant (Vector Database) ---
# ----------------------------
kubectl apply -n $NAMESPACE -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: qdrant
spec:
  clusterIP: None
  selector:
    app: qdrant
  ports:
    - name: http
      port: 6333
      targetPort: 6333
    - name: grpc
      port: 6334
      targetPort: 6334
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: qdrant
spec:
  serviceName: qdrant
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      nodeSelector:
        cloud.google.com/gke-spot: "true"
      containers:
        - name: qdrant
          image: qdrant/qdrant:latest
          ports:
            - containerPort: 6333
            - containerPort: 6334
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: 500m
              memory: 1Gi
          volumeMounts:
            - name: qdrant-data
              mountPath: /qdrant/storage
          readinessProbe:
            tcpSocket:
              port: 6333
            initialDelaySeconds: 5
            periodSeconds: 5
  volumeClaimTemplates:
    - metadata:
        name: qdrant-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 5Gi
EOF

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to be ready..."
kubectl rollout status statefulset/qdrant -n $NAMESPACE --timeout=300s

# ----------------------------
# --- Build and Push Custom Services ---
# ----------------------------
# List of services to build and deploy
SERVICES="frontend host-agent faq-agent vector-db-service guardrails-service"

for service in $SERVICES; do
  # Define per-service variables
  case "$service" in
    "frontend")
      DOCKERFILE="frontend/Dockerfile"
      PORT=5173
      ;;
    "host-agent")
      DOCKERFILE="backend/host_agent/Dockerfile"
      PORT=8000
      ;;
    "faq-agent")
      DOCKERFILE="backend/agents/faq_agent/Dockerfile"
      PORT=8001
      ;;
    "vector-db-service")
      DOCKERFILE="backend/services/vector_db_service/Dockerfile"
      PORT=8004
      ;;
    "guardrails-service")
      DOCKERFILE="backend/services/guardrails/Dockerfile"
      PORT=8005
      ;;
  esac

  IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${service}:latest"
  echo "Building $service"
  docker build --platform linux/amd64 -t "$IMAGE" -f "$DOCKERFILE" .
  echo "Pushing $service"
  docker push "$IMAGE"

  # ----------------------------
  # --- Deploy Custom Services ---
  # ----------------------------
  EXTRA_ENV_VARS=""

  # Add service-specific environment variables
  case "$service" in
    "host-agent")
      EXTRA_ENV_VARS=$(cat <<'YAML'
            - name: FAQ_AGENT_URL
              value: http://faq-agent:8001
            - name: GUARDRAILS_URL
              value: http://guardrails-service:8005
YAML
)
      ;;
    "vector-db-service")
      EXTRA_ENV_VARS=$(cat <<'YAML'
            - name: QDRANT_URL
              value: http://qdrant:6333
            - name: QDRANT_API_KEY
              value: ""
            - name: VECTOR_DB_COLLECTION
              value: sample_bank_products
YAML
)
      ;;
    "faq-agent")
      EXTRA_ENV_VARS=$(cat <<'YAML'
            - name: VECTOR_DB_SERVICE_URL
              value: http://vector-db-service:8004/vector_db_service
YAML
)
      ;;
  esac

  # Set resource requests based on service type
  RESOURCE_REQUESTS="cpu: 100m
              memory: 256Mi"
  RESOURCE_LIMITS="cpu: 200m
              memory: 512Mi"

  kubectl apply -n $NAMESPACE -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: $service
  template:
    metadata:
      labels:
        app: $service
    spec:
      serviceAccountName: $KSA_NAME
      nodeSelector:
        cloud.google.com/gke-spot: "true"
      containers:
        - name: $service
          image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${service}:latest
          ports:
            - containerPort: ${PORT}
          envFrom:
            - configMapRef:
                name: app-env
          env:
            - name: PYTHONUNBUFFERED
              value: "1"
$EXTRA_ENV_VARS
          resources:
            requests:
              $RESOURCE_REQUESTS
            limits:
              $RESOURCE_LIMITS
EOF

  # --- EXPOSE SERVICES ---
  if [ "$service" == "frontend" ]; then
    kubectl delete svc frontend -n "$NAMESPACE" --ignore-not-found

    kubectl apply -n "$NAMESPACE" -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  type: ClusterIP
  selector:
    app: frontend
  ports:
    - port: 80
      targetPort: ${PORT}
      protocol: TCP
EOF
  else
    kubectl expose deployment "$service" \
      --type=ClusterIP \
      --port="${PORT}" \
      --target-port="${PORT}" \
      -n "$NAMESPACE" \
      --dry-run=client -o yaml | kubectl apply -f -
  fi

done

# ----------------------------
# --- Deploy Gateway (Nginx) ---
# ----------------------------
echo "Deploying Gateway with static IP: $INGRESS_STATIC_IP"
sed "s/STATIC_IP_PLACEHOLDER/$INGRESS_STATIC_IP/g" scripts/deployment/custom_gateway.yaml | kubectl apply -f -

echo ""
echo "--------------------------------------------------------"
echo "Deployment Complete!"
echo "Application accessible at: http://$INGRESS_STATIC_IP"
echo "--------------------------------------------------------"