# Observability Module

This module provides OpenTelemetry-based distributed tracing for the Purchaize agent system, exporting W3C traces to Grafana via the LGTM stack.

## Features

- **OpenTelemetry SDK Integration**: Full support for W3C trace context propagation
- **OTLP Export**: Supports both gRPC and HTTP protocols
- **Auto-instrumentation**: FastAPI, Requests, and Logging instrumentation
- **Environment-based Configuration**: Easy configuration via environment variables
- **Grafana LGTM Stack**: Pre-configured with Loki, Grafana, Tempo, and Mimir

## Installation

This module is designed to be installed as a local package:

```bash
pip install -e observability
```

Or include in your requirements.txt:

```
-e ../../observability  # for agents in backend/agents/
-e ../observability     # for other backend services
```

## Usage

### Basic Setup

```python
from observability import setup_telemetry, get_tracer

# Initialize telemetry (reads from environment variables automatically)
setup_telemetry()

# Get a tracer for creating spans
tracer = get_tracer(__name__)

# Create spans
with tracer.start_as_current_span("operation-name"):
    # Your code here
    pass
```

### Configuration via Environment Variables

The simplest way to configure telemetry is through environment variables:

```bash
export OTEL_SERVICE_NAME="my-agent"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://lgtm:4317"
export OTEL_EXPORTER_OTLP_PROTOCOL="grpc"
export OTEL_TRACES_ENABLED="true"
```

Then just call:
```python
setup_telemetry()
```

### Advanced: Programmatic Configuration

For more control, you can validate settings before initialization:

```python
from observability import TelemetrySettings
import os

# Set environment variables programmatically
os.environ["OTEL_SERVICE_NAME"] = "custom-agent"
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://custom:4317"

# Validate settings before setup
settings = TelemetrySettings()
print(f"Service: {settings.service_name}")
print(f"Endpoint: {settings.exporter_otlp_endpoint}")

# Initialize with validated settings
setup_telemetry()
```
```
```

### Environment Variables

Configure OpenTelemetry using these environment variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OTEL_SERVICE_NAME` | Service name for traces | None | Yes |
| `OTEL_SERVICE_VERSION` | Service version | `1.0.0` | No |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | None | Yes |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Export protocol (grpc or http) | `grpc` | No |
| `OTEL_TRACES_ENABLED` | Enable/disable tracing | `true` | No |
| `OTEL_ENABLE_LOGGING_INSTRUMENTATION` | Enable logging instrumentation | `true` | No |

### .env File Support

You can also use a `.env` file in your project root:

```env
OTEL_SERVICE_NAME=my-agent
OTEL_SERVICE_VERSION=1.0.0
OTEL_EXPORTER_OTLP_ENDPOINT=http://lgtm:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_ENABLED=true
OTEL_ENABLE_LOGGING_INSTRUMENTATION=true
```

The settings will automatically load from this file.

### Docker Compose Configuration

The observability module is integrated with docker-compose:

```yaml
services:
  my-agent:
    environment:
      - OTEL_SERVICE_NAME=my-agent
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://lgtm:4317
      - OTEL_EXPORTER_OTLP_PROTOCOL=grpc
      - OTEL_TRACES_ENABLED=true
```

## Grafana LGTM Stack

The LGTM (Loki, Grafana, Tempo, Mimir) stack provides a complete observability solution:

- **Grafana**: Visualization and dashboards (http://localhost:3000)
- **Tempo**: Distributed tracing backend
- **Loki**: Log aggregation
- **Mimir**: Metrics storage

### Starting Monitoring

```bash
# Start all services with monitoring
make monitor-up

# Start without monitoring
make up

# View monitoring logs
make monitor-logs

# Stop monitoring
make monitor-down
```

### Accessing Grafana

1. Navigate to http://localhost:3000
2. Default credentials: `admin` / `admin`
3. Explore traces in the Tempo data source
4. View logs in Loki
5. Create custom dashboards

## OTLP Endpoints

The LGTM container exposes multiple endpoints:

- **gRPC**: `http://lgtm:4317` (internal) or `http://localhost:4317` (external)
- **HTTP**: `http://lgtm:4318` (internal) or `http://localhost:4318` (external)
- **Grafana UI**: `http://localhost:3000`

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Agent     │         │     LGTM     │         │   Grafana   │
│             │ OTLP    │              │         │  Dashboard  │
│ + Telemetry ├────────►│ Tempo/Loki   ├────────►│             │
│   Module    │ (gRPC)  │              │         │             │
└─────────────┘         └──────────────┘         └─────────────┘
```

## Development

### Project Structure

```
observability/
├── __init__.py          # Module exports
├── telemetry.py         # OpenTelemetry setup
├── requirements.txt     # Dependencies
├── setup.py            # Package configuration
└── README.md           # This file
```

### Running Tests

```bash
# Start monitoring stack
make monitor-up

# Run your agents (they will send traces)
docker-compose up orchestrator purchase-agent

# Check traces in Grafana
open http://localhost:3000
```

### Troubleshooting

**Traces not appearing:**
- Verify `OTEL_EXPORTER_OTLP_ENDPOINT` is set correctly
- Check that `OTEL_TRACES_ENABLED=true`
- Ensure LGTM container is healthy: `docker-compose ps lgtm`
- View agent logs for telemetry initialization messages

**Connection errors:**
- Verify network connectivity: `docker-compose network inspect purchaize_default`
- Check LGTM health: `docker-compose exec lgtm test -f /tmp/ready`
- Review LGTM logs: `docker-compose logs lgtm`

## Cloud Deployment

For GKE deployment, use the provided Makefile command:

```bash
make deploy-monitoring
```

This will execute the `deploy_gke.sh` script with monitoring profile enabled.

## References

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [Grafana LGTM](https://grafana.com/docs/grafana-cloud/monitor-applications/application-observability/)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
