#!/bin/bash
set -e

# ----------------------------
# --- Load .env file first ---
# ----------------------------
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Configuration - can be overridden via .env or environment variables
PROJECT_ID="${GCP_PROJECT_ID:-agentixbuddy-dev}"
REGION="${GCP_REGION:-europe-west3}"
CLUSTER_NAME="${GKE_CLUSTER_NAME:-agentixbuddy-cluster}"
STATIC_IP_NAME="${GKE_STATIC_IP_NAME:-agentixbuddy-ingress-ip}"

# Set DELETE_STATIC_IP=true to also delete the reserved IP address
DELETE_STATIC_IP="${DELETE_STATIC_IP:-false}"

echo "Tearing down: project=$PROJECT_ID, region=$REGION, cluster=$CLUSTER_NAME"

echo "Deleting GKE cluster: $CLUSTER_NAME in $REGION..."
gcloud container clusters delete $CLUSTER_NAME --region $REGION --quiet || echo "Cluster not found or already deleted."

if [ "$DELETE_STATIC_IP" = "true" ]; then
  echo "Deleting static IP: $STATIC_IP_NAME in $REGION..."
  gcloud compute addresses delete $STATIC_IP_NAME --region $REGION --quiet || echo "Static IP not found or already deleted."
else
  STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" --region "$REGION" --format="get(address)" 2>/dev/null || echo "")
  echo "Static IP preserved: $STATIC_IP_NAME ($STATIC_IP)"
  echo "To delete it, run: DELETE_STATIC_IP=true make teardown-cluster"
fi

echo "Teardown complete."