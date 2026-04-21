# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY backend/services/voice_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory structure
COPY backend/ ./backend/

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8008

# Run the voice service server
CMD ["python", "-m", "uvicorn", "backend.services.voice_service.server:voice_db_app", "--host", "0.0.0.0", "--port", "8008", "--reload", "--log-level", "debug", "--use-colors"]
