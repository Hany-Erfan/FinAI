# Deployment Guide

This guide explains how to deploy the **FinAI** application to Google Kubernetes Engine (GKE) Autopilot.

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
    *   Checks if the cluster `finai-cluster` exists.
    *   If not, creates a **GKE Autopilot** cluster in `europe-west3`.
3.  **Static IP Reservation**:
    *   Reserves a regional static IP named `finai-ingress-ip` (if not already existing).
    *   This IP is used for the Gateway/LoadBalancer.
4.  **Build & Push Images**:
    *   Builds Docker images for specific platforms (`linux/amd64`) to ensure compatibility with GKE.
    *   Images built: Frontend, Host Agent, FAQ Agent, Vector DB Service, Guardrails Service.
    *   Pushes all images to Google Artifact Registry.
5.  **Infrastructure Setup**:
    *   Creates namespace `finai`.
    *   Deploys **Qdrant** vector database as a StatefulSet.
    *   Deploys **LGTM** observability stack (Grafana + Loki + Tempo) as a StatefulSet.
    *   Creates **ConfigMaps** from your local `.env` file.
6.  **Service Deployment**:
    *   Deploys all agent microservices and the frontend.
    *   Configures inter-service communication via environment variables.
    *   All services export OpenTelemetry traces and logs to the LGTM stack.
7.  **Expose Application**:
    *   Deploys an **Nginx Gateway** service with type `LoadBalancer`.
    *   Assigns the reserved static IP to the LoadBalancer.
    *   Prints the final accessible URL.
8.  **Dashboard Upload**:
    *   Uploads the POC Effectiveness Dashboard to Grafana automatically.

---

## 3. Makefile Commands & Usage

### Cloud Deployment (GKE)

| Command | Description |
| :--- | :--- |
| `make deploy-cluster` | Full cluster deployment to GKE (includes LGTM + dashboard upload). |
| `make deploy-services` | Redeploy services only (keeps databases and LGTM). |
| `make teardown-cluster` | **Destructive**. Deletes all resources in the `finai` namespace and tears down the cluster to stop costs. |
| `make deploy-status` | Shows status of Pods, Services, and Ingress in the cluster. |
| `make deploy-logs` | Tails logs from all running pods in the cluster. |
| `make deploy-cost-estimate` | Estimates monthly cost based on current pod resource usage. |

### Observability

| Command | Description |
| :--- | :--- |
| `make upload-dashboard` | Upload POC Metrics Dashboard to local Grafana (localhost:3000). |
| `make upload-dashboard-prod` | Upload POC Metrics Dashboard to production Grafana (via kubectl port-forward). |

### Local Development (Docker Compose)

| Command | Description |
| :--- | :--- |
| `make up` | Starts the full stack locally (without monitoring). |
| `make down` | Stops containers and removes volumes. |
| `make logs` | Follows logs for all local services. |
| `make status` | Shows running local containers (`docker-compose ps`). |

To start with the monitoring stack locally:
```bash
docker-compose --profile monitor up -d
make upload-dashboard
```

Grafana is then accessible at `http://localhost:3000` (default credentials: `admin`/`admin`).

---

## 4. Environment Variables

Ensure your `.env` file contains the required environment variables:

```
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production-min-32-chars
JWT_EXPIRE_MINUTES=480
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

Ensure your `.env.secrets` file contains API keys (loaded separately for security):

```
GOOGLE_API_KEY=your-google-api-key
```

### OpenTelemetry & Logging (set automatically in docker-compose and K8s manifests)

| Variable | Description | Example |
| :--- | :--- | :--- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | `lgtm:4317` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Export protocol | `grpc` |
| `OTEL_TRACES_ENABLED` | Enable/disable tracing | `true` |
| `OTEL_SERVICE_NAME` | Service name for traces | `host-agent` |
| `LOG_LOKI_ENDPOINT` | Loki log endpoint | `lgtm:4317` |
| `LOG_SERVICE_NAME` | Service name for logs | `host-agent` |

---

## 5. HTTPS Configuration (cert-manager & Let's Encrypt)

The application uses **cert-manager** with Let's Encrypt (HTTP-01 challenge) to automatically provision and renew TLS certificates. HTTPS is enforced by default.

When you run `make deploy-cluster` on a fresh cluster:
1. `cert-manager` is installed.
2. A temporary "dummy" TLS certificate is generated so Nginx can start successfully.
3. Once running, Let's Encrypt verifies the domain and seamlessly replaces the dummy certificate with the real, valid TLS certificate in the background (usually takes 1-3 minutes).
4. All HTTP traffic is automatically `301 Redirected` to HTTPS.

| Command | Description |
| :--- | :--- |
| `kubectl get certificate finai-cert -n finai -w` | Monitor the Let's Encrypt certificate provisioning status. Wait until `READY=True`. |

---

## 6. Troubleshooting

*   **deployment script syntax error:** If editing scripts on Windows, ensure line endings are LF, not CRLF.
*   **gcloud permission denied:** Run `gcloud auth login` and `gcloud auth application-default login`.
*   **ImagePullBackOff:** Usually means the image wasn't pushed correctly or the cluster doesn't have permissions. The script handles auth, so try re-running the deployment.
*   **Grafana not loading in production:** Ensure the LGTM pod is running (`kubectl get pods -n finai -l app=lgtm`) and the gateway has the `/grafana/` route.

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
     ┌───────────┬───────────┼───────────┬──────────┐
     │           │           │           │          │
┌────▼────┐ ┌───▼────┐ ┌────▼─────┐ ┌───▼───┐ ┌───▼───┐
│Frontend │ │Grafana │ │Host Agent│ │Vector │ │  FAQ  │
│         │ │ (LGTM) │ └────┬─────┘ │  DB   │ │ Agent │
└─────────┘ └───▲────┘      │       └───┬───┘ └───┬───┘
                │            │           │         │
                │       ┌────▼──────┐    │         │
                │       │Guardrails │    │         │
                │       └───────────┘    │         │
                │                   ┌────▼────┐    │
                │                   │ Qdrant  │    │
                │                   └─────────┘    │
                │                                  │
                └──── OTEL traces & logs ──────────┘
```

All backend services export OpenTelemetry traces (via gRPC) and logs (via Loki) to the LGTM stack. The Grafana dashboard is accessible at `/grafana/` through the gateway.
