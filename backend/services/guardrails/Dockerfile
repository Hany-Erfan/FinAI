# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install system/build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy observability module
COPY observability/ ./observability/

# Environment
ENV UV_HTTP_TIMEOUT=300
ENV UV_SYSTEM_PYTHON=1
ENV NLTK_DATA=/usr/local/nltk_data
ENV PYTHONPATH=/app

# Copy dependency metadata first for better layer caching
COPY backend/services/guardrails/pyproject.toml ./pyproject.toml

# Install Python dependencies declared in pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    sed -i 's|path = "../../observability"|path = "./observability"|' pyproject.toml && \
    uv pip install --system -r pyproject.toml

# Copy app code
COPY backend/ ./backend/

# Build args
ARG GUARDRAILS_API_KEY
ARG GUARDRAILS_LLM_MODEL

# Runtime env vars
ENV GUARDRAILS_API_KEY=${GUARDRAILS_API_KEY}
ENV GUARDRAILS_LLM_MODEL=${GUARDRAILS_LLM_MODEL}

# Configure Guardrails and install Hub packages only when a token is provided
RUN if [ -n "$GUARDRAILS_API_KEY" ]; then \
    yes "y" | guardrails configure --token="$GUARDRAILS_API_KEY" && \
    guardrails hub install --no-install-local-models hub://guardrails/detect_pii && \
    guardrails hub install --no-install-local-models hub://tryolabs/restricttotopic && \
    guardrails hub install --no-install-local-models hub://guardrails/toxic_language && \
    guardrails hub install --no-install-local-models hub://guardrails/secrets_present && \
    guardrails hub install --no-install-local-models hub://guardrails/gibberish_text; \
    fi

# Ensure NLTK resources are present
RUN python - <<'PY'
import os
import nltk
from nltk.data import find

download_dir = "/usr/local/nltk_data"
os.makedirs(download_dir, exist_ok=True)

nltk.download("punkt", download_dir=download_dir)
nltk.download("punkt_tab", download_dir=download_dir)

find("tokenizers/punkt")
find("tokenizers/punkt_tab/english")

print("NLTK resources present.")
PY

# Expose port
EXPOSE 8005

# Start service
CMD ["python", "-m", "backend.services.guardrails.server"]