# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast resolution (matching the host agent pattern)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy pyproject.toml and install dependencies
COPY backend/services/guardrails/pyproject.toml ./pyproject.toml
ENV UV_HTTP_TIMEOUT=300
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system google-generativeai

# Copy the entire backend directory structure
COPY backend/ ./backend/

# Accept the API key as a build argument
ARG GUARDRAILS_API_KEY
ENV GUARDRAILS_API_KEY=$GUARDRAILS_API_KEY
ENV GUARDRAILS_LLM_MODEL=$GUARDRAILS_LLM_MODEL
ENV UV_SYSTEM_PYTHON=1

# Configure Guardrails and install Hub packages
RUN if [ -n "$GUARDRAILS_API_KEY" ]; then \
    yes "y" | guardrails configure --token=$GUARDRAILS_API_KEY && \
    guardrails hub install --no-install-local-models hub://guardrails/detect_pii && \
    guardrails hub install --no-install-local-models hub://tryolabs/restricttotopic && \
    guardrails hub install --no-install-local-models hub://guardrails/toxic_language && \
    guardrails hub install --no-install-local-models hub://guardrails/secrets_present && \
    guardrails hub install --no-install-local-models hub://guardrails/gibberish_text; \
    fi

# Ensure NLTK resources are present for hub validators
ENV NLTK_DATA=/usr/local/nltk_data
RUN python - <<'PY'
import os
import nltk

os.makedirs("/usr/local/nltk_data", exist_ok=True)

# These are the resources your logs are asking for
nltk.download("punkt", download_dir="/usr/local/nltk_data")
nltk.download("punkt_tab", download_dir="/usr/local/nltk_data")

# Fail build if they are still missing
from nltk.data import find
find("tokenizers/punkt")
find("tokenizers/punkt_tab/english")
print("NLTK resources present.")
PY

ENV PYTHONPATH=/app

# Expose port (8005 by default for guardrails)
EXPOSE 8005

# Run the guardrails server
CMD ["python", "-m", "backend.services.guardrails.server"]