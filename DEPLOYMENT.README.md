# Deployment Guide

This guide explains how to deploy the **AgentixBuddy** application to Google Kubernetes Engine (GKE) Autopilot.

---

## 1. Prerequisites & Installation

### Windows
1.  **Docker Desktop**: Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/). Ensure WSL 2 backend is enabled.
2.  **WSL 2 (Recommended)**: It is highly recommended to run these commands inside a WSL 2 (Ubuntu) terminal for compatibility with `make` and bash scripts.
    *   Open PowerShell as Admin: `wsl --install`
3.  **Google Cloud CLI (`gcloud`)**:
    *   Install via PowerShell: `(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:Temp\GoogleCloudSDKInstaller.exe"); & $env:Temp\GoogleCloudSDKInstaller.exe`
    *   Or follow [official docs](https://cloud.google.com/sdk/docs/install#windows).
4.  **`kubectl`**:
    *   Run: `gcloud components install kubectl`
5.  **`make`**:
    *   In WSL 2 (Ubuntu): `sudo apt-get update && sudo apt-get install make`
    *   Creating a GKE cluster also requires the GKE Auth Plugin: `gcloud components install gke-gcloud-auth-plugin`

### MacOS
1.  **Homebrew**: Ensure you have [Homebrew](https://brew.sh/) installed.
2.  **Docker Desktop**: `brew install --cask docker` (or download from website).
3.  **Google Cloud CLI (`gcloud`)**:
    *   `brew install --cask google-cloud-sdk`
    *   Initialize: `gcloud init`
4.  **`kubectl`**:
    *   `gcloud components install kubectl`
    *   `gcloud components install gke-gcloud-auth-plugin`
5.  **`make`**: Typically pre-installed. If not: `xcode-select --install`.

---

## 2. Deployment Process

The deployment is automated via the `scripts/deployment/deploy_gke.sh` script, which is triggered by `make deploy-cluster`.

**What happens step-by-step:**

1.  **Authentication**: Logs you into Google Cloud (`gcloud auth login`).
2.  **Cluster Provisioning**:
    *   Checks if the cluster `agentixbuddy-cluster` exists.
    *   If not, creates a **GKE Autopilot** cluster in `europe-west3`.
3.  **Static IP Reservation**:
    *   Reserves a regional static IP named `agentixbuddy-ingress-ip` (if not already existing).
    *   This IP is used for the Gateway/LoadBalancer.
4.  **Build & Push Images**:
    *   Builds Docker images for specific platforms (`linux/amd64`) to ensure compatibility with GKE.
    *   Images built: Frontend, Host Agent, FAQ Agent, Vector DB Service, Guardrails Service.
    *   Pushes all images to Google Artifact Registry.
5.  **Infrastructure Setup**:
    *   Creates namespace `agentixbuddy`.
    *   Deploys **Qdrant** vector database as a StatefulSet.
    *   Creates **ConfigMaps** from your local `.env` file.
6.  **Service Deployment**:
    *   Deploys all agent microservices and the frontend.
    *   Configures inter-service communication via environment variables.
7.  **Expose Application**:
    *   Deploys an **Nginx Gateway** service with type `LoadBalancer`.
    *   Assigns the reserved static IP to the LoadBalancer.
    *   Prints the final accessible URL.

---

## 3. Makefile Commands & Usage

### Cloud Deployment (GKE)

| Command | Description |
| :--- | :--- |
| `make deploy-cluster` | Full cluster deployment to GKE. |
| `make teardown-cluster` | **Destructive**. Deletes all resources in the `agentixbuddy` namespace and tears down the cluster to stop costs. |
| `make deploy-status` | Shows status of Pods, Services, and Ingress in the cluster. |
| `make deploy-logs` | Tails logs from all running pods in the cluster. |
| `make deploy-cost-estimate` | Estimates monthly cost based on current pod resource usage. |

### Local Development (Docker Compose)

| Command | Description |
| :--- | :--- |
| `make up` | Starts the full stack locally. |
| `make down` | Stops containers and removes volumes. |
| `make logs` | Follows logs for all local services. |
| `make status` | Shows running local containers (`docker-compose ps`). |

---

## 4. Environment Variables

Ensure your `.env` file contains the required environment variables:

```
GOOGLE_API_KEY=your-google-api-key
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production-min-32-chars
JWT_EXPIRE_MINUTES=480
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

---

## 5. Troubleshooting

*   **deployment script syntax error:** If editing scripts on Windows, ensure line endings are LF, not CRLF.
*   **gcloud permission denied:** Run `gcloud auth login` and `gcloud auth application-default login`.
*   **ImagePullBackOff:** Usually means the image wasn't pushed correctly or the cluster doesn't have permissions. The script handles auth, so try re-running the deployment.

---

## 6. Architecture

```
                    ┌─────────────────┐
                    │   LoadBalancer  │
                    │   (Static IP)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Nginx Gateway  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌─────▼─────┐         ┌───▼────┐
   │Frontend │         │Host Agent │         │  APIs  │
   └─────────┘         └─────┬─────┘         └────────┘
                             │
                        ┌────▼────┐
                        │FAQ Agent│
                        └────┬────┘
                             │
                   ┌─────────▼──────────┐
                   │ Vector DB Service  │
                   └─────────┬──────────┘
                             │
                        ┌────▼────┐
                        │ Qdrant  │
                        └─────────┘
```