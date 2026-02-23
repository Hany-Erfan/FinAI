# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy observability module
COPY observability/ ./observability/

# Copy pyproject.toml and install dependencies
COPY backend/host_agent/pyproject.toml ./pyproject.toml
ENV UV_HTTP_TIMEOUT=300
RUN --mount=type=cache,target=/root/.cache/uv \
    sed -i 's|path = "../../observability"|path = "./observability"|' pyproject.toml && \
    uv pip install --system -r pyproject.toml

# Copy the entire backend directory structure
COPY backend/ ./backend/

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the orchestrator server
CMD ["python", "-m", "backend.host_agent.main"]
