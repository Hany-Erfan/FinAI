#!/bin/bash
set -e

# Configuration - can be overridden via environment variables
PROJECT_ID="${GCP_PROJECT_ID:-agentixbuddy-dev}"
REGION="${GCP_REGION:-europe-west3}"
CLUSTER_NAME="${GKE_CLUSTER_NAME:-agentixbuddy-cluster}"
STATIC_IP_NAME="${GKE_STATIC_IP_NAME:-agentixbuddy-ingress-ip}"

echo "Tearing down: project=$PROJECT_ID, region=$REGION, cluster=$CLUSTER_NAME"

echo "Deleting GKE cluster: $CLUSTER_NAME in $REGION..."
gcloud container clusters delete $CLUSTER_NAME --region $REGION --quiet || echo "Cluster not found or already deleted."

echo "Deleting static IP: $STATIC_IP_NAME in $REGION..."
gcloud compute addresses delete $STATIC_IP_NAME --region $REGION --quiet || echo "Static IP not found or already deleted."

echo "Teardown complete."